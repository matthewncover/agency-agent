from datetime import date

from pydantic import BaseModel


class SurfacedWin(BaseModel):
    text: str
    why: str | None = None
    source: str  # 'manual' | 'derived'


class YesterdayItem(BaseModel):
    goal_title: str
    status: str  # stored verbatim — never synthesized to not_done
    what_shifted: str | None = None


class CandidateItem(BaseModel):
    goal_id: int
    goal_version_id: int  # the version chosen to pin (need by default)
    goal_title: str
    level: str
    is_carry_over: bool = False


class MorningContext(BaseModel):
    person_id: int
    plan_date: date
    win_surface: list[SurfacedWin]
    thin_day: bool  # true when nothing to surface → A6 gives a meaning-linked ack
    yesterday: list[YesterdayItem]
    candidates: list[CandidateItem]  # smart subset to propose
    full_list: list[CandidateItem]   # always-one-tap-away override
