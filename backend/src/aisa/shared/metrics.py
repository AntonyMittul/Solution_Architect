"""Application metrics (doc 14). Instruments are created at import time on the
proxy meter and start recording once configure_metrics installs a provider, so
they are cheap no-ops when observability is disabled."""

from aisa.shared.telemetry import get_meter

_meter = get_meter("aisa")

# RED for HTTP: a duration histogram implies rate and errors via its labels.
http_server_duration = _meter.create_histogram(
    "aisa.http.server.duration",
    unit="ms",
    description="HTTP server request duration",
)

# Run outcomes (run success SLO).
runs_total = _meter.create_counter(
    "aisa.runs.total",
    description="Runs that reached a terminal state, by kind and status",
)

# LLM cost driver: tokens by model and direction (in/out).
llm_tokens_total = _meter.create_counter(
    "aisa.llm.tokens.total",
    description="LLM tokens consumed, by model and direction",
)


def record_http_request(method: str, status_code: int, duration_ms: float) -> None:
    http_server_duration.record(
        duration_ms, {"http.request.method": method, "http.response.status_code": status_code}
    )


def record_run_outcome(kind: str, status: str) -> None:
    runs_total.add(1, {"run.kind": kind, "run.status": status})


def record_llm_tokens(model: str, input_tokens: int, output_tokens: int) -> None:
    llm_tokens_total.add(input_tokens, {"llm.model": model, "direction": "input"})
    llm_tokens_total.add(output_tokens, {"llm.model": model, "direction": "output"})
