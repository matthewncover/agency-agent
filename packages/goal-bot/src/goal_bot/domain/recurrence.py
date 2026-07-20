"""Deterministic recurrence mechanics (mcp-tools §1 — "Python, never a tool").

Every function here is pure: it takes goal state + today and returns a
surfacing/budget/completion decision. No DB, no LLM. The morning assembler
gathers state via repos and calls these; the smart-subset heuristic (spec §3)
is built on top of them.

## recurrence_config schema (the deterministic-layer contract)

The ingestion layer (B2) authors `goal_version.recurrence_config` (JSONB). This
module is the single reader of that shape, so the conventions live here:

- **daily** — `{}`. Always due.
- **interval** — `{"every_days": N}`. Due when `today - last_completed_at ≥ N`
  days (measured from last completion; clock resets on `done`).
- **rotation** — `{"sequence": [label, ...], "rest_labels": [label, ...]?}`.
  A completion-advanced pointer (`goal_state.rotation_index`) into `sequence`.
  The pointer only advances on `done` (spec §5 rotation redesign), and each
  consecutive rest/spacer label consumes ONE elapsed calendar day since the
  last completion (ADR-0016) — a rest day surfaces nothing.

Rotation *groups* (ADR-0016) are not a recurrence type: they live in
`goalbot.rotation_group` and schedule cadence ACROSS member goals with the same
date-aware walk. A goal referenced by an active group is excluded from the
per-goal classification below; see the rotation-group section of this module.
- **quota** — `{"per_window": N, "window": "week", "week_start": "monday"?}`.
  N sessions per rolling window; budgeted against days left in the window.
  `count` is accepted as a legacy alias for `per_window` (the first prod
  ingestion wrote it, 2026-07); read via `quota_per_window`, author `per_window`.
- **oneoff** — `{"target": "YYYY-MM-DD"?}`. Surfaces only when the target date
  is near (within ONEOFF_NEAR_DAYS) or overdue (spec §3 bucket 3, OQ-10). No
  target → never auto-surfaces: reachable via the full list on request, and a
  carried-over one-off still surfaces via the assembler's carry-over rule.
- **fixed_schedule** — `{"weekdays": [0..6]}` (Mon=0) **or** `{"month_days": [1..31]}`.
  Surfaces only on its named days.
- **accumulation** — `{"unit": str?, "window": "chapter"}`; the target is the
  version's `target_quantity`. Sums logged progress toward that chapter total.

Thresholds for the heavy-/light-day trim (D-12/OQ-15) are Whoop-derived
defaults, overridable by callers.
"""

from datetime import date, datetime, timedelta
from enum import Enum, auto

from goal_bot.domain.entities import RecurrenceType

# --- heavy / light day thresholds (B1 daily signal, D-12 / OQ-15) ----------
# Whoop recovery zones: red < 34 (strained), green ≥ 67 (primed). Sleep in hrs.
HEAVY_RECOVERY_MAX = 34
HEAVY_SLEEP_MAX_HOURS = 6.0
LIGHT_RECOVERY_MIN = 67
LIGHT_SLEEP_MIN_HOURS = 7.5

_WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


class QuotaStatus(Enum):
    MET = auto()  # enough sessions already done this window → not due
    FORCED = auto()  # must happen today or the window breaks (due-by-budget)
    SLACK = auto()  # still has room → offered as a candidate, not forced


# --- rotation (spec §5 + ADR-0016: the date-aware pointer walk) -------------
#
# Two bugs the pre-ADR-0016 walk had, both fixed here:
#   1. Rest slots consumed zero calendar days (skipped instantly at surfacing),
#      so push done Friday offered pull on Saturday.
#   2. The pointer advanced from the STORED index, not the SURFACED one, so a
#      session reached by skipping rest surfaced twice in a row.
# The walk now takes days-elapsed-since-completion: each consecutive rest slot
# consumes one elapsed day, and callers advance from the surfaced index.


def rotation_days_elapsed(
    last_completed_at: datetime | None, today: date
) -> int | None:
    """Whole days since the pointer's last completion; None = never completed
    (the next session is due immediately, rest slots cost nothing)."""
    if last_completed_at is None:
        return None
    return (today - last_completed_at.date()).days


def _walk_due_index(
    n: int,
    stored_index: int | None,
    days_elapsed: int | None,
    is_rest,
    is_skipped=lambda idx: False,
) -> int | None:
    """The shared date-aware walk: from the stored pointer, skipped entries
    (e.g. inactive member goals) cost nothing, each consecutive rest slot
    consumes one elapsed calendar day, and the first real session is due iff
    enough days have passed (rests-crossed + 1). Returns the due index, or None
    while today is still inside the rest gap (or nothing is live)."""
    if n <= 0:
        return None
    start = (stored_index or 0) % n
    rests = 0
    for step in range(n):
        idx = (start + step) % n
        if is_skipped(idx):
            continue
        if is_rest(idx):
            rests += 1
            continue
        if days_elapsed is None:
            return idx  # never completed → due now
        return idx if days_elapsed >= rests + 1 else None
    return None  # every entry is rest/skipped — nothing to do


def rotation_due_index(
    sequence: list[str],
    stored_index: int | None,
    rest_labels: list[str] | None = None,
    days_elapsed: int | None = None,
) -> int | None:
    """The label-rotation session due today, or None on a rest day."""
    rest = set(rest_labels or [])
    return _walk_due_index(
        len(sequence), stored_index, days_elapsed, lambda i: sequence[i] in rest
    )


def rotation_current_index(
    sequence: list[str],
    stored_index: int | None,
    rest_labels: list[str] | None = None,
) -> int | None:
    """The next real session at/after the pointer, ignoring the calendar — the
    fallback for resolving which slot a `done` belongs to when the log lands on
    a rest day (did it early). Surfacing uses rotation_due_index instead."""
    if not sequence:
        return None
    rest = set(rest_labels or [])
    n = len(sequence)
    start = (stored_index or 0) % n
    for step in range(n):
        idx = (start + step) % n
        if sequence[idx] not in rest:
            return idx
    return None  # every entry is a rest label — nothing to do


def rotation_current_label(
    sequence: list[str],
    stored_index: int | None,
    rest_labels: list[str] | None = None,
) -> str | None:
    idx = rotation_current_index(sequence, stored_index, rest_labels)
    return sequence[idx] if idx is not None else None


def rotation_next_index(surfaced_index: int | None, sequence_len: int) -> int:
    """Pointer advance on `done`: one past the slot that was actually surfaced
    and completed — NEVER the raw stored pointer, which may sit on a rest slot
    behind the surfaced session (ADR-0016 bug 2)."""
    if sequence_len <= 0:
        return 0
    return ((surfaced_index or 0) + 1) % sequence_len


# --- rotation group (ADR-0016: cadence scheduled across member goals) --------
# `sequence` entries are {"goal_id": N} (member) or {"rest": true} (spacer).


def rotation_group_member_ids(sequence: list[dict]) -> list[int]:
    """Member goal ids in sequence order (rest slots excluded)."""
    return [e["goal_id"] for e in sequence if "goal_id" in e]


def rotation_group_due_index(
    sequence: list[dict],
    stored_index: int | None,
    days_elapsed: int | None,
    active_goal_ids: set[int] | None = None,
) -> int | None:
    """The sequence index of the member due today, or None on a rest day.
    Entries whose goal is not in `active_goal_ids` (archived/paused members)
    are skipped transparently and consume no days."""

    def is_rest(idx: int) -> bool:
        return "goal_id" not in sequence[idx]

    def is_skipped(idx: int) -> bool:
        gid = sequence[idx].get("goal_id")
        return (
            gid is not None
            and active_goal_ids is not None
            and gid not in active_goal_ids
        )

    return _walk_due_index(
        len(sequence), stored_index, days_elapsed, is_rest, is_skipped
    )


def rotation_group_due_goal_id(
    sequence: list[dict],
    stored_index: int | None,
    days_elapsed: int | None,
    active_goal_ids: set[int] | None = None,
) -> int | None:
    idx = rotation_group_due_index(
        sequence, stored_index, days_elapsed, active_goal_ids
    )
    return sequence[idx]["goal_id"] if idx is not None else None


def rotation_group_index_of_goal(
    sequence: list[dict], stored_index: int | None, goal_id: int
) -> int | None:
    """The first entry at/after the pointer referencing `goal_id` — resolves
    which slot a `done` belongs to when it lands off-schedule (did it early on
    a rest day). Completion advances from this index."""
    n = len(sequence)
    if n <= 0:
        return None
    start = (stored_index or 0) % n
    for step in range(n):
        idx = (start + step) % n
        if sequence[idx].get("goal_id") == goal_id:
            return idx
    return None


# --- interval --------------------------------------------------------------


def interval_is_due(
    last_completed_at: datetime | None, every_days: int, today: date
) -> bool:
    if last_completed_at is None:
        return True  # never completed → due now
    last_day = last_completed_at.date()
    return (today - last_day).days >= every_days


# --- quota -----------------------------------------------------------------


def quota_window_bounds(today: date, week_start: str = "monday") -> tuple[date, date]:
    """Inclusive [start, end] of the weekly window containing `today`."""
    start_idx = _WEEKDAY_INDEX.get(week_start.lower(), 0)
    offset = (today.weekday() - start_idx) % 7
    start = today - timedelta(days=offset)
    return start, start + timedelta(days=6)


def quota_status(
    done_in_window: int, per_window: int, today: date, window_end: date
) -> QuotaStatus:
    remaining_sessions = per_window - done_in_window
    if remaining_sessions <= 0:
        return QuotaStatus.MET
    remaining_days = (window_end - today).days + 1  # inclusive of today
    if remaining_sessions >= remaining_days:
        return QuotaStatus.FORCED
    return QuotaStatus.SLACK


def quota_per_window(config: dict) -> int:
    """Sessions required per window. Canonical key `per_window`; `count` is a
    legacy alias (see the module contract)."""
    return config.get("per_window", config.get("count", 1))


# --- oneoff ----------------------------------------------------------------

# "Near" horizon for a one-off's target date (spec §3 bucket 3): it enters the
# candidate subset this many days before target, and stays while overdue.
ONEOFF_NEAR_DAYS = 7


def oneoff_is_due(config: dict, today: date, near_days: int = ONEOFF_NEAR_DAYS) -> bool:
    """A one-off auto-surfaces only when its target date is near or overdue.
    No target → False: it stays reachable via the full list, and a carried-over
    one-off surfaces through the assembler's carry-over rule regardless."""
    target = config.get("target")
    if not target:
        return False
    t = target if isinstance(target, date) else date.fromisoformat(str(target))
    return today >= t - timedelta(days=near_days)


# --- fixed_schedule --------------------------------------------------------


def fixed_schedule_is_due(config: dict, today: date) -> bool:
    weekdays = config.get("weekdays")
    if weekdays:
        return today.weekday() in weekdays
    month_days = config.get("month_days")
    if month_days:
        return today.day in month_days
    return False


# --- accumulation ----------------------------------------------------------


def accumulation_reached(total: float, target: float | None) -> bool:
    if target is None:
        return False
    return total >= target


# --- heavy / light day (B1 daily signal) -----------------------------------


def is_heavy_day(
    recovery: int | None,
    sleep_hours: float | None,
    recovery_max: int = HEAVY_RECOVERY_MAX,
    sleep_max: float = HEAVY_SLEEP_MAX_HOURS,
) -> bool:
    """A physiologically demanding day: low recovery OR short sleep. Drives the
    proactive trim (D-12) — never drops a need, only caps suggested extras."""
    if recovery is not None and recovery < recovery_max:
        return True
    if sleep_hours is not None and sleep_hours < sleep_max:
        return True
    return False


def is_light_day(
    recovery: int | None,
    sleep_hours: float | None,
    recovery_min: int = LIGHT_RECOVERY_MIN,
    sleep_min: float = LIGHT_SLEEP_MIN_HOURS,
) -> bool:
    """A day with headroom: high recovery and (if known) good sleep. Gates the
    OQ-15 lighter-day nudge, which only ever offers non-needs."""
    if recovery is None:
        return False
    if recovery < recovery_min:
        return False
    if sleep_hours is not None and sleep_hours < sleep_min:
        return False
    return True


# --- surfacing predicate over any recurrence type --------------------------


def is_pointer_recurrence(recurrence: RecurrenceType) -> bool:
    """rotation/interval carry pointer state that backdating can't recompute
    (mcp-tools §3.1/§5) — used to gate backdated `log_outcome`."""
    return recurrence in (RecurrenceType.ROTATION, RecurrenceType.INTERVAL)
