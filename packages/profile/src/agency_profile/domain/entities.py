from datetime import datetime, time
from enum import StrEnum

from pydantic import BaseModel


class ProfileKind(StrEnum):
    PERSON = "person"
    GROUP = "group"


class Profile(BaseModel):
    id: int | None = None
    kind: ProfileKind
    created_at: datetime | None = None


class Person(BaseModel):
    profile_id: int | None = None
    display_name: str
    timezone: str
    morning_prompt_local_time: time = time(6, 0)


class GroupProfile(BaseModel):
    profile_id: int | None = None
    label: str


class ProfileDoc(BaseModel):
    person_id: int
    content: str
    updated_at: datetime | None = None
