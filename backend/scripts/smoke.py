"""Walking-skeleton smoke test against a live api + worker.

Creates a ping run, follows its SSE stream, and asserts the full event
sequence arrives and the run completes. Exits non-zero on failure.

Usage: uv run python scripts/smoke.py [base_url]   (default http://localhost:8000)
"""

import sys
import time

import httpx

TIMEOUT = 30.0
READY_DEADLINE = 60.0


def wait_until_ready(client: httpx.Client) -> None:
    deadline = time.monotonic() + READY_DEADLINE
    last: str = "no response"
    while time.monotonic() < deadline:
        try:
            ready = client.get("/health/ready")
            if ready.status_code == 200:
                return
            last = f"{ready.status_code}: {ready.text}"
        except httpx.TransportError as exc:
            last = str(exc)
        time.sleep(2)
    raise AssertionError(f"/health/ready never became ready: {last}")


def main() -> int:
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    with httpx.Client(base_url=base_url, timeout=TIMEOUT) as client:
        wait_until_ready(client)

        created = client.post("/api/v1/runs", json={"kind": "ping"})
        assert created.status_code == 201, f"create run -> {created.status_code}: {created.text}"
        run_id = created.json()["id"]
        print(f"created run {run_id}")

        events: list[str] = []
        with client.stream("GET", f"/api/v1/runs/{run_id}/events") as response:
            assert response.status_code == 200
            for line in response.iter_lines():
                if line.startswith("event: "):
                    event_type = line.removeprefix("event: ")
                    events.append(event_type)
                    print(f"  sse: {event_type}")
                    if event_type in ("run.completed", "run.failed"):
                        break

        assert events[0] == "run.status", events
        assert events.count("agent.token") == 3, events
        assert events[-1] == "run.completed", events

        final = client.get(f"/api/v1/runs/{run_id}")
        assert final.json()["status"] == "completed", final.text

    print("SMOKE OK: web -> api -> queue -> worker -> events -> SSE all green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
