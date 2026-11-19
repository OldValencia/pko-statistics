from dataclasses import dataclass

from pkostat.domain import Kind


@dataclass(frozen=True, slots=True)
class ParsedNotification:
    occurred_at: str  # local ISO date-time; from the text, else when the push arrived
    amount_minor: int  # signed: spending < 0
    currency: str
    kind: Kind
    counterparty: str | None
    location: str | None
    title: str | None

    @property
    def occurred_on(self) -> str:
        return self.occurred_at[:10]
