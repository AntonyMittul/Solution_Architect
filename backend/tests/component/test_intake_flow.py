"""End-to-end requirements intake against real Postgres with a scripted fake
LLM. The executor is driven directly to stand in for the worker (the API ->
Redis -> worker wiring is covered by the ping smoke test)."""

from collections.abc import AsyncIterator

import httpx

from aisa.intake.domain.schemas import AnalystTurn
from aisa.llm.domain.messages import LLMMessage, MessageRole
from aisa.llm.infrastructure.fake import FakeLLMProvider
from aisa.platform.app import create_app
from aisa.platform.container import Container
from tests.component.conftest import ContainerFactory

PASSWORD = "correct-horse-battery"


def _turn(*, ready: bool, questions: list[str]) -> str:
    return AnalystTurn(
        assistant_message="Here is what I captured so far.",
        requirements={
            "summary": "A food delivery app for one million users",
            "goals": ["Serve 1M users"],
            "actors": ["customer", "courier", "restaurant"],
            "functional_requirements": ["place order", "track delivery"],
            "non_functional_requirements": ["99.9% uptime"],
            "constraints": [],
            "assumptions": ["AWS target cloud"],
            "open_questions": questions,
        },
        clarifying_questions=[
            {"id": f"q{i}", "question": q, "why": "affects the design"}
            for i, q in enumerate(questions)
        ],
        ready_to_confirm=ready,
    ).model_dump_json()


def _user_turns(messages: list[LLMMessage]) -> int:
    return sum(1 for m in messages if m.role is MessageRole.USER)


def two_round_handler(system: str, messages: list[LLMMessage], model: type) -> str:
    # First user turn -> ask a question; after the user answers -> ready.
    if _user_turns(messages) <= 1:
        return _turn(ready=False, questions=["What is the expected peak scale?"])
    return _turn(ready=True, questions=[])


def always_questions_handler(system: str, messages: list[LLMMessage], model: type) -> str:
    return _turn(ready=False, questions=["One more thing?"])


async def _client_for(container: Container) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app(container))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _register_verified_owner(client: httpx.AsyncClient, email: str) -> str:
    reg = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD, "name": "Owner"}
    )
    assert reg.status_code == 201, reg.text
    token = reg.json()["verification_token"]
    assert (await client.post("/api/v1/auth/verify", json={"token": token})).status_code == 200
    assert (
        await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    ).status_code == 200
    return reg.json()["workspace_id"]


async def test_full_intake_conversation(container_factory: ContainerFactory) -> None:
    container = container_factory(FakeLLMProvider(handler=two_round_handler))
    intake_executor = container.run_executors["intake"]

    async for client in _client_for(container):
        ws = await _register_verified_owner(client, "dan@example.com")
        project = await client.post(
            f"/api/v1/workspaces/{ws}/projects",
            json={"name": "Food app", "settings": {"target_cloud": "aws"}},
        )
        pid = project.json()["id"]

        # Round 1: post the idea, run pauses for a clarifying question.
        posted = await client.post(
            f"/api/v1/workspaces/{ws}/projects/{pid}/messages",
            json={"text": "Build a food delivery app for one million users"},
        )
        assert posted.status_code == 201, posted.text
        run_id = posted.json()["run_id"]
        assert posted.json()["resumed"] is False

        await intake_executor.execute(run_id)  # stand in for the worker

        run = await client.get(f"/api/v1/runs/{run_id}")
        assert run.json()["status"] == "needs_input"

        messages = await client.get(f"/api/v1/workspaces/{ws}/projects/{pid}/messages")
        assert [m["role"] for m in messages.json()] == ["user", "assistant"]
        assert messages.json()[1]["content"]["questions"]

        reqs = await client.get(f"/api/v1/workspaces/{ws}/projects/{pid}/requirements")
        assert reqs.status_code == 200
        assert reqs.json()["version"] == 1
        assert reqs.json()["status"] == "draft"
        assert "food delivery" in reqs.json()["content"]["summary"].lower()

        # Round 2: answer -> same run resumes and completes.
        answered = await client.post(
            f"/api/v1/workspaces/{ws}/projects/{pid}/messages",
            json={"text": "Peak is one million daily users; AWS; launch in 3 months"},
        )
        assert answered.json()["resumed"] is True
        assert answered.json()["run_id"] == run_id

        await intake_executor.execute(run_id)

        assert (await client.get(f"/api/v1/runs/{run_id}")).json()["status"] == "completed"
        reqs2 = await client.get(f"/api/v1/workspaces/{ws}/projects/{pid}/requirements")
        assert reqs2.json()["version"] == 2

        confirmed = await client.post(
            f"/api/v1/workspaces/{ws}/projects/{pid}/requirements/confirm"
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["status"] == "confirmed"


async def test_round_cap_forces_completion(container_factory: ContainerFactory) -> None:
    container = container_factory(FakeLLMProvider(handler=always_questions_handler))
    intake_executor = container.run_executors["intake"]

    async for client in _client_for(container):
        ws = await _register_verified_owner(client, "dan@example.com")
        pid = (await client.post(f"/api/v1/workspaces/{ws}/projects", json={"name": "P"})).json()[
            "id"
        ]
        messages_url = f"/api/v1/workspaces/{ws}/projects/{pid}/messages"

        posted = await client.post(messages_url, json={"text": "Build something"})
        run_id = posted.json()["run_id"]
        await intake_executor.execute(run_id)  # round 1 -> needs_input
        assert (await client.get(f"/api/v1/runs/{run_id}")).json()["status"] == "needs_input"

        await client.post(messages_url, json={"text": "answer 1"})
        await intake_executor.execute(run_id)  # round 2 -> needs_input
        assert (await client.get(f"/api/v1/runs/{run_id}")).json()["status"] == "needs_input"

        await client.post(messages_url, json={"text": "answer 2"})
        await intake_executor.execute(run_id)  # round 3 == cap -> completes despite questions
        assert (await client.get(f"/api/v1/runs/{run_id}")).json()["status"] == "completed"


async def test_unverified_member_cannot_start_intake(container_factory: ContainerFactory) -> None:
    container = container_factory(FakeLLMProvider(handler=two_round_handler))
    async for client in _client_for(container):
        # Owner sets up a team workspace + project.
        await _register_verified_owner(client, "owner@example.com")
        ws = (await client.post("/api/v1/workspaces", json={"name": "Acme"})).json()["id"]
        pid = (await client.post(f"/api/v1/workspaces/{ws}/projects", json={"name": "P"})).json()[
            "id"
        ]

        # An unverified member is invited and logs in.
        member = httpx.AsyncClient(transport=client._transport, base_url="http://test")
        async with member:
            await member.post(
                "/api/v1/auth/register",
                json={"email": "sam@example.com", "password": PASSWORD, "name": "Sam"},
            )
            await client.post(
                f"/api/v1/workspaces/{ws}/members",
                json={"email": "sam@example.com", "role": "member"},
            )
            await member.post(
                "/api/v1/auth/login", json={"email": "sam@example.com", "password": PASSWORD}
            )
            blocked = await member.post(
                f"/api/v1/workspaces/{ws}/projects/{pid}/messages", json={"text": "hi"}
            )
            assert blocked.status_code == 403
