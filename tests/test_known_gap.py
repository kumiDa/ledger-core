"""ONE DELIBERATELY FAILING TEST.

This module is expected to fail. It is not a bug awaiting a fix in the next
commit; it is the strongest argument against a decision this engine makes on
purpose, written as an executable assertion so the cost stays measurable
instead of becoming a paragraph nobody rereads.

Run it on its own:

    python3 -m unittest tests.test_known_gap -v

See AMBIGUITIES.md section 2 for the decision and REJECTED.md section 9 for
the alternative that was built and then abandoned.
"""

import unittest
from decimal import Decimal

from ledger.engine import Engine
from ledger.money import AED
from scenario import ACCOUNTS, EVENTS


class RetroactiveOverdraftGap(unittest.TestCase):
    """The hole that forward-only fee assessment leaves open."""

    @classmethod
    def setUpClass(cls):
        cls.state = Engine(ACCOUNTS).replay(EVENTS)

    def _restated(self, value_date: int, as_of_day: int) -> Decimal:
        return self.state.journal.balance(
            "ACC-001", AED,
            value_date_through=value_date,
            known_through_day=as_of_day,
            kinds_excluded=("FEE", "INTEREST"),
        )

    def test_the_gap_is_real_before_we_assert_on_it(self):
        """Passes. Establishes the premise: three days were overdrawn.

        At the close of Day 5, with E7 (value-dated Day 2) on the books, the
        restated balances are:

            Day 1   +250.00
            Day 2   -370.00   <-- overdrawn
            Day 3    +30.00
            Day 4   -155.00   <-- overdrawn
            Day 5   -155.00   <-- overdrawn, and the only one charged

        The customer's Day 2 and Day 4 positions were negative in the
        restated books. Those two days carry no fee.
        """
        self.assertEqual(self._restated(2, as_of_day=5), Decimal("-370.00"))
        self.assertEqual(self._restated(3, as_of_day=5), Decimal("30.00"))
        self.assertEqual(self._restated(4, as_of_day=5), Decimal("-155.00"))
        self.assertEqual(len(self.state.fees_for("ACC-001")), 1)

    def test_FAILS_overdrawn_days_should_each_carry_a_fee(self):
        """FAILS. Asserts 75.00 of fees; the engine books 25.00.

        What it reveals
        ---------------
        The brief makes two statements that cannot both be fully honoured:

          (a) "assessed once per day per account when that day's closing
               ledger balance (all entries with value_date <= that day) is
               negative"
          (b) "The ledger is append-only. No event record is ever mutated
               or deleted."

        Read (a) literally and a day's fee is a function of its *restated*
        balance, which a backdated entry can change at any later time. So
        E7's arrival on Day 5 makes Day 2 and Day 4 retroactively overdrawn,
        and (a) says they are each chargeable.

        This engine assesses forward-only -- a day's fee is decided once, at
        that day's close, from the balance known then -- so Day 2 and Day 4
        are never charged. That is a defensible banking policy and it keeps
        closed days stable, but it is not what (a) literally says, and the
        difference is 50.00 AED of fee revenue on this stream alone.

        Why it is left failing rather than fixed
        ----------------------------------------
        Fixing it costs more than it buys, and the cost is not obvious:

          1. Re-deciding a closed day's fee requires either mutating the
             fee entry (banned by (b)) or appending a Day-5-posted fee
             value-dated Day 2. The second is legal, but a fee value-dated
             Day 2 *changes the Day 2 balance*, which can push a neighbouring
             day negative and trigger another fee, which can push another --
             fee assessment stops being a function of the stream and becomes
             a fixpoint iteration. I built that; see REJECTED.md section 9.
          2. Under retroactive assessment, E9's reversal on Day 6 makes the
             restated Day 2 positive again (+250.00). The Day 2 fee was then
             assessed on a balance that, on the final books, never existed.
             Charging it is arguably wrong; un-charging it violates (b).
          3. Real overdraft practice sides with forward-only. A bank that
             re-bills closed days every time a backdated item lands produces
             statements that change after they are issued.

        What would change my mind: a rule in the brief stating whether a
        closed day is re-assessable, and if so whether a later reversal
        un-assesses it. Both readings are self-consistent; the brief picks
        neither, so the engine picks the conservative one and this test
        records the bill for that choice.
        """
        # Days 1-5 only: at the close of Day 5, Day 6 is not a closed day
        # and has no balance to assess.
        overdrawn_days = [
            day for day in range(1, 6)
            if self._restated(day, as_of_day=5) < 0
        ]
        self.assertEqual(overdrawn_days, [2, 4, 5])

        expected_fees_under_literal_reading = Decimal("25.00") * len(overdrawn_days)
        booked = -sum(
            (e.amount for e in self.state.fees_for("ACC-001")), Decimal("0.00")
        )

        self.assertEqual(
            booked,
            expected_fees_under_literal_reading,
            msg=(
                f"\n\n  EXPECTED (literal reading of the fee rule): "
                f"{expected_fees_under_literal_reading} AED across days "
                f"{overdrawn_days}"
                f"\n  ACTUAL   (forward-only assessment):          "
                f"{booked} AED on day 5 only"
                f"\n  GAP:                                        "
                f"{expected_fees_under_literal_reading - booked} AED unassessed"
                "\n\n  This failure is intentional and documented. Read the"
                "\n  docstring above, AMBIGUITIES.md section 2, and"
                "\n  REJECTED.md section 9.\n"
            ),
        )


if __name__ == "__main__":
    unittest.main()
