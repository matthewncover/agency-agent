from datetime import time

import pytest
from agency_profile.domain.entities import ProfileKind


def test_person_default_morning_prompt_time():
    from agency_profile.domain.entities import Person
    p = Person(display_name="Alice", timezone="America/Los_Angeles")
    assert p.morning_prompt_local_time == time(6, 0)


def test_profile_kind_valid_values():
    assert ProfileKind("person") == ProfileKind.PERSON
    assert ProfileKind("group") == ProfileKind.GROUP


def test_profile_kind_invalid_raises():
    with pytest.raises(ValueError):
        ProfileKind("invalid")
