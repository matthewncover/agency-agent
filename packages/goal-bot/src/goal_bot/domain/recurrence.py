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
  Rest/spacer labels are skipped when surfacing (you don't "do" rest) and the
  pointer only advances on `done` (spec §5 rotation redesign).
- **quota** — `{"per_window": N, "window": "week", "week_start": "monday"?}`.
  N sessions per rolling window; budgeted against days left in the window.
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


# --- rotation --------------------------------------------------------------


def rotation_current_index(
    sequence: list[str],
    stored_index: int | None,
    rest_labels: list[str] | None = None,
) -> int | None:
    """The index of the session to surface now: start at the stored pointer and
    skip forward over rest/spacer labels (rest auto-clears with a passing day).
    Returns None if the sequence is empty or all-rest."""
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


def rotation_next_index(stored_index: int | None, sequence_len: int) -> int:
    """Pointer advance on `done`: step one past the current slot (wrapping)."""
    if sequence_len <= 0:
        return 0
    return ((stored_index or 0) + 1) % sequence_len


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
