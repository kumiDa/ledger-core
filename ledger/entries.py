"""Append-only ledger entries and the immutable journal that holds them.

The journal is the system of record. It supports exactly one mutation:
append. There is no update, no delete, no entry rewrite. A reversal is a
*new* entry that happens to carry the opposite sign of an earlier one; the
reversed entry stays on the books forever.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Iterator, Optional

from .money import Currency


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


class Journal:
    """Append-only entry store with as-of balance queries."""

    def __init__(self) -> None:
        self._entries: list[Entry] = []

    def append(
        self,
        *,
        event_id: str,
        account_id: str,
        posting_day: int,
        value_date: int,
        amount: Decimal,
        kind: str,
        memo: str = "",
        reverses_seq: Optional[int] = None,
    ) -> Entry:
        entry = Entry(
            seq=len(self._entries) + 1,
            event_id=event_id,
            account_id=account_id,
            posting_day=posting_day,
            value_date=value_date,
            amount=amount,
            kind=kind,
            memo=memo,
            reverses_seq=reverses_seq,
        )
        self._entries.append(entry)
        return entry

    def __iter__(self) -> Iterator[Entry]:
        return iter(tuple(self._entries))

    def __len__(self) -> int:
        return len(self._entries)

    def for_account(self, account_id: str) -> tuple[Entry, ...]:
        return tuple(e for e in self._entries if e.account_id == account_id)

    def by_seq(self, seq: int) -> Optional[Entry]:
        for entry in self._entries:
            if entry.seq == seq:
                return entry
        return None

    def entries_for_event(self, event_id: str) -> tuple[Entry, ...]:
        return tuple(e for e in self._entries if e.event_id == event_id)

    def balance(
        self,
        account_id: str,
        currency: Currency,
        *,
        value_date_through: int,
        known_through_day: Optional[int] = None,
        kinds_excluded: Iterable[str] = (),
    ) -> Decimal:
        """Sum of entries with value_date <= `value_date_through`.

        `known_through_day` bounds which entries are considered to exist yet.
        The pair is what makes a restatement expressible: "the Day 2 balance
        as the books looked at the end of Day 5" is
        value_date_through=2, known_through_day=5.
        """
        excluded = set(kinds_excluded)
        total = currency.zero()
        for entry in self._entries:
            if entry.account_id != account_id:
                continue
            if entry.value_date > value_date_through:
                continue
            if known_through_day is not None and entry.posting_day > known_through_day:
                continue
            if entry.kind in excluded:
                continue
            total += entry.amount
        return currency.quantize(total)
