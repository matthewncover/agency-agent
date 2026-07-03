from datetime import date

import pytest
from goal_bot.application.use_cases import GoalUseCases
from goal_bot.domain.entities import (
    CompletionType,
    DailyPlanItem,
    Level,
    RecurrenceType,
)
from goal_bot.infrastructure.adapters.goal_repo import SqlAlchemyGoalRepository
from goal_bot.infrastructure.adapters.plan_repo import SqlAlchemyPlanRepository
from goal_bot.infrastructure.adapters.win_repo import SqlAlchemyWinRepository

TODAY = date(2026, 6, 27)

_VERSION_KW = dict(
    version_no=1,
    level=Level.NEED,
    definition="run 5k",
    recurrence_type=RecurrenceType.DAILY,
    recurrence_config={},
    completion_type=CompletionType.BINARY,
)


@pytest.fixture
def uc(migrated_engine):
    return GoalUseCases(
        goals=SqlAlchemyGoalRepository(migrated_engine),
        plans=SqlAlchemyPlanRepository(migrated_engine),
        wins=SqlAlchemyWinRepository(migrated_engine),
    )


@pytest.mark.integration
def test_create_goals_batch(uc, person_id):
    ch_id = uc.create_chapter(person_id, date(2026, 1, 1), date(2026, 12, 31), "Q1")
    result = uc.create_goals(
        person_id,
        [
            {
                "title": "step goal",
                "chapter_id": ch_id,
                "versions": [
                    {
                        "level": "need",
                        "definition": "5k",
                        "target_quantity": 5000,
                        "quantity_unit": "steps",
                        "recurrence_type": "daily",
                        "recurrence_config": {},
                        "completion_type": "quantity",
                        "why": "mood",
                        "obstacles": ["waking late", "gassed"],
                    },
                    {
                        "level": "want",
                        "definition": "7k",
                        "target_quantity": 7000,
                        "quantity_unit": "steps",
                        "recurrence_type": "daily",
                        "recurrence_config": {},
                        "completion_type": "quantity",
                        "why": "mood",
                    },
                ],
            },
            {  # a chapter-less one-off, defaults handled by caller
                "title": "renew passport",
                "chapter_id": None,
                "versions": [
                    {
                        "level": "need",
                        "definition": "renew passport",
                        "recurrence_type": "oneoff",
                        "recurrence_config": {},
                        "completion_type": "binary",
                        "why": "close loops",
                    }
                ],
            },
        ],
    )

    assert [r["title"] for r in result] == ["step goal", "renew passport"]
    steps = result[0]
    assert {v["level"] for v in steps["versions"]} == {"need", "want"}
    assert all(v["version_no"] == 1 for v in steps["versions"])

    # obstacles persisted on the need version
    detail = uc.get_goal_detail(steps["gid"])
    need = next(v for v in detail["versions"] if v["level"] == "need")
    assert need["obstacles"] == ["waking late", "gassed"]


@pytest.mark.integration
def test_create_goal_versions_batch_bumps_existing(uc, person_id):
    g1 = uc.create_goal(person_id, "a", chapter_id=None)
    g2 = uc.create_goal(person_id, "b", chapter_id=None)
    base = dict(
        recurrence_type="daily",
        recurrence_config={},
        completion_type="binary",
    )
    uc.create_goal_version(goal_id=g1, level="need", definition="v1", **base)
    ids = uc.create_goal_versions(
        [
            {"goal_id": g1, "level": "need", "definition": "v2", **base},
            {"goal_id": g2, "level": "need", "definition": "v1", **base},
        ]
    )
    assert len(ids) == 2
    d1 = uc.get_goal_detail(g1)
    need = sorted(d1["versions"], key=lambda v: v["version_no"])
    assert [v["version_no"] for v in need] == [1, 2]  # server bumped g1's need


@pytest.mark.integration
def test_authoring_round_trip(uc, person_id):
    ch_id = uc.create_chapter(person_id, date(2026, 1, 1), date(2026, 12, 31), "Q1")
    gid = uc.create_goal(person_id, "run", chapter_id=ch_id)
    uc.create_goal_version(goal_id=gid, **_VERSION_KW)

    goals = uc.get_full_goal_list(person_id, TODAY)
    assert any(g["id"] == gid for g in goals)

    detail = uc.get_goal_detail(gid)
    assert detail["goal"]["id"] == gid
    assert len(detail["versions"]) == 1


@pytest.mark.integration
def test_update_goal_identity_ok(uc, person_id):
    gid = uc.create_goal(person_id, "old title", chapter_id=None)
    result = uc.update_goal(gid, {"title": "new title"})
    assert result["title"] == "new title"


@pytest.mark.integration
def test_update_goal_content_fields_rejected(uc, person_id):
    gid = uc.create_goal(person_id, "run", chapter_id=None)
    with pytest.raises(ValueError, match="rejected"):
        uc.update_goal(gid, {"definition": "faster"})


def test_update_goal_tags_rejected_not_yet_writable(uc, person_id):
    gid = uc.create_goal(person_id, "run", chapter_id=None)
    with pytest.raises(ValueError, match="rejected"):
        uc.update_goal(gid, {"tags": ["movement"]})


@pytest.mark.integration
def test_log_outcome_done(uc, person_id):
    gid = uc.create_goal(person_id, "run", chapter_id=None)
    vid = uc.create_goal_version(goal_id=gid, **_VERSION_KW)
    plan = uc.plans.get_or_create_plan(person_id, TODAY)
    item = uc.plans.add_plan_item(
        DailyPlanItem(daily_plan_id=plan.id, goal_id=gid, goal_version_id=vid)
    )
    result = uc.log_outcome(item.id, "done")
    assert result["status"] == "done"


@pytest.mark.integration
def test_log_outcome_rejects_planned(uc, person_id):
    gid = uc.create_goal(person_id, "run", chapter_id=None)
    vid = uc.create_goal_version(goal_id=gid, **_VERSION_KW)
    plan = uc.plans.get_or_create_plan(person_id, TODAY)
    item = uc.plans.add_plan_item(
        DailyPlanItem(daily_plan_id=plan.id, goal_id=gid, goal_version_id=vid)
    )
    with pytest.raises(ValueError, match="done|partial|not_done"):
        uc.log_outcome(item.id, "planned")


@pytest.mark.integration
def test_log_outcome_rejects_carried_over(uc, person_id):
    gid = uc.create_goal(person_id, "run", chapter_id=None)
    vid = uc.create_goal_version(goal_id=gid, **_VERSION_KW)
    plan = uc.plans.get_or_create_plan(person_id, TODAY)
    item = uc.plans.add_plan_item(
        DailyPlanItem(daily_plan_id=plan.id, goal_id=gid, goal_version_id=vid)
    )
    with pytest.raises(ValueError, match="done|partial|not_done"):
        uc.log_outcome(item.id, "carried_over")


@pytest.mark.integration
def test_lock_in_plan(uc, person_id):
    plan = uc.plans.get_or_create_plan(person_id, TODAY)
    result = uc.lock_in_plan(plan.id, explicit=True)
    assert result["locked_in_at"] is not None
    assert result["lock_was_explicit"] is True


@pytest.mark.integration
def test_add_win_persists(uc, person_id):
    result = uc.add_win(person_id, "hit a PR")
    assert result["text"] == "hit a PR"
    wins = uc.wins.list_wins(person_id)
    assert any(w.text == "hit a PR" for w in wins)
