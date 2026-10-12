"""The replay engine: six days, one event stream, no persistence.

Day shape, in strict order:

  1. apply every event whose posting_day is this day, in stream order
  2. assess the overdraft fee (once per account, if the day closes negative)
  3. accrue the day's interest on the post-fee closing balance, if positive
  4. on the final day only, capitalize the accruals as one credit

Two dates drive everything and must not be conflated:

  posting_day  -- when the ledger learned about the movement
  value_date   -- when the movement counts toward a balance

E7 is a Day 5 event with a Day 2 value date. Its arrival changes what the
Day 2 balance *is* when restated, which is a reporting question, and
separately raises whether a closed day can grow a new fee, which is a
policy question. This engine answers the second one forward-only: a day's
fee is assessed once, at that day's close, on the balance known then.
AMBIGUITIES.md section 2 argues the case and names what it costs.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from .entries import Journal
from .events import Event
from .money import Currency

WINDOW_DAYS = 6


@dataclass(frozen=True)
class Account:
    id: str
    currency: Currency
    opening_balance: Decimal


@dataclass
class DayReport:
    day: int
    account_id: str
    closing_balance: Decimal


@dataclass
class ReplayResult:
    accounts: dict[str, Account]
    journal: Journal
    results: list[EventResult] = field(default_factory=list)
    days: dict[int, list[DayReport]] = field(default_factory=dict)

    def result_for(self, event_id: str) -> EventResult:
        for r in self.results:
            if r.event_id == event_id:
                return r
        raise KeyError(event_id)

    def report(self, day: int, account_id: str) -> DayReport:
        for r in self.days[day]:
            if r.account_id == account_id:
                return r
        raise KeyError((day, account_id))


class Engine:
    """Replays an event stream over a fixed day window."""

    def __init__(self, accounts: list[Account], *, window: int = WINDOW_DAYS):
        self.window = window
        self.state = ReplayResult(
            accounts={a.id: a for a in accounts},
            journal=Journal(),
        )
        for account in accounts:
            if account.opening_balance != 0:
                self.state.journal.append(
                    event_id=f"OPENING-{account.id}",
                    account_id=account.id,
                    posting_day=1,
                    value_date=1,
                    amount=account.currency.quantize(account.opening_balance),
                    kind="CREDIT",
                    memo="opening balance",
                )

    # ---------- balance views ----------

    def ledger_balance(self, account_id: str, *, through_day: int,
                       value_date_through: Optional[int] = None) -> Decimal:
        account = self.state.accounts[account_id]
        return self.state.journal.balance(
            account_id,
            account.currency,
            value_date_through=through_day if value_date_through is None else value_date_through,
            known_through_day=through_day,
        )

    # ---------- replay ----------

    def replay(self, events: list[Event]) -> ReplayResult:
        for event in events:
            if event.posting_day > self.window:
                raise ValueError(f"{event.id}: posting_day beyond the window")
        for day in range(1, self.window + 1):
            self._close_day(day)
        return self.state

    # ---------- end of day ----------

    def _close_day(self, day: int) -> None:
        reports = []
        for account_id in self.state.accounts:
            reports.append(DayReport(
                day=day,
                account_id=account_id,
                closing_balance=self.ledger_balance(account_id, through_day=day),
            ))
        self.state.days[day] = reports
