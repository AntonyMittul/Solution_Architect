"""Test-only container builders."""

from typing import Any, cast

from aisa.orchestration.application.use_cases import CreateRun, ExecutePingRun, GetRun
from aisa.platform.container import Container
from aisa.shared.clock import Clock
from aisa.shared.config import Settings
from aisa.shared.ids import new_id
from tests.fakes import InlineJobQueue, InMemoryRunEvents, InMemoryRunRepository


def make_walking_skeleton_container(clock: Clock) -> Container:
    """Container with in-memory orchestration adapters; identity/projects
    fields are unused by walking-skeleton tests and left unwired."""
    repo = InMemoryRunRepository()
    events = InMemoryRunEvents()
    queue = InlineJobQueue()
    executor = ExecutePingRun(repo, events, clock)

    async def handle(payload: dict[str, str]) -> None:
        await executor.execute(payload["run_id"])

    queue.handlers["run.execute"] = handle
    unwired = cast(Any, None)
    return Container(
        settings=Settings(),
        engine=None,
        redis=None,
        clock=clock,
        run_repository=repo,
        job_queue=queue,
        run_event_sink=events,
        run_event_stream=events,
        create_run=CreateRun(repo, queue, clock, new_id),
        get_run=GetRun(repo),
        execute_ping_run=executor,
        access_codec=unwired,
        token_service=unwired,
        register_user=unwired,
        verify_email=unwired,
        login_user=unwired,
        get_current_user=unwired,
        resolve_actor=unwired,
        list_my_workspaces=unwired,
        create_workspace=unwired,
        list_members=unwired,
        invite_member=unwired,
        change_member_role=unwired,
        remove_member=unwired,
        create_project=unwired,
        list_projects=unwired,
        get_project=unwired,
        update_project=unwired,
        delete_project=unwired,
        restore_project=unwired,
        audit=unwired,
    )
