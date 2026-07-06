from datetime import UTC, datetime

import pytest

from aisa.orchestration.domain.run import Run, RunStatus
from aisa.shared.errors import InvalidStateError

NOW = datetime(2026, 7, 6, tzinfo=UTC)


def make_run() -> Run:
    return Run.create(run_id="01TEST0000000000000000TEST", kind="ping", now=NOW)


def test_created_run_is_queued() -> None:
    run = make_run()
    assert run.status is RunStatus.QUEUED
    assert not run.is_terminal


def test_happy_path_queued_running_completed() -> None:
    run = make_run()
    run.start(NOW)
    assert run.status is RunStatus.RUNNING
    assert run.started_at == NOW
    run.complete(NOW)
    assert run.status is RunStatus.COMPLETED
    assert run.finished_at == NOW
    assert run.is_terminal


def test_running_run_can_fail_with_error() -> None:
    run = make_run()
    run.start(NOW)
    run.fail(NOW, error="boom")
    assert run.status is RunStatus.FAILED
    assert run.error == "boom"
    assert run.is_terminal


def test_queued_run_can_be_cancelled_but_not_completed() -> None:
    run = make_run()
    with pytest.raises(InvalidStateError):
        run.complete(NOW)
    run.cancel(NOW)
    assert run.status is RunStatus.CANCELLED


@pytest.mark.parametrize("terminal", ["complete", "fail", "cancel"])
def test_terminal_states_reject_all_transitions(terminal: str) -> None:
    run = make_run()
    run.start(NOW)
    if terminal == "complete":
        run.complete(NOW)
    elif terminal == "fail":
        run.fail(NOW, "x")
    else:
        run.cancel(NOW)

    with pytest.raises(InvalidStateError):
        run.start(NOW)
    with pytest.raises(InvalidStateError):
        run.complete(NOW)
