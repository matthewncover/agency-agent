"""B7 Part 3 — group fan-out, shared completion, and the no-comparison guard."""

import json
from datetime import date

import pytest
from agency_profile.domain.entities import GroupProfile, Person
from agency_profile.infrastructure.adapters.profile_repo import (
    SqlAlchemyProfileRepository,
)
from goal_bot.application.morning_context import CandidateItem, MorningContext
from goal_bot.application.ritual_assembly import assemble_morning_context
from goal_bot.application.use_cases import GoalUseCases
from goal_bot.domain.entities import (
    CompletionType,
    DailyPlanItem,
    Goal,
    GoalVersion,
    Level,
    PlanItemStatus,
    RecurrenceType,
)
from goal_bot.infrastructure.adapters.goal_repo import SqlAlchemyGoalRepository
from goal_bot.infrastructure.adapters.plan_repo import SqlAlchemyPlanRepository
from goal_bot.infrastructure.adapters.win_repo import SqlAlchemyWinRepository

TODAY = date.today()

_BANNED_PARTNER = ("partner", "compare", "versus", "relative_to", "rank")


def _profiles(engine):
    return SqlAlchemyProfileRepository(engine)


def _person(engine, name):
    return (
        _profiles(engine)
        .create_person(Person(display_name=name, timezone="America/Los_Angeles"))
        .profile_id
    )


def _group(engine, label, members):
    return _profiles(engine).create_group(GroupProfile(label=label), members).profile_id


def _group_goal(goal_repo, group_id, title, *, target=None):
    g = goal_repo.create_goal(Goal(owner_profile_id=group_id, title=title))
    v = goal_repo.create_goal_version(
        GoalVersion(
            goal_id=g.id,
            level=Level.NEED,
            definition=title,
            version_no=1,
            recurrence_type=RecurrenceType.DAILY,
            recurrence_config={},
            completion_type=CompletionType.QUANTITY,
            target_quantity=target,
        )
    )
    return g, v


def _assemble(engine, person_id, group_ids):
    return assemble_morning_context(
        person_id,
        TODAY,
        goals=SqlAlchemyGoalRepository(engine),
        plans=SqlAlchemyPlanRepository(engine),
        wins=SqlAlchemyWinRepository(engine),
        group_owner_ids=group_ids,
    )


def _uc(engine):
    return GoalUseCases(
        goals=SqlAlchemyGoalRepository(engine),
        plans=SqlAlchemyPlanRepository(engine),
        wins=SqlAlchemyWinRepository(engine),
        profiles=_profiles(engine),
    )


# --- fan-out ----------------------------------------------------------------


@pytest.mark.integration
def test_list_groups_for_person_is_inverse_of_members(migrated_engine):
    a = _person(migrated_engine, "A")
    b = _person(migrated_engine, "B")
    gid = _group(migrated_engine, "Household", [a, b])
    profiles = _profiles(migrated_engine)
    assert set(profiles.list_group_members(gid)) == {a, b}
    assert profiles.list_groups_for_person(a) == [gid]
    assert profiles.list_groups_for_person(b) == [gid]


@pytest.mark.integration
def test_group_goal_fans_out_to_both_members_as_separate_block(
    migrated_engine, goal_repo
):
    a = _person(migrated_engine, "A")
    b = _person(migrated_engine, "B")
    gid = _group(migrated_engine, "Household", [a, b])
    gg, _ = _group_goal(goal_repo, gid, "Walk the dog")

    for member in (a, b):
        ctx = _assemble(migrated_engine, member, [gid])
        # shared goal is in the SEPARATE block...
        assert any(c.goal_id == gg.id for c in ctx.group_block)
        assert all(c.bucket == "group" for c in ctx.group_block)
        # ...and NOT interleaved into the individual plan/full list
        assert not any(c.goal_id == gg.id for c in ctx.candidates)
        assert not any(c.goal_id == gg.id for c in ctx.full_list)


@pytest.mark.integration
def test_individual_goal_stays_out_of_group_block(migrated_engine, goal_repo):
    a = _person(migrated_engine, "A")
    gid = _group(migrated_engine, "Household", [a])
    # an individual goal owned by A, not the group
    ig = goal_repo.create_goal(Goal(owner_profile_id=a, title="Solo run"))
    goal_repo.create_goal_version(
        GoalVersion(
            goal_id=ig.id,
            level=Level.NEED,
            definition="run",
            version_no=1,
            recurrence_type=RecurrenceType.DAILY,
            recurrence_config={},
            completion_type=CompletionType.BINARY,
        )
    )
    ctx = _assemble(migrated_engine, a, [gid])
    assert any(c.goal_id == ig.id for c in ctx.candidates)  # in the plan
    assert not any(c.goal_id == ig.id for c in ctx.group_block)  # not shared


# --- shared completion ------------------------------------------------------


@pytest.mark.integration
def test_completion_by_one_member_marks_done_for_both(
    migrated_engine, goal_repo, plan_repo
):
    a = _person(migrated_engine, "A")
    b = _person(migrated_engine, "B")
    gid = _group(migrated_engine, "Household", [a, b])
    gg, gv = _group_goal(goal_repo, gid, "Walk the dog")

    # A's plan has the shared item; A completes it
    plan_a = plan_repo.get_or_create_plan(a, TODAY)
    item_a = plan_repo.add_plan_item(
        DailyPlanItem(daily_plan_id=plan_a.id, goal_id=gg.id, goal_version_id=gv.id)
    )
    _uc(migrated_engine).log_outcome(item_a.id, "done")

    # ...and it reads done for B too (shared completion)
    prior = plan_repo.get_plan_for_date(b, TODAY)
    assert prior is not None
    _, b_items = prior
    shared = [i for i in b_items if i.goal_id == gg.id]
    assert len(shared) == 1
    assert shared[0].status == PlanItemStatus.DONE


@pytest.mark.integration
def test_individual_completion_does_not_propagate(
    migrated_engine, goal_repo, plan_repo
):
    a = _person(migrated_engine, "A")
    b = _person(migrated_engine, "B")
    _group(migrated_engine, "Household", [a, b])
    # an individual goal owned by A
    g = goal_repo.create_goal(Goal(owner_profile_id=a, title="Solo"))
    v = goal_repo.create_goal_version(
        GoalVersion(
            goal_id=g.id,
            level=Level.NEED,
            definition="solo",
            version_no=1,
            recurrence_type=RecurrenceType.DAILY,
            recurrence_config={},
            completion_type=CompletionType.BINARY,
        )
    )
    plan_a = plan_repo.get_or_create_plan(a, TODAY)
    item_a = plan_repo.add_plan_item(
        DailyPlanItem(daily_plan_id=plan_a.id, goal_id=g.id, goal_version_id=v.id)
    )
    _uc(migrated_engine).log_outcome(item_a.id, "done")
    # B gets nothing — it's not a shared goal
    assert plan_repo.get_plan_for_date(b, TODAY) is None


# --- lowered-bar visibility (D-16), neutral ---------------------------------


@pytest.mark.integration
def test_lowered_shared_bar_surfaces_a_neutral_notice(migrated_engine, goal_repo):
    a = _person(migrated_engine, "A")
    gid = _group(migrated_engine, "Household", [a])
    gg, _ = _group_goal(goal_repo, gid, "Steps together", target=8000)
    # re-anchor the shared bar downward (a new lower need version)
    _uc(migrated_engine).create_goal_version(
        goal_id=gg.id,
        level="need",
        definition="5k steps",
        recurrence_type="daily",
        recurrence_config={},
        completion_type="quantity",
        target_quantity=5000,
    )
    ctx = _assemble(migrated_engine, a, [gid])
    assert ctx.shared_notices  # a neutral notice exists
    assert "Steps together" in ctx.shared_notices[0]


# --- no-comparison guard across all surfaces --------------------------------


@pytest.mark.integration
def test_no_surface_names_or_ranks_the_other_person(migrated_engine, goal_repo):
    alice = _person(migrated_engine, "Alice")
    bob = _person(migrated_engine, "Bob")
    gid = _group(migrated_engine, "Alice and Bob", [alice, bob])
    _group_goal(goal_repo, gid, "Cook dinner", target=3)

    ctx = _assemble(migrated_engine, alice, [gid])
    blob = json.dumps(ctx.model_dump(), default=str)
    # the partner is a witness, not a scoreboard — never named/ranked in a view
    assert "Bob" not in blob
    assert "Alice and Bob" not in blob


def test_context_models_have_no_comparison_field():
    for model in (MorningContext, CandidateItem):
        for f in model.model_fields:
            assert not any(b in f.lower() for b in _BANNED_PARTNER)
