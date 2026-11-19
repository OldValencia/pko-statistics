"""Core domain types shared by ingest, reconciliation, analytics and the database layer."""

from dataclasses import dataclass, field
from enum import StrEnum


class Source(StrEnum):
    NOTIFICATION = "notification"
    CSV = "csv"


class Kind(StrEnum):
    CARD = "card"
    BLIK = "blik"
    TRANSFER_OUT = "transfer_out"
    TRANSFER_IN = "transfer_in"
    REFUND = "refund"
    ATM = "atm"
    OTHER = "other"


class Status(StrEnum):
    SETTLED = "settled"
    PENDING = "pending"
    SUPERSEDED = "superseded"
    UNMATCHED = "unmatched"


@dataclass(frozen=True, slots=True)
class Transaction:
    user_id: int
    source: Source
    source_id: int
    occurred_on: str
    occurred_at: str | None
    amount_minor: int
    currency: str
    kind: Kind
    counterparty: str | None
    location: str | None
    title: str | None
    status: Status
    merchant_key: str | None = None
    matched_csv_row_id: int | None = None
    category: str | None = None

    @property
    def counted(self) -> bool:
        """Whether it enters statistics: superseded and unmatched records do not."""
        return self.status in (Status.SETTLED, Status.PENDING)


@dataclass(frozen=True, slots=True)
class Budget:
    """Money in grosze. No goal and no limits = the feature is off for the user."""

    goal: int | None = None
    limits: dict[str, int] = field(default_factory=dict)

    @property
    def empty(self) -> bool:
        return self.goal is None and not self.limits
