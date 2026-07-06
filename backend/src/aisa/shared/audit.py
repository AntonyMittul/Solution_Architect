from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class AuditEntry:
    actor: str  # 'user:<id>' | 'system'
    action: str  # e.g. 'auth.login', 'project.deleted'
    workspace_id: str | None = None
    target: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


class AuditLogger(Protocol):
    async def record(self, entry: AuditEntry) -> None: ...
