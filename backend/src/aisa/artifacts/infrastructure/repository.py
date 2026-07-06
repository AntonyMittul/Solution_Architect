from sqlalchemy import delete, func, select

from aisa.artifacts.domain.models import Artifact, ArtifactType, ArtifactVersion
from aisa.artifacts.infrastructure.tables import (
    ArtifactDependencyRow,
    ArtifactRow,
    ArtifactVersionRow,
)
from aisa.shared.clock import Clock
from aisa.shared.db import SessionFactory, tenant_session
from aisa.shared.ids import new_id


class SqlArtifactRepository:
    def __init__(self, session_factory: SessionFactory, clock: Clock) -> None:
        self._session_factory = session_factory
        self._clock = clock

    async def ensure(self, workspace_id: str, project_id: str, type: ArtifactType) -> Artifact:
        async with tenant_session(self._session_factory, workspace_id) as session:
            row = await session.scalar(
                select(ArtifactRow).where(
                    ArtifactRow.project_id == project_id, ArtifactRow.type == type.value
                )
            )
            if row is None:
                row = ArtifactRow(
                    id=new_id(),
                    workspace_id=workspace_id,
                    project_id=project_id,
                    type=type.value,
                    is_stale=False,
                )
                session.add(row)
                await session.flush()
            return _artifact(row)

    async def append_version(
        self,
        workspace_id: str,
        artifact_id: str,
        *,
        content: dict[str, object],
        provenance: dict[str, object],
    ) -> ArtifactVersion:
        async with tenant_session(self._session_factory, workspace_id) as session:
            current_max = await session.scalar(
                select(func.max(ArtifactVersionRow.version)).where(
                    ArtifactVersionRow.artifact_id == artifact_id
                )
            )
            row = ArtifactVersionRow(
                id=new_id(),
                workspace_id=workspace_id,
                artifact_id=artifact_id,
                version=(current_max or 0) + 1,
                content=content,
                provenance=provenance,
                created_at=self._clock.now(),
            )
            session.add(row)
            # A freshly (re)generated artifact is no longer stale.
            artifact = await session.get(ArtifactRow, artifact_id)
            if artifact is not None:
                artifact.is_stale = False
            await session.flush()
            return _version(row)

    async def set_dependencies(
        self, workspace_id: str, artifact_id: str, depends_on_ids: list[str]
    ) -> None:
        async with tenant_session(self._session_factory, workspace_id) as session:
            await session.execute(
                delete(ArtifactDependencyRow).where(
                    ArtifactDependencyRow.artifact_id == artifact_id
                )
            )
            for dep in depends_on_ids:
                session.add(
                    ArtifactDependencyRow(
                        workspace_id=workspace_id, artifact_id=artifact_id, depends_on_id=dep
                    )
                )

    async def list_latest(
        self, workspace_id: str, project_id: str
    ) -> list[tuple[Artifact, ArtifactVersion | None]]:
        async with tenant_session(self._session_factory, workspace_id) as session:
            artifacts = list(
                await session.scalars(
                    select(ArtifactRow)
                    .where(ArtifactRow.project_id == project_id)
                    .order_by(ArtifactRow.type)
                )
            )
            result: list[tuple[Artifact, ArtifactVersion | None]] = []
            for row in artifacts:
                latest = await self._latest_version(session, row.id)
                result.append((_artifact(row), latest))
            return result

    async def get_latest(
        self, workspace_id: str, project_id: str, type: ArtifactType
    ) -> tuple[Artifact, ArtifactVersion | None] | None:
        async with tenant_session(self._session_factory, workspace_id) as session:
            row = await session.scalar(
                select(ArtifactRow).where(
                    ArtifactRow.project_id == project_id, ArtifactRow.type == type.value
                )
            )
            if row is None:
                return None
            return _artifact(row), await self._latest_version(session, row.id)

    async def list_versions(
        self, workspace_id: str, project_id: str, type: ArtifactType
    ) -> list[ArtifactVersion]:
        async with tenant_session(self._session_factory, workspace_id) as session:
            artifact = await session.scalar(
                select(ArtifactRow).where(
                    ArtifactRow.project_id == project_id, ArtifactRow.type == type.value
                )
            )
            if artifact is None:
                return []
            rows = await session.scalars(
                select(ArtifactVersionRow)
                .where(ArtifactVersionRow.artifact_id == artifact.id)
                .order_by(ArtifactVersionRow.version.desc())
            )
            return [_version(row) for row in rows]

    async def mark_stale(self, workspace_id: str, artifact_ids: list[str], stale: bool) -> None:
        if not artifact_ids:
            return
        async with tenant_session(self._session_factory, workspace_id) as session:
            for artifact_id in artifact_ids:
                artifact = await session.get(ArtifactRow, artifact_id)
                if artifact is not None:
                    artifact.is_stale = stale

    async def dependents_of(self, workspace_id: str, artifact_id: str) -> list[str]:
        async with tenant_session(self._session_factory, workspace_id) as session:
            rows = await session.scalars(
                select(ArtifactDependencyRow.artifact_id).where(
                    ArtifactDependencyRow.depends_on_id == artifact_id
                )
            )
            return list(rows)

    @staticmethod
    async def _latest_version(session, artifact_id: str) -> ArtifactVersion | None:  # type: ignore[no-untyped-def]
        row = await session.scalar(
            select(ArtifactVersionRow)
            .where(ArtifactVersionRow.artifact_id == artifact_id)
            .order_by(ArtifactVersionRow.version.desc())
            .limit(1)
        )
        return _version(row) if row is not None else None


def _artifact(row: ArtifactRow) -> Artifact:
    return Artifact(
        id=row.id,
        workspace_id=row.workspace_id,
        project_id=row.project_id,
        type=ArtifactType(row.type),
        is_stale=row.is_stale,
    )


def _version(row: ArtifactVersionRow) -> ArtifactVersion:
    return ArtifactVersion(
        id=row.id,
        workspace_id=row.workspace_id,
        artifact_id=row.artifact_id,
        version=row.version,
        content=dict(row.content),
        provenance=dict(row.provenance),
        created_at=row.created_at,
    )
