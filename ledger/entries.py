"""Append-only ledger entries and the immutable journal that holds them.

The journal is the system of record. It supports exactly one mutation:
append. There is no update, no delete, no entry rewrite. A reversal is a
*new* entry that happens to carry the opposite sign of an earlier one; the
reversed entry stays on the books forever.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class Entry:
    """One signed movement on one account. Immutable by construction."""

    seq: int               # journal position; strictly increasing, never reused
    event_id: str          # the event that caused this entry
    account_id: str
    posting_day: int       # when the entry was appended
    value_date: int        # when it counts toward a balance
    amount: Decimal        # signed: credit > 0, debit < 0
    kind: str              # CREDIT / DEBIT / SETTLEMENT / FEE / INTEREST / REVERSAL
    memo: str = ""
    reverses_seq: Optional[int] = None
