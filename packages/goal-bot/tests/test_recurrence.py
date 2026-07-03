"""Pure unit tests for the deterministic recurrence mechanics (no DB, no LLM)."""

from datetime import date, datetime

from goal_bot.domain.entities import RecurrenceType
from goal_bot.domain.recurrence import (
    QuotaStatus,
    accumulation_reached,
    fixed_schedule_is_due,
    interval_is_due,
    is_heavy_day,
    is_light_day,
    is_pointer_recurrence,
    quota_status,
    quota_window_bounds,
    rotation_current_index,
    rotation_current_label,
    rotation_next_index,
)


class TestRotation:
    SEQ = ["upper", "lower", "rest"]

    def test_current_item_at_pointer(self):
        assert rotation_current_label(self.SEQ, 0) == "upper"
        assert rotation_current_label(self.SEQ, 1) == "lower"

    def test_rest_is_skipped_when_surfacing(self):
        # pointer sits on 'rest' → surface the next real session (wraps to upper)
        assert rotation_current_label(self.SEQ, 2, rest_labels=["rest"]) == "upper"

    def test_advance_on_done_steps_one(self):
        assert rotation_next_index(0, 3) == 1
        assert rotation_next_index(2, 3) == 0  # wraps

    def test_miss_holds_pointer(self):
        # no advance call on a miss → same item re-surfaces
        assert rotation_current_index(self.SEQ, 1) == 1

    def test_all_rest_returns_none(self):
        assert rotation_current_index(["rest"], 0, rest_labels=["rest"]) is None

    def test_empty_sequence(self):
        assert rotation_current_index([], 0) is None
        assert rotation_next_index(0, 0) == 0


class TestInterval:
    def test_never_completed_is_due(self):
        assert interval_is_due(None, 4, date(2026, 7, 3)) is True

    def test_not_yet_due(self):
        last = datetime(2026, 7, 1, 8, 0)
        assert interval_is_due(last, 4, date(2026, 7, 3)) is False  # 2 < 4

    def test_due_when_elapsed(self):
        last = datetime(2026, 6, 29, 8, 0)
        assert interval_is_due(last, 4, date(2026, 7, 3)) is True  # 4 >= 4


class TestQuota:
    def test_window_bounds_monday_start(self):
        # 2026-07-03 is a Friday; Monday-anchored window is 06-29 .. 07-05
        start, end = quota_window_bounds(date(2026, 7, 3))
        assert start == date(2026, 6, 29)
        assert end == date(2026, 7, 5)

    def test_met(self):
        # 3 of 3 done → satisfied
        assert quota_status(3, 3, date(2026, 7, 3), date(2026, 7, 5)) is QuotaStatus.MET

    def test_forced_when_sessions_ge_days(self):
        # 0 done, need 3, but only Fri/Sat/Sun left (3 days) → forced today
        assert (
            quota_status(0, 3, date(2026, 7, 3), date(2026, 7, 5)) is QuotaStatus.FORCED
        )

    def test_slack_when_room(self):
        # need 1 more, 3 days left → slack (offered, not forced)
        assert (
            quota_status(2, 3, date(2026, 7, 3), date(2026, 7, 5)) is QuotaStatus.SLACK
        )


class TestFixedSchedule:
    def test_weekdays(self):
        # 2026-07-03 is Friday (weekday 4)
        assert fixed_schedule_is_due({"weekdays": [0, 2, 4]}, date(2026, 7, 3)) is True
        assert fixed_schedule_is_due({"weekdays": [0, 2]}, date(2026, 7, 3)) is False

    def test_month_days(self):
        assert fixed_schedule_is_due({"month_days": [1, 3]}, date(2026, 7, 3)) is True
        assert fixed_schedule_is_due({"month_days": [1, 15]}, date(2026, 7, 3)) is False

    def test_empty_config_not_due(self):
        assert fixed_schedule_is_due({}, date(2026, 7, 3)) is False


class TestAccumulation:
    def test_reached(self):
        assert accumulation_reached(4.0, 4.0) is True
        assert accumulation_reached(5.0, 4.0) is True

    def test_not_reached(self):
        assert accumulation_reached(3.5, 4.0) is False

    def test_no_target(self):
        assert accumulation_reached(100.0, None) is False


class TestHeavyLightDay:
    def test_heavy_low_recovery(self):
        assert is_heavy_day(30, None) is True

    def test_heavy_short_sleep(self):
        assert is_heavy_day(None, 5.0) is True

    def test_not_heavy(self):
        assert is_heavy_day(70, 8.0) is False

    def test_no_signal_not_heavy(self):
        assert is_heavy_day(None, None) is False

    def test_light_day(self):
        assert is_light_day(75, 8.0) is True

    def test_not_light_low_recovery(self):
        assert is_light_day(50, 8.0) is False

    def test_not_light_short_sleep(self):
        assert is_light_day(75, 6.0) is False


class TestPointerPredicate:
    def test_pointer_types(self):
        assert is_pointer_recurrence(RecurrenceType.ROTATION) is True
        assert is_pointer_recurrence(RecurrenceType.INTERVAL) is True

    def test_non_pointer_types(self):
        for rt in (
            RecurrenceType.DAILY,
            RecurrenceType.QUOTA,
            RecurrenceType.FIXED_SCHEDULE,
            RecurrenceType.ACCUMULATION,
            RecurrenceType.ONEOFF,
        ):
            assert is_pointer_recurrence(rt) is False
