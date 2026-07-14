"""task_ref validation on version creation (ADR-0018): a ref must resolve via
the task query client, which answers None for private tasks — so refs to
private, foreign, or nonexistent tasks are all rejected identically."""

import pytest
from goal_bot.application.use_cases import GoalUseCases
from goal_bot.infrastructure.adapters.goal_repo import SqlAlchemyGoalRepository
from goal_bot.infrastructure.adapters.plan_repo import SqlAlchemyPlanRepository
from goal_bot.infrastructure.adapters.win_repo import SqlAlchemyWinRepository
from task_tracker.domain.entities import PersonalTaskEntity
from task_tracker.infrastructure.adapters import PgTaskRepositoryAdapter
from task_tracker.infrastructure.task_query_client import PgTaskQueryClient


@pytest.fixture
def uc(migrated_engine):
    return GoalUseCases(
        goals=SqlAlchemyGoalRepository(migrated_engine),
        plans=SqlAlchemyPlanRepository(migrated_engine),
        wins=SqlAlchemyWinRepository(migrated_engine),
        tasks=PgTaskQueryClient(migrated_engine),
    )


@pytest.fixture
def task_repo(migrated_engine, person_id):
    return PgTaskRepositoryAdapter(migrated_engine, person_id)


def _oneoff_version(task_id: int) -> dict:
    return {
        "level": "need",
        "definition": "do the thing",
        "recurrence_type": "oneoff",
        "recurrence_config": {},
        "completion_type": "binary",
        "task_ref_source": "personal",
        "task_ref_id": task_id,
    }


def _goal_spec(task_id: int) -> dict:
    return {"title": "errand", "versions": [_oneoff_version(task_id)]}


@pytest.mark.integration
class TestTaskRefValidation:
    def test_ref_to_public_task_accepted(self, uc, task_repo, person_id):
        task = task_repo.create_personal_task(
            PersonalTaskEntity(title="Errand", tier=2)
        )
        created = uc.create_goals(person_id, [_goal_spec(task.id)])
        assert len(created) == 1

    def test_ref_to_private_task_rejected(self, uc, task_repo, person_id):
        task = task_repo.create_personal_task(
            PersonalTaskEntity(title="Secret gift", tier=2, private=True)
        )
        with pytest.raises(ValueError, match="does not resolve"):
            uc.create_goals(person_id, [_goal_spec(task.id)])

    def test_ref_to_missing_task_rejected(self, uc, person_id):
        with pytest.raises(ValueError, match="does not resolve"):
            uc.create_goals(person_id, [_goal_spec(99999)])

    def test_create_goal_version_validates_via_goal_owner(
        self, uc, task_repo, person_id
    ):
        task = task_repo.create_personal_task(
            PersonalTaskEntity(title="Secret", tier=2, private=True)
        )
        gid = uc.create_goal(person_id, "errand", None)
        with pytest.raises(ValueError, match="does not resolve"):
            uc.create_goal_version(goal_id=gid, **_oneoff_version(task.id))

    def test_half_specified_ref_rejected(self, uc, person_id):
        spec = _goal_spec(1)
        spec["versions"][0].pop("task_ref_source")
        with pytest.raises(ValueError, match="requires both"):
            uc.create_goals(person_id, [spec])

    def test_no_client_skips_validation(self, migrated_engine, person_id):
        # Single-package setups without task-tracker wiring store refs as-is.
        uc = GoalUseCases(
            goals=SqlAlchemyGoalRepository(migrated_engine),
            plans=SqlAlchemyPlanRepository(migrated_engine),
            wins=SqlAlchemyWinRepository(migrated_engine),
        )
        created = uc.create_goals(person_id, [_goal_spec(99999)])
        assert len(created) == 1
