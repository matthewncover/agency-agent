"""The shared task surface (ADR-0018): private personal tasks are invisible —
indistinguishable from nonexistent — on every read path of the
include_private=False adapter, and create_shared_app grants only the curated
read-only tool set."""

from datetime import date

import pytest

from task_tracker.domain.entities import PersonalTaskEntity
from task_tracker.infrastructure.adapters import PgTaskRepositoryAdapter
from task_tracker.server import SHARED_TOOLS, create_shared_app


@pytest.fixture
def shared_repo(migrated_engine, person_id):
    return PgTaskRepositoryAdapter(migrated_engine, person_id, include_private=False)


@pytest.fixture
def secret_task(task_repo):
    return task_repo.create_personal_task(
        PersonalTaskEntity(title="Secret gift", tier=2, private=True)
    )


class TestPrivateFilteringAdapter:
    def test_get_personal_task_hides_private(self, shared_repo, secret_task):
        assert shared_repo.get_personal_task(secret_task.id) is None

    def test_full_adapter_still_sees_private(self, task_repo, secret_task):
        task = task_repo.get_personal_task(secret_task.id)
        assert task is not None
        assert task.private is True

    def test_open_tasks_hide_private(self, task_repo, shared_repo, secret_task):
        task_repo.create_personal_task(PersonalTaskEntity(title="Public", tier=2))
        titles = [t.title for t in shared_repo.get_open_personal_tasks()]
        assert titles == ["Public"]

    def test_private_child_hidden_under_public_parent(self, task_repo, shared_repo):
        parent = task_repo.create_personal_task(
            PersonalTaskEntity(title="Parent", tier=2)
        )
        task_repo.create_personal_task(
            PersonalTaskEntity(
                title="Secret sub", tier=2, private=True, parent_task_id=parent.id
            )
        )
        loaded = shared_repo.get_personal_task(parent.id)
        assert loaded is not None
        assert loaded.children == []

    def test_search_hides_private(self, task_repo, shared_repo, secret_task):
        task_repo.create_personal_task(
            PersonalTaskEntity(title="Public gift list", tier=2)
        )
        titles = [r["title"] for r in shared_repo.search_tasks("gift")]
        assert titles == ["Public gift list"]

    def test_updated_on_hides_private(self, shared_repo, secret_task):
        result = shared_repo.get_tasks_updated_on(date.today())
        assert result["personal"] == []


class TestCreateSharedApp:
    def test_grants_only_curated_read_tools(self, migrated_engine, person_id):
        _, tools = create_shared_app(migrated_engine, person_id)
        assert set(tools) == SHARED_TOOLS

    def test_shared_tools_hide_private(
        self, migrated_engine, person_id, task_repo, secret_task
    ):
        task_repo.create_personal_task(PersonalTaskEntity(title="Public", tier=2))
        _, tools = create_shared_app(migrated_engine, person_id)
        open_tasks = tools["get_open_tasks"](type="personal")
        titles = [t["title"] for t in open_tasks["personal"]]
        assert titles == ["Public"]
        assert tools["get_task_detail"](id=secret_task.id, type="personal") is None
