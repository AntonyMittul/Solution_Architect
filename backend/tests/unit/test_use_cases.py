import pytest

from aisa.orchestration.application.use_cases import CreateRun, ExecutePingRun
from aisa.orchestration.domain.run import RunStatus
from aisa.shared.clock import SystemClock
from aisa.shared.errors import UnsupportedOperationError
from tests.fakes import InMemoryRunEvents, InMemoryRunRepository, RecordingJobQueue


def fixed_id() -> str:
    return "01TEST0000000000000000TEST"


async def test_create_run_persists_and_enqueues() -> None:
    repo = InMemoryRunRepository()
    queue = RecordingJobQueue()
    use_case = CreateRun(repo, queue, SystemClock(), fixed_id)

    run = await use_case.execute(kind="ping")

    assert run.status is RunStatus.QUEUED
    stored = await repo.get(run.id)
    assert stored.status is RunStatus.QUEUED
    assert queue.jobs == [("run.execute", {"run_id": run.id})]


async def test_create_run_rejects_unknown_kind() -> None:
    use_case = CreateRun(InMemoryRunRepository(), RecordingJobQueue(), SystemClock(), fixed_id)
    with pytest.raises(UnsupportedOperationError):
        await use_case.execute(kind="teleport")


async def test_execute_ping_run_emits_ordered_events_and_completes() -> None:
    repo = InMemoryRunRepository()
    events = InMemoryRunEvents()
    clock = SystemClock()
    created = await CreateRun(repo, RecordingJobQueue(), clock, fixed_id).execute(kind="ping")

    await ExecutePingRun(repo, events, clock).execute(created.id)

    final = await repo.get(created.id)
    assert final.status is RunStatus.COMPLETED
    collected = [e async for e in events.stream(created.id, after_seq=0) if e is not None]
    assert [e.seq for e in collected] == list(range(1, len(collected) + 1))
    assert collected[0].type == "run.status"
    assert collected[-1].type == "run.completed"
    assert sum(1 for e in collected if e.type == "agent.token") == 3


async def test_execute_ping_run_is_idempotent_on_redelivery() -> None:
    repo = InMemoryRunRepository()
    events = InMemoryRunEvents()
    clock = SystemClock()
    created = await CreateRun(repo, RecordingJobQueue(), clock, fixed_id).execute(kind="ping")
    executor = ExecutePingRun(repo, events, clock)

    await executor.execute(created.id)
    first_count = len([e async for e in events.stream(created.id, after_seq=0)])
    await executor.execute(created.id)  # simulated redelivery
    second_count = len([e async for e in events.stream(created.id, after_seq=0)])

    assert first_count == second_count  # no duplicate events
