"""Report models for the plan (limits, goal) and the month told in words."""

from pydantic import BaseModel


class BudgetLine(BaseModel):
    category: str
    label: str
    kind: str
    limit: int
    spent: int
    forecast: int | None  # end-of-month estimate while the month runs
    status: str  # ok | near | over


class GoalStatus(BaseModel):
    target: int
    complete: bool
    net: int
    met: bool | None  # None while the month runs
    expected_income: int | None = None
    left_to_spend: int | None = None  # what can still be spent and the goal kept
    per_day: int | None = None
    days_left: int | None = None


class Advice(BaseModel):
    category: str
    label: str
    action: str
    reason: str
    saving: int | None  # a month's saving by code; None for "watch this limit" notes


class MonthStory(BaseModel):
    summary: str
    advice: list[Advice]
