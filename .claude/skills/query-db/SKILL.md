---
name: query-db
description: Query the agency-agent Postgres database (profile + goalbot schemas). Use whenever the user asks to inspect, check, count, or verify data in the database — goals, daily plans, plan items/outcomes, wins, chapters, persons, etc. Contains the connection command, full schema map, naming traps, and ready-to-run query recipes.
---

# Querying the agency-agent database

The database runs in Docker (Postgres). All data lives in two schemas: **`profile`** and **`goalbot`**. There is no `public` data — always schema-qualify table names.

## Connection

```bash
docker exec agency-agent-postgres-1 psql -U agency -d agency -c "SELECT ..."
```

- Container: `agency-agent-postgres-1` (confirm with `docker ps` if a query errors with "No such container"; start it with `just up`).
- User/db: `agency` / `agency`.
- For multi-line SQL, pass a heredoc-style quoted string to `-c`. For readability add `psql` flags: `-P pager=off` (never paginate), `-x` (expanded/vertical output for wide rows).

## Naming traps (we hit all of these)

These are the mismatches between intuition and reality. Check here first when a column/table "doesn't exist":

| You might type | It's actually |
|---|---|
| `goalbot.win` | `goalbot.win_log` |
| `win_log.owner` / `owner_profile_id` | `win_log.person_id` |
| `goal.name` | `goal.title` |
| `daily_plan.owner` | `daily_plan.person_id` |
| a person's PK `person.id` | `person.profile_id` (PK shared with `profile.id`) |
| `goal_version.title` | versions have **no title** — title lives on `goal`; versions carry `definition` |

Ownership column is **inconsistent by design**: `goal` and `chapter` use **`owner_profile_id`**; everything else (`daily_plan`, `win_log`, `friction_log`, `insight`) uses **`person_id`**. Both point at `profile.person.profile_id`.

## Enums (CHECK constraints)

- `daily_plan_item.status`: `planned` | `done` | `partial` | `not_done` | `carried_over`
- `goal_version.level`: `need` | `want`
- `goal_version.lifecycle`: `active` | `paused` | `archived`
- `goal_version.completion_type`: `binary` | `quantity` | `duration`
- `goal_version.recurrence_type`: `oneoff` | `daily` | `rotation` | `quota` | `interval` | `fixed_schedule` | `accumulation`
- `goal_version.task_ref_source`: `personal` | `work`
- `win_log.source`: `manual` | `derived`
- `insight.status`: `active` | `proposed_for_profile` | `graduated` | `dismissed`

## Schema map

### profile schema

- **profile** `(id PK, kind, created_at)` — base identity. `kind` distinguishes person vs group.
- **person** `(profile_id PK→profile.id, display_name, timezone, morning_prompt_local_time)` — the human. **PK is `profile_id`.**
- **profile_doc** `(person_id PK→person, content, updated_at)` — the authored Tier-1 profile doc.
- **group_profile** `(profile_id PK→profile.id, label)`
- **group_member** `(group_profile_id→group_profile, member_person_id→person)`

### goalbot schema

- **chapter** `(id PK, owner_profile_id, label, start_date, end_date)` — time-boxed life chapter.
- **goal** `(id PK, owner_profile_id, chapter_id→chapter, title, created_at, archived_at)` — stable goal identity. **Title lives here.**
- **goal_version** `(id PK, goal_id→goal, version_no, level, definition, why, recurrence_type, recurrence_config jsonb, completion_type, target_quantity, quantity_unit, task_ref_source, task_ref_id, effective_from, effective_to, lifecycle, created_at)` — versioned goal spec. **Current version = `effective_to IS NULL`.** Unique current version per `(goal_id, level)`.
- **goal_state** `(goal_id PK→goal, rotation_index, last_completed_at, carry_over_count, updated_at)` — mutable runtime state.
- **anticipated_obstacle** `(id PK, goal_version_id→goal_version, text)`
- **tag** `(id PK, name)` / **goal_tag** `(goal_id, tag_id)` — M:N tags.
- **daily_plan** `(id PK, person_id, plan_date, locked_in_at, lock_was_explicit, created_at)` — one plan per person per day. Locked when `locked_in_at IS NOT NULL`.
- **daily_plan_item** `(id PK, daily_plan_id→daily_plan, goal_id, goal_version_id, status, quantity_actual, what_shifted, created_at, updated_at)` — the day's items + outcomes. FK is composite `(goal_id, goal_version_id)→goal_version(goal_id, id)`.
- **win_log** `(id PK, person_id, goal_id→goal nullable, source, text, created_at)` — surfaced/recorded wins.
- **friction_log** `(id PK, person_id, goal_id nullable, daily_plan_item_id nullable, text, logged_for_date, created_at)`
- **insight** `(id PK, person_id, content, status, derived_from jsonb, created_at, updated_at)` — Tier-3 advisory digest entries.

### Key joins

- plan item → its goal title: `daily_plan_item dpi JOIN goal g ON dpi.goal_id = g.id`
- plan item → version spec: `daily_plan_item dpi JOIN goal_version gv ON dpi.goal_version_id = gv.id`
- current version of a goal: `goal_version WHERE goal_id = ? AND effective_to IS NULL`
- person's goals: `goal WHERE owner_profile_id = ?`

## Query recipes

**Today's plan with outcomes** (the most common check):
```bash
docker exec agency-agent-postgres-1 psql -U agency -d agency -P pager=off -c "
SELECT dpi.id, g.title, dpi.status, dpi.quantity_actual, dpi.what_shifted
FROM goalbot.daily_plan dp
JOIN goalbot.daily_plan_item dpi ON dpi.daily_plan_id = dp.id
JOIN goalbot.goal g ON dpi.goal_id = g.id
WHERE dp.person_id = 1 AND dp.plan_date = CURRENT_DATE
ORDER BY dpi.id;"
```

**Plan lock status:**
```bash
docker exec agency-agent-postgres-1 psql -U agency -d agency -c "
SELECT id, plan_date, locked_in_at, lock_was_explicit
FROM goalbot.daily_plan WHERE person_id = 1 ORDER BY plan_date DESC LIMIT 5;"
```

**Active goals with current version:**
```bash
docker exec agency-agent-postgres-1 psql -U agency -d agency -P pager=off -c "
SELECT g.id, g.title, gv.level, gv.definition, gv.recurrence_type, gv.lifecycle
FROM goalbot.goal g
JOIN goalbot.goal_version gv ON gv.goal_id = g.id AND gv.effective_to IS NULL
WHERE g.owner_profile_id = 1 AND g.archived_at IS NULL
ORDER BY g.id;"
```

**Recent wins:**
```bash
docker exec agency-agent-postgres-1 psql -U agency -d agency -c "
SELECT id, source, text, goal_id, created_at
FROM goalbot.win_log WHERE person_id = 1 ORDER BY id DESC LIMIT 10;"
```

**Persons (find the person_id):**
```bash
docker exec agency-agent-postgres-1 psql -U agency -d agency -c "
SELECT profile_id, display_name, timezone, morning_prompt_local_time FROM profile.person;"
```

## Discovery fallbacks

When unsure, introspect rather than guess:
- List tables: `\dt goalbot.*` / `\dt profile.*`
- Describe a table: `\d goalbot.daily_plan_item`
- All enums in a schema: query `pg_constraint` for `contype='c'`.

## Boundaries

Per repo rules: this skill is for **reads**. Do not run migrations or destructive/DDL statements against the live DB on your own; migrations are append-only and human-applied. If the user asks to mutate data, surface that boundary and let them decide.
