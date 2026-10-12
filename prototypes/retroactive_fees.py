#!/usr/bin/env python3
"""ABANDONED PROTOTYPE -- retroactive overdraft fee assessment.

Kept in the repository because REJECTED.md section 9 claims this was built
and measured, and a claim like that should be runnable rather than asserted.

It implements the literal reading of the fee rule: a day's fee follows that
day's *restated* balance, so a backdated entry can make a closed day
chargeable after the fact. Fees are appended (never mutated), which keeps
the append-only rule intact -- and immediately creates the problem that
killed the approach, because a fee value-dated to Day N changes the Day N
balance and therefore every later day's balance too.

    python3 prototypes/retroactive_fees.py
"""

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ledger.engine import Engine                              # noqa: E402
from ledger.money import AED                                   # noqa: E402
from scenario import ACCOUNTS, EVENTS                          # noqa: E402

FEE = Decimal("25.00")
MAX_PASSES = 50


def assess_retroactively(state, account_id, as_of_day, *, verbose=True):
    """Append fees until no closed day is both overdrawn and unfeed.

    Returns (fee_days, passes). Raises if it does not converge.
    """
    currency = state.accounts[account_id].currency
    charged: set[int] = set()
    for pass_number in range(1, MAX_PASSES + 1):
        changed = False
        for day in range(1, as_of_day + 1):
            if day in charged:
                continue
            balance = state.journal.balance(
                account_id, currency,
                value_date_through=day, known_through_day=as_of_day,
                kinds_excluded=("INTEREST",),      # fees DO count, by design
            )
            if balance < 0:
                state.journal.append(
                    event_id=f"RETRO-FEE-{account_id}-D{day}",
                    account_id=account_id, posting_day=as_of_day,
                    value_date=day, amount=-currency.quantize(FEE),
                    kind="FEE",
                    memo=f"retroactive overdraft fee for day {day}, "
                         f"assessed on day {as_of_day}",
                )
                charged.add(day)
                changed = True
                if verbose:
                    print(f"    pass {pass_number}: day {day} restated at "
                          f"{currency.format(balance)} -> fee appended")
        if not changed:
            return sorted(charged), pass_number
    raise RuntimeError("fee assessment did not converge")


def main() -> None:
    print(__doc__.split("\n\n")[1].strip(), "\n")

    print("A. Fixpoint run at the close of Day 5 (E7 landed, E9 not yet):")
    state = Engine(ACCOUNTS).replay(EVENTS[:-1])   # every event except E9
    days, passes = assess_retroactively(state, "ACC-001", as_of_day=5)
    total = FEE * len(days)
    print(f"    converged after {passes} passes: fees on days {days} "
          f"= {AED.format(total)}")
    margin = state.journal.balance(
        "ACC-001", AED, value_date_through=3, known_through_day=5,
        kinds_excluded=("INTEREST",))
    print(f"    Day 3 restated after those fees: {AED.format(margin)}")
    print(f"    -> Day 3 stayed positive by {AED.format(margin)}. Had E4 been "
          f"{AED.format(Decimal('400.00') - margin)} or less,\n"
          f"       the Day 2 fee alone would have pushed Day 3 negative and "
          f"cascaded.\n")

    print("B. The same literal rule applied at the close of Day 6 "
          "(E9 reversal included):")
    # Replay all six days, then strip the forward-only fees and interest so
    # the literal rule starts from the movement entries alone.
    fresh = Engine(ACCOUNTS)
    fresh.state.journal._entries = [            # noqa: SLF001  (prototype only)
        e for e in Engine(ACCOUNTS).replay(EVENTS).journal
        if e.kind not in ("FEE", "INTEREST")
    ]
    days6, passes6 = assess_retroactively(fresh.state, "ACC-001", as_of_day=6)
    print(f"    converged after {passes6} passes: fees on days {days6} "
          f"= {AED.format(FEE * len(days6))}")
    print("    -> On the final books, no day is overdrawn at all. The literal "
          "rule\n       charges 75.00 on Day 5 and 0.00 on Day 6 for the same "
          "six days.\n")

    print("C. Why this was abandoned:")
    print("    1. The fee total depends on WHEN you ask, not on the stream: "
          "75.00\n       at the close of Day 5, 0.00 at the close of Day 6.")
    print("    2. Removing the Day 5 answer to adopt the Day 6 one would mean "
          "deleting\n       booked fee entries -- banned by the append-only "
          "rule.")
    print("    3. Convergence is not structural. It held here with "
          f"{AED.format(margin)} to spare on\n       Day 3; a smaller E4 "
          "turns assessment into a cascade.")
    print("    Forward-only assessment has none of these properties. "
          "See AMBIGUITIES.md\n    section 2. The 50.00 AED this costs is "
          "asserted in tests/test_known_gap.py.")


if __name__ == "__main__":
    main()
