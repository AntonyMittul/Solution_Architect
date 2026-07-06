from datetime import UTC, datetime

import pytest

from aisa.projects.domain.project import Project, ProjectStatus
from aisa.shared.errors import DomainValidationError, InvalidStateError

NOW = datetime(2026, 7, 6, tzinfo=UTC)


def make_project() -> Project:
    return Project.create(
        project_id="p1",
        workspace_id="w1",
        name="Food delivery app",
        description=None,
        settings={},
        created_by="u1",
        now=NOW,
    )


def test_create_requires_name() -> None:
    with pytest.raises(DomainValidationError):
        Project.create(
            project_id="p1",
            workspace_id="w1",
            name="   ",
            description=None,
            settings={},
            created_by="u1",
            now=NOW,
        )


def test_new_project_is_active_and_not_deleted() -> None:
    project = make_project()
    assert project.status is ProjectStatus.ACTIVE
    assert not project.is_deleted


def test_soft_delete_then_restore() -> None:
    project = make_project()
    project.soft_delete(NOW)
    assert project.is_deleted
    project.restore(NOW)
    assert not project.is_deleted


def test_double_delete_and_bad_restore_rejected() -> None:
    project = make_project()
    with pytest.raises(InvalidStateError):
        project.restore(NOW)  # not deleted yet
    project.soft_delete(NOW)
    with pytest.raises(InvalidStateError):
        project.soft_delete(NOW)
