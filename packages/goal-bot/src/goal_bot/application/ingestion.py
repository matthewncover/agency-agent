"""Deterministic goal-setting / re-ingest machinery (B2).

Per mcp-tools §1 and goal-markdown §5, the *identity-bearing* decisions of
ingestion — which past goals/tasks to propose, whether an edit is a new version
or a new goal, how a chapter rolls over — are deterministic Python behind the
MCP boundary. The ingestion LLM is handed prepared lists and classifications; it
never re-identifies goals from content (the failure mode §5.1 exists to avoid).
"""

from dataclasses import dataclass
from datetime import date

from agency_profile.application.ports import ProfileRepositoryPort
from agency_profile.domain.entities import ProfileKind
from pydantic import BaseModel
from task_tracker.application.query_client import TaskQueryClient

from goal_bot.application.ports import GoalRepositoryPort
from goal_bot.domain.entities import GoalVersion, Level, VersionLifecycle


class ParsedGoal(BaseModel):
    """One goal as parsed from the authored markdown, reduced to the fields the
    diff classifies on. `gid` is the written-back id (None on first sight)."""

    gid: int | None = None
    title: str
    definition: str
    recurrence_type: str
    target_quantity: float | None = None


# Change-summary classifications (goal-markdown §5.6).
NEW = "new"
VERSION_BUMP = "version_bump"
UNCHANGED = "unchanged"
AMBIGUOUS = "ambiguous"  # version-vs-new-goal — chat must resolve (§5.2)
ARCHIVED = "archived"  # gid vanished from the markdown (§5.4)
UNKNOWN_GID = "unknown_gid"  # gid not in this chapter — surface, don't guess


class GoalDiff(BaseModel):
    gid: int | None
    title: str
    classification: str
    # For AMBIGUOUS: the safe default the chat should offer ("version_bump" —
    # §5.2 says default to a version bump, never silently fork identity).
    default: str | None = None


class Candidates(BaseModel):
    """Prepared goal-setting candidate list (§5.5 / architecture §5). The LLM
    proposes *from* this; it never issues the selection query."""

    goals: list[dict]  # past goals (any chapter, archived or not)
    tasks: list[dict]  # open tier-2/3 personal tasks; work tasks never appear


def _current_version(versions: list[GoalVersion]) -> GoalVersion | None:
    """The live version to diff against: the open (`effective_to is None`),
    active version, preferring the NEED bar (the committed floor)."""
    live = [
        v
        for v in versions
        if v.effective_to is None and v.lifecycle == VersionLifecycle.ACTIVE
    ]
    if not live:
        return None
    return next((v for v in live if v.level == Level.NEED), live[0])


@dataclass
class IngestionUseCases:
    goals: GoalRepositoryPort
    profiles: ProfileRepositoryPort
    tasks: TaskQueryClient

    # --- candidate-gathering (B2.1) ---

    def propose_candidates(self, owner: int) -> dict:
        """Past goals ∪ open tier-2/3 personal tasks for the owner. The tracker
        is personal-only (ADR-0019); private tasks are excluded by the client
        (ADR-0018)."""
        past = [
            {
                "gid": g.id,
                "title": g.title,
                "chapter_id": g.chapter_id,
                "archived": g.archived_at is not None,
            }
            for g in self.goals.list_all_goals(owner)
        ]
        tasks = [
            {"id": t.id, "title": t.title, "tier": t.tier, "source": "personal"}
            for t in self.tasks.get_personal_candidates(owner, tiers=(2, 3))
        ]
        return Candidates(goals=past, tasks=tasks).model_dump()

    # --- re-ingest diff (B2.2) ---

    def diff_chapter(self, chapter_id: int, parsed: list[dict]) -> list[dict]:
        """Classify each parsed goal against the chapter's current records, and
        flag any recorded goal that vanished from the markdown as ARCHIVED.
        Identity is by `gid` only, resolved within the chapter (§5.1/§5.2)."""
        parsed_goals = [ParsedGoal(**p) for p in parsed]
        current = self.goals.get_goals_for_chapter(chapter_id)
        by_gid = {g.id: g for g in current}
        seen: set[int] = set()

        out: list[GoalDiff] = []
        for pg in parsed_goals:
            if pg.gid is None:
                out.append(GoalDiff(gid=None, title=pg.title, classification=NEW))
                continue
            goal = by_gid.get(pg.gid)
            if goal is None:
                out.append(
                    GoalDiff(gid=pg.gid, title=pg.title, classification=UNKNOWN_GID)
                )
                continue
            seen.add(pg.gid)
            out.append(self._classify(pg, goal))

        # Recorded, non-archived goals absent from the markdown → auto-archive.
        for goal in current:
            if goal.id not in seen and goal.archived_at is None:
                out.append(
                    GoalDiff(gid=goal.id, title=goal.title, classification=ARCHIVED)
                )
        return [d.model_dump() for d in out]

    def _classify(self, pg: ParsedGoal, goal) -> GoalDiff:
        detail = self.goals.get_goal_detail(goal.id)
        current = _current_version(detail[1]) if detail else None
        if current is None:
            # No live version to compare — treat any content as a fresh bump.
            return GoalDiff(gid=goal.id, title=pg.title, classification=VERSION_BUMP)

        title_changed = pg.title != goal.title
        defn_changed = pg.definition != current.definition
        rec_changed = pg.recurrence_type != str(current.recurrence_type)
        bar_changed = pg.target_quantity != current.target_quantity

        if not (title_changed or defn_changed or rec_changed or bar_changed):
            return GoalDiff(gid=goal.id, title=pg.title, classification=UNCHANGED)
        # A pure numeric-bar edit (7k→8k) is tracked evolution — version, no
        # prompt (§5.2). Old daily_plan_items stay pinned to the old version.
        if bar_changed and not (title_changed or defn_changed or rec_changed):
            return GoalDiff(gid=goal.id, title=pg.title, classification=VERSION_BUMP)
        # Any definition/title/recurrence shift may be a moved meaning — surface
        # version-vs-new-goal, never guess. Default to a version bump (§5.2).
        return GoalDiff(
            gid=goal.id,
            title=pg.title,
            classification=AMBIGUOUS,
            default=VERSION_BUMP,
        )

    # --- rollover (B2.3, goal-markdown §5.5 / ADR-0013) ---

    def rollover(
        self,
        owner: int,
        start: date,
        end: date,
        carried: list[dict],
        label: str | None = None,
        preamble: str | None = None,
    ) -> dict:
        """Open a new chapter window and carry goals forward as FRESH goals
        scoped to it; close (archive) the prior chapter's goals. No cross-chapter
        lineage is recorded — deliberate (ADR-0013), keeps `gid` reconciliation
        tractable."""
        # The prior chapter is the owner's latest chapter started before the
        # new window — NOT "active the day before start": chapters are not
        # contiguous in practice (a late rollover leaves a gap, and the old
        # active-day-before lookup silently archived nothing).
        prior = self.goals.get_latest_chapter_before(owner, start)
        archived = self.goals.archive_chapter_goals(prior.id) if prior else []
        new_chapter_id = self.goals.create_chapter(
            _chapter(owner, start, end, label, preamble)
        ).id
        specs = [dict(g, chapter_id=new_chapter_id) for g in carried]
        new_goals = self._create_carried(owner, specs)
        return {
            "chapter_id": new_chapter_id,
            "new_goal_ids": [g["gid"] for g in new_goals],
            "archived_goal_ids": archived,
        }

    def _create_carried(self, owner: int, specs: list[dict]) -> list[dict]:
        from goal_bot.domain.entities import Goal

        built: list[tuple] = []
        for g in specs:
            goal = Goal(
                owner_profile_id=owner,
                title=g["title"],
                chapter_id=g.get("chapter_id"),
            )
            versions = [GoalVersion(goal_id=None, **v) for v in g["versions"]]
            built.append((goal, versions))
        saved = self.goals.create_goals_with_versions(built)
        return [{"gid": goal.id, "title": goal.title} for goal, _ in saved]

    # --- soft invariant (B2.4, ADR-0013, confirm-at-ingest) ---

    def check_goal_scope(self, goal_owner_id: int, chapter_id: int) -> dict:
        """Flag a group-owned goal placed inside an individual's *private*
        chapter for confirmation at ingest. This is an application check, not a
        DB rule — a personal goal in a shared chapter is legitimate and is never
        flagged. Ownership equality is otherwise unenforced."""
        chapter = self.goals.get_chapter(chapter_id)
        if chapter is None:
            return {"confirm_required": False}
        goal_kind = self.profiles.get_kind(goal_owner_id)
        chapter_kind = self.profiles.get_kind(chapter.owner_profile_id)
        confirm = goal_kind == ProfileKind.GROUP and chapter_kind == ProfileKind.PERSON
        return {
            "confirm_required": confirm,
            "reason": (
                "group-owned goal in an individual's private chapter"
                if confirm
                else None
            ),
        }


def _chapter(
    owner: int,
    start: date,
    end: date,
    label: str | None,
    preamble: str | None = None,
):
    from goal_bot.domain.entities import Chapter

    return Chapter(
        owner_profile_id=owner,
        start_date=start,
        end_date=end,
        label=label,
        preamble=preamble,
    )
