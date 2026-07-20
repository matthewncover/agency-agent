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
    rotation_days_elapsed,
    rotation_due_index,
    rotation_group_due_goal_id,
    rotation_group_due_index,
    rotation_group_index_of_goal,
    rotation_group_member_ids,
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


class TestRotationDueIndex:
    """The date-aware walk (ADR-0016): each consecutive rest slot consumes one
    elapsed calendar day; a rest day surfaces nothing."""

    SEQ = ["push", "rest", "pull", "rest"]
    REST = ["rest"]

    def test_never_completed_is_due_now(self):
        assert rotation_due_index(self.SEQ, 0, self.REST, None) == 0
        # never-completed with the pointer on rest → next session, rests free
        assert rotation_due_index(self.SEQ, 1, self.REST, None) == 2

    def test_rest_consumes_a_day(self):
        # push done yesterday, pointer on rest: today IS the rest day (bug 1
        # regression — the old walk skipped rest instantly and offered pull)
        assert rotation_due_index(self.SEQ, 1, self.REST, 1) is None

    def test_session_after_rest_is_due(self):
        assert rotation_due_index(self.SEQ, 1, self.REST, 2) == 2

    def test_miss_holds_the_session(self):
        # pull not done → it stays due as days pass; nothing skips ahead
        assert rotation_due_index(self.SEQ, 1, self.REST, 5) == 2

    def test_same_day_as_completion_not_due(self):
        # pointer on a session, zero days elapsed → tomorrow, not twice today
        assert rotation_due_index(self.SEQ, 0, self.REST, 0) is None

    def test_no_rest_alternates_daily(self):
        assert rotation_due_index(["a", "b"], 1, None, 1) == 1

    def test_all_rest_and_empty(self):
        assert rotation_due_index(["rest"], 0, self.REST, 3) is None
        assert rotation_due_index([], 0, None, 3) is None

    def test_days_elapsed(self):
        assert rotation_days_elapsed(None, date(2026, 7, 3)) is None
        assert rotation_days_elapsed(datetime(2026, 7, 3, 18, 0), date(2026, 7, 5)) == 2


class TestRotationGroupWalk:
    """Same walk over member-goal entries (ADR-0016): exactly one member can be
    due per day, so same-day collisions are structurally impossible."""

    SEQ = [{"goal_id": 11}, {"rest": True}, {"goal_id": 22}, {"rest": True}]

    def test_member_ids(self):
        assert rotation_group_member_ids(self.SEQ) == [11, 22]

    def test_never_completed_first_member_due(self):
        assert rotation_group_due_goal_id(self.SEQ, 0, None) == 11

    def test_push_done_yesterday_today_is_rest(self):
        assert rotation_group_due_index(self.SEQ, 1, 1) is None

    def test_pull_due_after_the_rest_day(self):
        assert rotation_group_due_goal_id(self.SEQ, 1, 2) == 22

    def test_miss_shifts_everything_downstream(self):
        # pull missed for days → still pull; the next push waits behind it
        assert rotation_group_due_goal_id(self.SEQ, 1, 6) == 22

    def test_inactive_member_skipped_for_free(self):
        # goal 11 archived: its slot costs nothing, walk continues to 22
        assert rotation_group_due_goal_id(self.SEQ, 0, 2, active_goal_ids={22}) == 22

    def test_index_of_goal_from_pointer(self):
        assert rotation_group_index_of_goal(self.SEQ, 1, 22) == 2
        assert rotation_group_index_of_goal(self.SEQ, 1, 11) == 0  # wraps
        assert rotation_group_index_of_goal(self.SEQ, 1, 99) is None


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


class TestOneoffIsDue:
    def test_no_target_never_auto_surfaces(self):
        from goal_bot.domain.recurrence import oneoff_is_due

        assert oneoff_is_due({}, date(2026, 7, 19)) is False

    def test_near_target_is_due(self):
        from goal_bot.domain.recurrence import oneoff_is_due

        assert oneoff_is_due({"target": "2026-07-25"}, date(2026, 7, 19)) is True

    def test_far_target_not_due(self):
        from goal_bot.domain.recurrence import oneoff_is_due

        assert oneoff_is_due({"target": "2026-08-15"}, date(2026, 7, 19)) is False

    def test_overdue_target_stays_due(self):
        from goal_bot.domain.recurrence import oneoff_is_due

        assert oneoff_is_due({"target": "2026-07-01"}, date(2026, 7, 19)) is True


class TestQuotaPerWindow:
    def test_canonical_key(self):
        from goal_bot.domain.recurrence import quota_per_window

        assert quota_per_window({"per_window": 3}) == 3

    def test_count_alias(self):
        # The first prod ingestion (2026-07) wrote `count`; it must be honored.
        from goal_bot.domain.recurrence import quota_per_window

        assert quota_per_window({"count": 2, "window": "week"}) == 2

    def test_canonical_wins_over_alias(self):
        from goal_bot.domain.recurrence import quota_per_window

        assert quota_per_window({"per_window": 3, "count": 2}) == 3

    def test_default(self):
        from goal_bot.domain.recurrence import quota_per_window

        assert quota_per_window({}) == 1
