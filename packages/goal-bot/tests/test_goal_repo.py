import inspect
from datetime import date

import pytest
from goal_bot.application.ports import GoalRepositoryPort
from goal_bot.domain.entities import (
    Chapter,
    CompletionType,
    Goal,
    GoalVersion,
    Level,
    RecurrenceType,
    VersionLifecycle,
)

TODAY = date(2026, 6, 27)
_VERSION_DEFAULTS = dict(
    version_no=1,
    recurrence_type=RecurrenceType.DAILY,
    recurrence_config={},
    completion_type=CompletionType.BINARY,
)


def _make_version(goal_id: int, level: Level, **kw) -> GoalVersion:
    return GoalVersion(
        goal_id=goal_id, level=level, definition="bar", **_VERSION_DEFAULTS, **kw
    )


@pytest.mark.integration
def test_create_goal_returns_id(goal_repo, person_id):
    g = goal_repo.create_goal(Goal(owner_profile_id=person_id, title="run"))
    assert g.id is not None
    assert g.title == "run"


@pytest.mark.integration
def test_create_and_get_goal_detail(goal_repo, person_id):
    g = goal_repo.create_goal(Goal(owner_profile_id=person_id, title="run"))
    v_need = goal_repo.create_goal_version(_make_version(g.id, Level.NEED))
    v_want = goal_repo.create_goal_version(_make_version(g.id, Level.WANT))

    detail = goal_repo.get_goal_detail(g.id)
    assert detail is not None
    fetched_goal, versions = detail
    assert fetched_goal.id == g.id
    assert {v.id for v in versions} == {v_need.id, v_want.id}


@pytest.mark.integration
def test_create_goal_version_persists_obstacles(goal_repo, person_id):
    g = goal_repo.create_goal(Goal(owner_profile_id=person_id, title="steps"))
    obstacles = ["waking late and rushed", "gassed after work"]
    created = goal_repo.create_goal_version(
        _make_version(g.id, Level.NEED, obstacles=obstacles)
    )
    assert created.obstacles == obstacles

    _, versions = goal_repo.get_goal_detail(g.id)
    assert versions[0].obstacles == obstacles


@pytest.mark.integration
def test_version_no_auto_assigned_and_prior_closed(goal_repo, person_id):
    g = goal_repo.create_goal(Goal(owner_profile_id=person_id, title="steps"))
    need_v1 = GoalVersion(
        goal_id=g.id, level=Level.NEED, definition="5k",
        recurrence_type=RecurrenceType.DAILY, recurrence_config={},
        completion_type=CompletionType.BINARY,
    )
    want_v1 = need_v1.model_copy(update={"level": Level.WANT, "definition": "7k"})
    goal_repo.create_goal_version(need_v1)
    goal_repo.create_goal_version(want_v1)
    # a bar bump on need: same goal, new version in the need lineage only
    goal_repo.create_goal_version(need_v1.model_copy(update={"definition": "6k"}))

    _, versions = goal_repo.get_goal_detail(g.id)
    by_level = {}
    for v in versions:
        by_level.setdefault(v.level, []).append(v)

    need_versions = sorted(by_level[Level.NEED], key=lambda v: v.version_no)
    assert [v.version_no for v in need_versions] == [1, 2]
    assert need_versions[0].effective_to is not None  # prior closed
    assert need_versions[1].effective_to is None       # new current
    # want is its own lineage, untouched by the need bump
    assert [v.version_no for v in by_level[Level.WANT]] == [1]
    assert by_level[Level.WANT][0].effective_to is None


@pytest.mark.integration
def test_get_full_goal_list_includes_chapter_and_chapterless(goal_repo, person_id):
    ch = goal_repo.create_chapter(Chapter(
        owner_profile_id=person_id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    ))

    g_in_chapter = goal_repo.create_goal(
        Goal(owner_profile_id=person_id, title="in-chapter", chapter_id=ch.id)
    )
    g_no_chapter = goal_repo.create_goal(
        Goal(owner_profile_id=person_id, title="no-chapter")
    )
    goal_repo.create_goal_version(_make_version(g_in_chapter.id, Level.NEED))
    goal_repo.create_goal_version(_make_version(g_no_chapter.id, Level.NEED))

    goals = goal_repo.get_full_goal_list(person_id, TODAY)
    ids = {g.id for g in goals}
    assert g_in_chapter.id in ids
    assert g_no_chapter.id in ids


@pytest.mark.integration
def test_get_full_goal_list_excludes_archived(goal_repo, person_id):
    g = goal_repo.create_goal(Goal(owner_profile_id=person_id, title="archived"))
    goal_repo.create_goal_version(_make_version(g.id, Level.NEED))
    goal_repo.update_goal(g.id, {"archived_at": "2026-01-01T00:00:00+00:00"})

    goals = goal_repo.get_full_goal_list(person_id, TODAY)
    assert g.id not in {gl.id for gl in goals}


@pytest.mark.integration
def test_get_full_goal_list_excludes_all_paused(goal_repo, person_id):
    g = goal_repo.create_goal(Goal(owner_profile_id=person_id, title="paused"))
    goal_repo.create_goal_version(
        _make_version(g.id, Level.NEED, lifecycle=VersionLifecycle.PAUSED)
    )

    goals = goal_repo.get_full_goal_list(person_id, TODAY)
    assert g.id not in {gl.id for gl in goals}


@pytest.mark.integration
def test_update_goal_title(goal_repo, person_id):
    g = goal_repo.create_goal(Goal(owner_profile_id=person_id, title="old"))
    updated = goal_repo.update_goal(g.id, {"title": "new"})
    assert updated.title == "new"


def test_update_goal_port_has_no_content_params():
    sig = inspect.signature(GoalRepositoryPort.update_goal)
    params = list(sig.parameters.keys())
    assert params == ["self", "goal_id", "fields"]
    for content_field in ("definition", "why", "recurrence_type", "completion_type"):
        assert content_field not in params
