from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from task_tracker.domain.entities import (
    DailyLogEntity,
    PersonalTaskEntity,
    PersonalTaskStatus,
    WorkTaskEntity,
)
from task_tracker.infrastructure.adapters import (
    PgDailyLogRepositoryAdapter,
    PgTaskRepositoryAdapter,
)


class TestGetPersonalCandidates:
    def test_returns_only_open_personal_tasks_in_tiers(
        self, task_repo, query_client, person_id
    ):
        task_repo.create_personal_task(PersonalTaskEntity(title="T2", tier=2))
        task_repo.create_personal_task(PersonalTaskEntity(title="T3", tier=3))
        task_repo.create_personal_task(PersonalTaskEntity(title="T1", tier=1))
        task_repo.create_personal_task(
            PersonalTaskEntity(title="Done T2", tier=2, status=PersonalTaskStatus.DONE)
        )

        candidates = query_client.get_personal_candidates(person_id)
        titles = {c.title for c in candidates}
        assert titles == {"T2", "T3"}  # tier 1 excluded, done excluded

    def test_excludes_work_tasks(self, task_repo, query_client, person_id):
        task_repo.create_work_task(WorkTaskEntity(title="Work thing"))
        task_repo.create_personal_task(PersonalTaskEntity(title="Personal", tier=2))
        candidates = query_client.get_personal_candidates(person_id)
        assert [c.title for c in candidates] == ["Personal"]

    def test_excludes_other_owners(
        self, migrated_engine, query_client, person_id, other_person_id
    ):
        PgTaskRepositoryAdapter(migrated_engine, person_id).create_personal_task(
            PersonalTaskEntity(title="Mine", tier=2)
        )
        PgTaskRepositoryAdapter(migrated_engine, other_person_id).create_personal_task(
            PersonalTaskEntity(title="Theirs", tier=2)
        )
        mine = query_client.get_personal_candidates(person_id)
        assert [c.title for c in mine] == ["Mine"]

    def test_custom_tiers(self, task_repo, query_client, person_id):
        task_repo.create_personal_task(PersonalTaskEntity(title="T1", tier=1))
        task_repo.create_personal_task(PersonalTaskEntity(title="T2", tier=2))
        candidates = query_client.get_personal_candidates(person_id, tiers=(1,))
        assert [c.title for c in candidates] == ["T1"]


class TestGetTaskStatus:
    def test_personal(self, task_repo, query_client, person_id):
        created = task_repo.create_personal_task(
            PersonalTaskEntity(title="Ref me", tier=2)
        )
        status = query_client.get_task_status("personal", created.id, person_id)
        assert status is not None
        assert status.source == "personal"
        assert status.title == "Ref me"
        assert status.is_deleted is False

    def test_work(self, task_repo, query_client, person_id):
        created = task_repo.create_work_task(WorkTaskEntity(title="Work ref"))
        status = query_client.get_task_status("work", created.id, person_id)
        assert status is not None
        assert status.source == "work"

    def test_missing_returns_none(self, query_client, person_id):
        assert query_client.get_task_status("personal", 99999, person_id) is None

    def test_other_owner_returns_none(
        self, task_repo, query_client, person_id, other_person_id
    ):
        created = task_repo.create_personal_task(
            PersonalTaskEntity(title="Mine", tier=2)
        )
        assert (
            query_client.get_task_status("personal", created.id, other_person_id)
            is None
        )

    def test_invalid_source_raises(self, query_client, person_id):
        with pytest.raises(ValueError):
            query_client.get_task_status("bogus", 1, person_id)


class TestGetDailySignal:
    def test_returns_whoop_and_sleep(self, migrated_engine, query_client, person_id):
        repo = PgDailyLogRepositoryAdapter(migrated_engine, person_id)
        repo.create_or_update(
            DailyLogEntity(
                date=date(2026, 3, 1),
                whoop_recovery=72,
                whoop_hrv=45,
                whoop_sleep_hours=7.5,
                whoop_rhr=52,
            )
        )
        signal = query_client.get_daily_signal(person_id, date(2026, 3, 1))
        assert signal is not None
        assert signal.whoop_recovery == 72
        assert signal.sleep_hours == 7.5
        assert signal.whoop_rhr == 52

    def test_unlogged_returns_none(self, query_client, person_id):
        assert query_client.get_daily_signal(person_id, date(2026, 3, 2)) is None


@pytest.mark.integration
class TestCrossSchemaFk:
    def test_personal_task_owner_must_exist(self, migrated_engine):
        bad = PgTaskRepositoryAdapter(migrated_engine, owner_id=987654321)
        with pytest.raises(IntegrityError):
            bad.create_personal_task(PersonalTaskEntity(title="Orphan", tier=2))
