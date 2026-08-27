from datetime import date

from fastmcp import FastMCP

from goal_bot.application.ingestion import IngestionUseCases


def register_ingestion_tools(mcp: FastMCP, uc: IngestionUseCases) -> None:
    """The deterministic goal-setting / re-ingest surface (B2). Each tool hands
    the LLM a prepared result; the LLM never re-identifies goals from content."""

    @mcp.tool
    def propose_candidates(owner: int) -> dict:
        """Goal-setting candidates: the owner's past goals ∪ their open tier-2/3
        personal tasks. Work tasks are never candidates (ADR-0005). Returns
        {goals:[...], tasks:[...]} — propose FROM this, never re-query."""
        return uc.propose_candidates(owner)

    @mcp.tool
    def diff_chapter(chapter_id: int, parsed: list[dict]) -> list[dict]:
        """Classify re-ingested goals against a chapter's records: each parsed
        goal ({gid?, title, definition, recurrence_type, target_quantity?}) →
        new / version_bump / unchanged / ambiguous / unknown_gid; recorded goals
        gone from the markdown → archived. `ambiguous` (version-vs-new-goal) must
        be resolved in the confirm queue — never guessed."""
        return uc.diff_chapter(chapter_id, parsed)

    @mcp.tool
    def rollover(
        owner: int,
        start: date,
        end: date,
        carried: list[dict],
        label: str | None = None,
        preamble: str | None = None,
    ) -> dict:
        """Open a new chapter window and carry goals forward as FRESH goals
        scoped to it, archiving the prior chapter's goals. `carried` is a list of
        {title, chapter_id?, versions:[...]} (chapter_id is overwritten).
        `preamble` is the authored per-chapter framing, stored verbatim
        (goal-markdown §2.1). No cross-chapter lineage is kept (ADR-0013).
        Returns {chapter_id, new_goal_ids, archived_goal_ids}."""
        return uc.rollover(owner, start, end, carried, label, preamble)

    @mcp.tool
    def check_goal_scope(goal_owner_id: int, chapter_id: int) -> dict:
        """Soft invariant: flag a group-owned goal placed in an individual's
        private chapter for confirmation (ADR-0013). Returns {confirm_required,
        reason}. A personal goal in a shared chapter is legitimate — not flagged."""
        return uc.check_goal_scope(goal_owner_id, chapter_id)
