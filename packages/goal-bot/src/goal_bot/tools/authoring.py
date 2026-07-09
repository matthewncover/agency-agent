from datetime import date

from fastmcp import FastMCP

from goal_bot.application.use_cases import GoalUseCases


def register_authoring_tools(mcp: FastMCP, uc: GoalUseCases) -> None:
    @mcp.tool
    def create_chapter(
        owner: int, start: date, end: date, label: str | None = None
    ) -> int:
        """Create a new chapter and return its id."""
        return uc.create_chapter(owner, start, end, label)

    @mcp.tool
    def create_goal(owner: int, title: str, chapter_id: int | None = None) -> int:
        """Create a new goal and return its id."""
        return uc.create_goal(owner, title, chapter_id)

    @mcp.tool
    def create_goal_version(
        goal_id: int,
        level: str,
        definition: str,
        recurrence_type: str,
        recurrence_config: dict,
        completion_type: str,
        why: str | None = None,
        target_quantity: float | None = None,
        quantity_unit: str | None = None,
        obstacles: list[str] | None = None,
        task_ref_source: str | None = None,
        task_ref_id: int | None = None,
        lifecycle: str = "active",
    ) -> int:
        """Create a new version for an existing goal and return the version id.

        version_no is assigned by the server (per goal+level); a bar change is a
        new version, same goal id. `obstacles` are stored verbatim, one row each.
        """
        return uc.create_goal_version(
            goal_id=goal_id,
            level=level,
            definition=definition,
            why=why,
            recurrence_type=recurrence_type,
            recurrence_config=recurrence_config,
            completion_type=completion_type,
            target_quantity=target_quantity,
            quantity_unit=quantity_unit,
            obstacles=obstacles or [],
            task_ref_source=task_ref_source,
            task_ref_id=task_ref_id,
            lifecycle=lifecycle,
        )

    @mcp.tool
    def create_goals(owner: int, goals: list[dict]) -> list[dict]:
        """Batch-create new goals with their versions in ONE transaction. Prefer
        this over many create_goal / create_goal_version calls.

        Each goal: {title, chapter_id?, versions: [ {level, definition,
        recurrence_type, recurrence_config, completion_type, why?,
        target_quantity?, quantity_unit?, obstacles?, task_ref_source?,
        task_ref_id?} ... ]}. Do NOT pass version_no (server-assigned).
        Returns [{gid, title, versions:[{level, version_id, version_no}]}] — use
        each gid for write-back. Handles explode-buckets and need+want pairs.
        """
        return uc.create_goals(owner, goals)

    @mcp.tool
    def create_goal_versions(versions: list[dict]) -> list[int]:
        """Batch-add versions to EXISTING goals in ONE transaction (re-ingest bar
        changes). Each version: {goal_id, level, definition, recurrence_type,
        recurrence_config, completion_type, why?, target_quantity?,
        quantity_unit?, obstacles?, task_ref_source?, task_ref_id?}. A bar change
        is a new version on the same goal_id (server closes the prior). Do NOT
        pass version_no. Returns the new version ids.
        """
        return uc.create_goal_versions(versions)

    @mcp.tool
    def create_rotation_group(owner: int, name: str, sequence: list[dict]) -> dict:
        """Create a rotation group (ADR-0016): a cross-goal cadence scheduler
        for goals sharing one rhythm (push → rest → pull → rest). `sequence`
        entries are {"goal_id": N} or {"rest": true}; each rest slot consumes
        one calendar day. Members keep their own bars/logging; a member is
        excluded from independent scheduling while its group is active, and may
        belong to at most one active group. Returns the created group."""
        return uc.create_rotation_group(owner, name, sequence)

    @mcp.tool
    def archive_rotation_group(group_id: int) -> dict:
        """Archive a rotation group (authoring edit, e.g. removed from the
        markdown or stale after rollover). Members degrade gracefully back to
        self-scheduling on their own recurrence."""
        return uc.archive_rotation_group(group_id)

    @mcp.tool
    def list_rotation_groups(owner: int) -> list[dict]:
        """The owner's active rotation groups (sequence, pointer, members) —
        the re-ingest reconciliation read (groups go stale at rollover)."""
        return uc.list_rotation_groups(owner)

    @mcp.tool
    def update_goal(goal_id: int, fields: dict) -> dict:
        """Update goal identity fields (title, chapter_id, archived_at only).

        Tags are not yet writable (no tag write path; deferred per template §4).
        """
        return uc.update_goal(goal_id, fields)
