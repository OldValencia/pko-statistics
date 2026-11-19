"""The report's data, as the page and the LLM receive it. Money is int grosze, shares are floats."""

from pydantic import BaseModel

from pkostat.analytics.model_plan import BudgetLine, GoalStatus, MonthStory


class MerchantLine(BaseModel):
    merchant: str
    total: int
    count: int


class CategoryRow(BaseModel):
    category: str
    label: str
    kind: str
    now: int
    previous: int
    average: int
    payments: int
    top_merchants: list[MerchantLine]


class Finding(BaseModel):
    category: str
    label: str
    kind: str
    now: int
    average: int
    change: float | None  # relative to average; None when there was no average
    payments: int
    headline: bool  # the biggest impulse category, shown even when it did not grow
    top_merchants: list[MerchantLine]


class ShareSlice(BaseModel):
    label: str
    category: str | None  # None for the "rest" slice
    total: int


class Pace(BaseModel):
    current: list[int]  # cumulative spending by day, index 0 = day 1
    previous: list[int]
    average: list[int]
    last_day: int


class Weekdays(BaseModel):
    months: list[str]
    average_per_day: list[int]  # Monday first
    totals: list[int]


class TopMerchant(BaseModel):
    merchant: str
    category: str
    label: str
    kind: str
    total: int
    count: int


class MonthSummary(BaseModel):
    month: str
    complete: bool
    income: int
    spend: int
    transfers: int
    to_people: int
    net: int
    savings_rate: float | None
    by_kind: dict[str, int]
    by_category: dict[str, int]


class MonthNotes(BaseModel):
    pending: int
    uncategorised: int
    uncategorised_total: int
    shifted_dates: list[str]


class MonthReport(BaseModel):
    summary: MonthSummary
    previous: MonthSummary | None
    baseline_months: list[str]
    categories: list[CategoryRow]
    leaks: list[Finding]
    wins: list[Finding]
    share: list[ShareSlice]
    pace: Pace
    weekdays: Weekdays
    top_merchants: list[TopMerchant]
    notes: MonthNotes
    budgets: list[BudgetLine] = []
    goal: GoalStatus | None = None
    story: MonthStory | None = None


class Recurring(BaseModel):
    merchant: str
    category: str
    label: str
    price: int  # the latest charge
    last_charge: str
    months: int
    active: bool


class Ytd(BaseModel):
    months: list[str]
    income: int
    spend: int
    net: int
    impulse: int
    top_impulse_label: str | None
    top_impulse_total: int
    top_impulse_payments: int
    biggest_essential_label: str | None
    biggest_essential_monthly: int


class Lever(BaseModel):
    category: str
    label: str
    monthly: int  # average spend per month in the baseline
    payments: int  # average payments per month
    by_count: bool  # slider on the number of payments instead of a percentage


class WhatIf(BaseModel):
    months: list[str]
    income: int
    net: int
    levers: list[Lever]


class CategoryInfo(BaseModel):
    name: str
    label: str
    kind: str


class TransactionRow(BaseModel):
    id: str
    date: str
    month: str
    merchant: str
    raw: str
    title: str
    category: str | None
    type: str
    status: str
    source: str
    amount: int


class ReportData(BaseModel):
    user: str
    generated_at: str
    data_until: str
    months: list[str]
    series: list[MonthSummary]
    reports: dict[str, MonthReport]
    categories: list[CategoryInfo]
    recurring: list[Recurring]
    ytd: Ytd | None
    what_if: WhatIf | None
    transactions: list[TransactionRow]
    unmatched_holds: int
