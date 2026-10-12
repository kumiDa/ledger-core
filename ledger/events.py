"""The input event stream. Events are facts that arrived; they are never edited.

An event is a *request*. It may be approved, declined, or rejected. The
ledger entries it produces (if any) are a separate, derived record -- see
entries.py. Keeping the two apart is what lets a declined authorization and
a rejected settlement leave an audit trail without moving money.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional


class EventType(str, Enum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"
    AUTHORIZATION = "AUTHORIZATION"
    SETTLEMENT = "SETTLEMENT"
    REVERSAL = "REVERSAL"


@dataclass(frozen=True)
class Event:
    id: str
    posting_day: int       # the day the event reaches the ledger
    type: EventType
    account_id: str
    value_date: int        # the day the money is effective for balance purposes
    amount: Optional[Decimal] = None
    auth_id: Optional[str] = None     # AUTHORIZATION / SETTLEMENT
    reverses: Optional[str] = None    # REVERSAL -> target event id
    instalments: int = 1              # split the amount into N postings

    def __post_init__(self) -> None:
        if self.posting_day < 1:
            raise ValueError(f"{self.id}: posting_day must be >= 1")
        if self.value_date < 1:
            raise ValueError(f"{self.id}: value_date must be >= 1")
        if self.type is EventType.REVERSAL and not self.reverses:
            raise ValueError(f"{self.id}: REVERSAL must name the event it reverses")
        if self.type in (EventType.AUTHORIZATION, EventType.SETTLEMENT) and not self.auth_id:
            raise ValueError(f"{self.id}: {self.type.value} must carry an auth_id")
        if self.type is not EventType.REVERSAL and self.amount is None:
            raise ValueError(f"{self.id}: {self.type.value} must carry an amount")
        if self.amount is not None and self.amount <= 0:
            raise ValueError(
                f"{self.id}: amounts are unsigned magnitudes; "
                f"direction comes from the event type, got {self.amount}"
            )
        if self.instalments < 1:
            raise ValueError(f"{self.id}: instalments must be >= 1")
