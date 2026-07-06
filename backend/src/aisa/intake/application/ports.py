from datetime import datetime
from typing import Protocol

from aisa.intake.domain.models import Message, RequirementDoc, Thread, ThreadRole


class ThreadRepository(Protocol):
    async def ensure_for_project(self, workspace_id: str, project_id: str) -> Thread: ...

    async def get_for_project(self, workspace_id: str, project_id: str) -> Thread | None: ...


class MessageRepository(Protocol):
    async def append(
        self,
        workspace_id: str,
        thread_id: str,
        *,
        role: ThreadRole,
        content: dict[str, object],
        run_id: str | None,
        now: datetime,
    ) -> Message: ...

    async def list_for_thread(self, workspace_id: str, thread_id: str) -> list[Message]: ...


class RequirementRepository(Protocol):
    async def append_version(
        self,
        workspace_id: str,
        project_id: str,
        *,
        content: dict[str, object],
        created_by: str,
        now: datetime,
    ) -> RequirementDoc: ...

    async def latest(self, workspace_id: str, project_id: str) -> RequirementDoc | None: ...

    async def confirm_latest(self, workspace_id: str, project_id: str) -> RequirementDoc: ...
