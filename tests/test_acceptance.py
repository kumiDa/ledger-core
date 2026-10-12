"""The acceptance criteria from the brief, each one labelled accepted or refused.

Criteria judged incorrect are NOT asserted as given. Each is instead
asserted in the form the engine actually implements, with the refusal
reasoned out in REJECTED.md. A test that encoded a wrong criterion would
make the suite agree with the brief and disagree with double-entry
bookkeeping.
"""

import unittest
from decimal import Decimal

from ledger.engine import Engine, Outcome
from ledger.money import AED, BHD
from scenario import ACCOUNTS, EVENTS


class AcceptanceCriteria(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = Engine(ACCOUNTS).replay(EVENTS)

    # -- Criterion 1: ACCEPTED ------------------------------------------
    def test_c1_day2_balance_at_end_of_day5_is_minus_370(self):
        """"The Day 2 closing ledger balance, evaluated at end of Day 5 and
        before any fee is assessed, is AED -370.00." -- correct.

        1200.00 - 950.00 - 620.00 = -370.00. E7 is value-dated Day 2, so it
        counts toward the Day 2 balance even though it arrived on Day 5.
        """
        engine_view = self.state.journal.balance(
            "ACC-001", AED,
            value_date_through=2,
            known_through_day=5,
            kinds_excluded=("FEE", "INTEREST"),
        )
        self.assertEqual(engine_view, Decimal("-370.00"))

    # -- Criterion 2: REFUSED -------------------------------------------
    def test_c2_refused_the_only_fee_lands_on_day5_not_day2(self):
        """"E7 causes exactly one overdraft fee to be assessed, on Day 2."
        -- REFUSED. One fee is right; Day 2 is wrong.

        The fee is assessed when a day closes negative, and Day 2 closed at
        +250.00 on Day 2. See REJECTED.md section 2.
        """
        fees = self.state.fees_for("ACC-001")
        self.assertEqual(len(fees), 1)
        self.assertEqual(fees[0].value_date, 5)
        self.assertEqual(fees[0].posting_day, 5)
        self.assertEqual(fees[0].amount, Decimal("-25.00"))

    def test_c2_refused_retroactive_reading_would_give_three_fees_not_one(self):
        """The other half of the refusal: even under full retroactive
        restatement the count is not one. At the end of Day 5 the restated
        balances are negative for Day 2, Day 4 and Day 5 (Day 3 is +30.00),
        so that policy yields three fees. Neither reading produces the
        criterion as written.
        """
        negative_days = [
            day for day in range(1, 6)
            if self.state.journal.balance(
                "ACC-001", AED, value_date_through=day, known_through_day=5,
                kinds_excluded=("FEE", "INTEREST"),
            ) < 0
        ]
        self.assertEqual(negative_days, [2, 4, 5])

    # -- Criterion 3: ACCEPTED ------------------------------------------
    def test_c3_auth_a_settlement_is_accepted(self):
        """"The Day 4 settlement of Auth-A must be accepted." -- correct.

        Auth-A was approved on Day 2 and still held 200.00; a 185.00
        settlement is within it.
        """
        result = self.state.result_for("E5")
        self.assertIs(result.outcome, Outcome.POSTED)
        self.assertEqual(len(result.entries), 1)
        self.assertEqual(result.entries[0].amount, Decimal("-185.00"))
        self.assertFalse(self.state.holds["Auth-A"].active)
        self.assertEqual(self.state.holds["Auth-A"].released_day, 4)

    def test_c3_unused_hold_remainder_is_released_not_posted(self):
        """The 15.00 difference between hold and settlement moves no money."""
        settlement_entries = self.state.journal.entries_for_event("E5")
        self.assertEqual(
            sum(e.amount for e in settlement_entries), Decimal("-185.00")
        )

    # -- Criterion 4: ACCEPTED ------------------------------------------
    def test_c4_settlement_without_authorization_is_rejected_and_posts_nothing(self):
        """"Any settlement referencing an authorization ID not present in the
        ledger must be rejected and the funds must not leave the account."
        -- correct, and the strongest criterion in the set.
        """
        result = self.state.result_for("E6")
        self.assertIs(result.outcome, Outcome.REJECTED)
        self.assertEqual(result.entries, ())
        self.assertEqual(self.state.journal.entries_for_event("E6"), ())
        self.assertNotIn("Auth-Z", self.state.holds)
        # Day 4 closes at 465.00, i.e. untouched by the 180.00.
        self.assertEqual(
            self.state.report(4, "ACC-001").closing_balance, Decimal("465.00")
        )

    # -- Criterion 5: VACUOUS (premise never holds) ---------------------
    def test_c5_auth_b_is_declined_so_the_criterion_never_fires(self):
        """"If Auth-B is approved, its hold reduces available balance but not
        ledger balance." -- true as a statement of hold semantics, but its
        premise is false: Auth-B is declined. See REJECTED.md section 5.

        At E8, available is -155.00 (E7 already applied, no active holds).
        A 90.00 hold would take it to -245.00, below zero.
        """
        result = self.state.result_for("E8")
        self.assertIs(result.outcome, Outcome.DECLINED)
        self.assertNotIn("Auth-B", self.state.holds)
        self.assertEqual(self.state.journal.entries_for_event("E8"), ())

    def test_c5_hold_semantics_hold_where_they_do_apply(self):
        """The consequent is still verified, on the authorization that was
        approved: Auth-A's hold moved available balance and left the ledger
        balance alone.
        """
        day2 = self.state.report(2, "ACC-001")
        day1 = self.state.report(1, "ACC-001")
        self.assertEqual(day2.closing_balance, day1.closing_balance)  # 250.00
        self.assertEqual(day2.active_holds, Decimal("200.00"))
        self.assertEqual(day2.available_balance, Decimal("50.00"))

    # -- Criterion 6: REFUSED -------------------------------------------
    def test_c6_refused_balances_return_but_the_fee_does_not(self):
        """"After E9, all balances and fees return to their pre-E7 values."
        -- REFUSED. Balances do; fees do not.

        The Day 5 fee is a booked entry on an append-only ledger. Reversing
        the debit that caused it does not un-assess it. Day 6 closes at
        440.00, which is the pre-E7 465.00 minus the 25.00 fee that stands.
        """
        self.assertEqual(
            self.state.report(6, "ACC-001").closing_balance, Decimal("440.00")
        )
        self.assertEqual(len(self.state.fees_for("ACC-001")), 1)
        pre_e7_day4 = self.state.report(4, "ACC-001").closing_balance
        self.assertEqual(pre_e7_day4, Decimal("465.00"))
        self.assertNotEqual(
            self.state.report(6, "ACC-001").closing_balance, pre_e7_day4
        )

    def test_c6_refused_restated_day2_balance_does_return(self):
        """The half of criterion 6 that is true, stated precisely: the
        value-date-2 balance restated at end of Day 6 is back to 250.00.
        """
        restated = self.state.journal.balance(
            "ACC-001", AED, value_date_through=2, known_through_day=6,
            kinds_excluded=("FEE", "INTEREST"),
        )
        self.assertEqual(restated, Decimal("250.00"))

    # -- Criterion 7: REFUSED -------------------------------------------
    def test_c7_refused_bhd_instalments_cannot_all_be_3_334(self):
        """"The three BHD instalments in E10 must each be BHD 3.334."
        -- REFUSED. 3.334 x 3 = 10.002, which invents 0.002 BHD.

        The engine splits largest-remainder: 3.334 / 3.333 / 3.333.
        """
        self.assertEqual(Decimal("3.334") * 3, Decimal("10.002"))
        entries = self.state.journal.entries_for_event("E10")
        self.assertEqual(len(entries), 3)
        self.assertEqual(
            [e.amount for e in entries],
            [Decimal("3.334"), Decimal("3.333"), Decimal("3.333")],
        )
        self.assertEqual(
            sum(e.amount for e in entries), BHD.parse("10.000")
        )

    # -- Criterion 8: REFUSED -------------------------------------------
    def test_c8_refused_no_remainder_is_discarded(self):
        """"If the rounded daily interest accruals do not sum to the
        capitalized total, the remainder is discarded." -- REFUSED. It
        contradicts a non-negotiable rule in the same brief.

        The capitalized credit is defined as the sum of the rounded daily
        accruals, so no remainder can exist. Equality holds by construction,
        not by reconciliation.
        """
        for account_id, accruals in self.state.accruals.items():
            currency = self.state.accounts[account_id].currency
            booked = sum(
                (e.amount for e in self.state.journal.for_account(account_id)
                 if e.kind == "INTEREST"),
                currency.zero(),
            )
            self.assertEqual(booked, sum(accruals, currency.zero()))

    def test_c8_refused_interest_figures_are_exact(self):
        self.assertEqual(
            self.state.accruals["ACC-001"],
            [Decimal(x) for x in ("0.10", "0.10", "0.26", "0.19", "0.00", "0.18")],
        )
        self.assertEqual(
            self.state.report(6, "ACC-001").capitalized_interest, Decimal("0.83")
        )
        self.assertEqual(
            self.state.accruals["ACC-002"],
            [Decimal(x) for x in
             ("0.000", "0.000", "0.000", "0.000", "0.004", "0.004")],
        )
        self.assertEqual(
            self.state.report(6, "ACC-002").capitalized_interest, Decimal("0.008")
        )


if __name__ == "__main__":
    unittest.main()


class Criterion8Divergence(unittest.TestCase):
    """The remainder criterion 8 wants to discard is real on this stream.

    Refusing criterion 8 is not a matter of preferring one of two contradictory
    lines in the brief. A system built the way the criterion presumes -- total
    computed independently of the dailies, then reconciled -- loses AED 0.01
    here, on six days, on the first account.
    """

    @classmethod
    def setUpClass(cls):
        cls.state = Engine(ACCOUNTS).replay(EVENTS)

    def test_c8_refused_independent_formula_would_lose_a_fil(self):
        positive_closings = [
            r.closing_balance for day in sorted(self.state.days)
            for r in [self.state.report(day, "ACC-001")] if r.closing_balance > 0
        ]
        independent_total = AED.quantize(
            sum(positive_closings, AED.zero()) * Decimal("0.0004")
        )
        accrual_sum = sum(self.state.accruals["ACC-001"], AED.zero())

        self.assertEqual(sum(positive_closings, AED.zero()), Decimal("2055.00"))
        self.assertEqual(independent_total, Decimal("0.82"))
        self.assertEqual(accrual_sum, Decimal("0.83"))
        # The fil that criterion 8 would have thrown away.
        self.assertEqual(accrual_sum - independent_total, Decimal("0.01"))

        # The engine capitalizes the accrual sum, so no remainder exists.
        self.assertEqual(
            self.state.report(6, "ACC-001").capitalized_interest, accrual_sum
        )
