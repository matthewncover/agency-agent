import pytest
from goal_bot.domain.entities import (
    CompletionType,
    GoalVersion,
    Level,
    PlanItemStatus,
    RecurrenceType,
    VersionLifecycle,
)


def test_level_enum_members():
    assert Level("need") == Level.NEED
    assert Level("want") == Level.WANT


def test_recurrence_type_all_members():
    for v in (
        "oneoff",
        "daily",
        "rotation",
        "quota",
        "interval",
        "fixed_schedule",
        "accumulation",
    ):
        assert RecurrenceType(v) is not None


def test_completion_type_members():
    assert CompletionType("binary") == CompletionType.BINARY
    assert CompletionType("quantity") == CompletionType.QUANTITY
    assert CompletionType("duration") == CompletionType.DURATION


def test_plan_item_status_members():
    for v in ("planned", "done", "partial", "not_done", "carried_over"):
        assert PlanItemStatus(v) is not None


def test_invalid_enum_raises():
    with pytest.raises(ValueError):
        Level("invalid")


def test_goal_version_accepts_dict_recurrence_config():
    gv = GoalVersion(
        goal_id=1,
        version_no=1,
        level=Level.NEED,
        definition="run 5k",
        recurrence_type=RecurrenceType.DAILY,
        recurrence_config={"days": ["mon", "wed", "fri"]},
        completion_type=CompletionType.BINARY,
        lifecycle=VersionLifecycle.ACTIVE,
    )
    assert isinstance(gv.recurrence_config, dict)
    assert gv.recurrence_config["days"] == ["mon", "wed", "fri"]
