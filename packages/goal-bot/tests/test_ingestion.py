"""B2 — chapters, goal-setting candidates, re-ingest diffing, rollover.

Covers the deterministic ingestion machinery behind the MCP boundary: the
author → edit → re-ingest → rollover cycle, plus candidate-gathering and the
group-goal-in-private-chapter soft invariant (ADR-0013).
"""

from datetime import date

import pytest
from agency_profile.domain.entities import GroupProfile, Person
from agency_profile.infrastructure.adapters.profile_repo import (
    SqlAlchemyProfileRepository,
)
from goal_bot.application.ingestion import (
    AMBIGUOUS,
    ARCHIVED,
    UNCHANGED,
    VERSION_BUMP,
    IngestionUseCases,
)
from goal_bot.application.use_cases import GoalUseCases
from goal_bot.infrastructure.adapters.goal_repo import SqlAlchemyGoalRepository
from goal_bot.infrastructure.adapters.plan_repo import SqlAlchemyPlanRepository
from goal_bot.infrastructure.adapters.win_repo import SqlAlchemyWinRepository
from sqlalchemy import insert
from task_tracker.infrastructure import tables as tt
from task_tracker.infrastructure.task_query_client import PgTaskQueryClient

C1 = (date(2026, 6, 1), date(2026, 6, 30))
C2 = (date(2026, 7, 1), date(2026, 7, 31))

_DAILY_STEPS = dict(
    level="need",
    recurrence_type="daily",
    recurrence_config={},
    completion_type="quantity",
    quantity_unit="steps",
)


@pytest.fixture
def uc(migrated_engine):
    return GoalUseCases(
        goals=SqlAlchemyGoalRepository(migrated_engine),
        plans=SqlAlchemyPlanRepository(migrated_engine),
        wins=SqlAlchemyWinRepository(migrated_engine),
    )


@pytest.fixture
def iuc(migrated_engine):
    return IngestionUseCases(
        goals=SqlAlchemyGoalRepository(migrated_engine),
        profiles=SqlAlchemyProfileRepository(migrated_engine),
        tasks=PgTaskQueryClient(migrated_engine),
    )


def _version(definition, **over):
    return {"definition": definition, **_DAILY_STEPS, **over}


# ── rollover ────────────────────────────────────────────────────────────────
@pytest.mark.integration
def test_rollover_mints_fresh_goals_and_archives_prior(uc, iuc, person_id):
    c1 = uc.create_chapter(person_id, *C1, "Spring")
    g_keep = uc.create_goal(person_id, "step goal", chapter_id=c1)
    uc.create_goal_version(goal_id=g_keep, **_version("5k steps", target_quantity=5000))
    g_drop = uc.create_goal(person_id, "one-off errand", chapter_id=c1)
    uc.create_goal_version(
        goal_id=g_drop,
        level="need",
        definition="errand",
        recurrence_type="oneoff",
        recurrence_config={},
        completion_type="binary",
    )

    result = iuc.rollover(
        person_id,
        *C2,
        carried=[
            {
                "title": "step goal",
                "versions": [_version("6k steps", target_quantity=6000)],
            }
        ],
        label="Summer",
    )

    # New chapter, one fresh goal, distinct id, scoped to C2
    assert result["chapter_id"] != c1
    assert len(result["new_goal_ids"]) == 1
    new_gid = result["new_goal_ids"][0]
    assert new_gid not in {g_keep, g_drop}
    c2_goals = {g["id"] for g in uc.get_goals_for_chapter(result["chapter_id"])}
    assert new_gid in c2_goals

    # Both prior-chapter goals archived; no cross-chapter lineage exists
    assert set(result["archived_goal_ids"]) == {g_keep, g_drop}
    assert uc.get_goal_detail(g_keep)["goal"]["archived_at"] is not None
    new_detail = uc.get_goal_detail(new_gid)
    assert new_detail["goal"]["chapter_id"] == result["chapter_id"]


# ── re-ingest: bar change → new version, same id ──────────────────────────────
@pytest.mark.integration
def test_reingest_bar_change_is_version_bump(uc, iuc, person_id):
    c1 = uc.create_chapter(person_id, *C1, "Spring")
    gid = uc.create_goal(person_id, "step goal", chapter_id=c1)
    v1 = uc.create_goal_version(
        goal_id=gid, **_version("5k steps", target_quantity=5000)
    )

    diff = iuc.diff_chapter(
        c1,
        [
            {
                "gid": gid,
                "title": "step goal",
                "definition": "5k steps",
                "recurrence_type": "daily",
                "target_quantity": 8000,
            },
        ],
    )
    assert diff[0]["classification"] == VERSION_BUMP

    # Applying the bump: new version, same goal id, prior version closed
    uc.create_goal_versions(
        [
            {"goal_id": gid, **_version("5k steps", target_quantity=8000)},
        ]
    )
    versions = uc.get_goal_detail(gid)["versions"]
    assert len(versions) == 2
    prior = next(v for v in versions if v["id"] == v1)
    assert prior["effective_to"] is not None


# ── re-ingest: large content change → surfaced, never guessed ────────────────
@pytest.mark.integration
def test_reingest_large_change_is_ambiguous(uc, iuc, person_id):
    c1 = uc.create_chapter(person_id, *C1, "Spring")
    gid = uc.create_goal(person_id, "step goal", chapter_id=c1)
    uc.create_goal_version(
        goal_id=gid, **_version("walk 5k steps", target_quantity=5000)
    )

    diff = iuc.diff_chapter(
        c1,
        [
            {
                "gid": gid,
                "title": "step goal",
                "definition": "train for a marathon",
                "recurrence_type": "daily",
                "target_quantity": 5000,
            },
        ],
    )
    assert diff[0]["classification"] == AMBIGUOUS
    assert diff[0]["default"] == VERSION_BUMP  # default to version, never fork


@pytest.mark.integration
def test_reingest_unchanged_and_archived(uc, iuc, person_id):
    c1 = uc.create_chapter(person_id, *C1, "Spring")
    g_same = uc.create_goal(person_id, "step goal", chapter_id=c1)
    uc.create_goal_version(goal_id=g_same, **_version("5k steps", target_quantity=5000))
    g_gone = uc.create_goal(person_id, "dropped goal", chapter_id=c1)
    uc.create_goal_version(goal_id=g_gone, **_version("read", target_quantity=1))

    diff = iuc.diff_chapter(
        c1,
        [
            {
                "gid": g_same,
                "title": "step goal",
                "definition": "5k steps",
                "recurrence_type": "daily",
                "target_quantity": 5000,
            },
        ],
    )
    by_gid = {d["gid"]: d["classification"] for d in diff}
    assert by_gid[g_same] == UNCHANGED
    assert by_gid[g_gone] == ARCHIVED  # vanished from the markdown → auto-archive


# ── candidate-gathering ──────────────────────────────────────────────────────
@pytest.mark.integration
def test_propose_candidates_past_goals_and_personal_tasks(
    migrated_engine, uc, iuc, person_id
):
    uc.create_goal(person_id, "an old goal", chapter_id=None)

    with migrated_engine.begin() as c:
        c.execute(
            insert(tt.personal_tasks).values(
                owner_id=person_id,
                title="tier-2 personal",
                tier=2,
                status="not_started",
            )
        )
        c.execute(
            insert(tt.personal_tasks).values(
                owner_id=person_id,
                title="tier-4 personal",
                tier=4,
                status="not_started",
            )
        )
        c.execute(
            insert(tt.work_tasks).values(
                owner_id=person_id,
                title="work thing",
                status="not_started",
            )
        )

    result = iuc.propose_candidates(person_id)

    assert "an old goal" in {g["title"] for g in result["goals"]}
    task_titles = {t["title"] for t in result["tasks"]}
    assert "tier-2 personal" in task_titles
    assert "tier-4 personal" not in task_titles  # out of tier
    assert "work thing" not in task_titles  # work tasks are never candidates


# ── soft invariant (group goal in a private chapter) ─────────────────────────
@pytest.mark.integration
def test_group_goal_in_private_chapter_flags_confirm(migrated_engine, uc, iuc):
    profiles = SqlAlchemyProfileRepository(migrated_engine)
    person = profiles.create_person(Person(display_name="P", timezone="UTC"))
    group = profiles.create_group(GroupProfile(label="couple"), [person.profile_id])

    private_chapter = uc.create_chapter(person.profile_id, *C1, "Personal")
    shared_chapter = uc.create_chapter(group.profile_id, *C1, "Shared")

    # group-owned goal in the person's private chapter → confirm required
    flagged = iuc.check_goal_scope(group.profile_id, private_chapter)
    assert flagged["confirm_required"] is True
    assert flagged["reason"]

    # a personal goal in the person's own chapter → legitimate
    assert (
        iuc.check_goal_scope(person.profile_id, private_chapter)["confirm_required"]
        is False
    )
    # a personal goal in a shared chapter → also legitimate (never flagged)
    assert (
        iuc.check_goal_scope(person.profile_id, shared_chapter)["confirm_required"]
        is False
    )
