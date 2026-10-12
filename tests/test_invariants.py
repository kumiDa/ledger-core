"""Structural invariants that must hold for any event stream, not just this one."""

import dataclasses
import unittest
from decimal import Decimal

from ledger.engine import (
    DAILY_INTEREST_RATE, Account, Engine, Outcome, OVERDRAFT_FEE,
)
from ledger.events import Event, EventType as T
from ledger.money import AED, BHD, split_evenly
from scenario import ACCOUNTS, EVENTS


class AppendOnly(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = Engine(ACCOUNTS).replay(EVENTS)

    def test_entries_are_frozen(self):
        entry = next(iter(self.state.journal))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            entry.amount = Decimal("1.00")

    def test_journal_exposes_no_mutation_path(self):
        for forbidden in ("delete", "remove", "update", "pop", "clear", "insert"):
            self.assertFalse(
                hasattr(self.state.journal, forbidden),
                f"Journal must not expose .{forbidden}()",
            )

    def test_sequence_numbers_are_dense_and_strictly_increasing(self):
        seqs = [e.seq for e in self.state.journal]
        self.assertEqual(seqs, list(range(1, len(seqs) + 1)))

    def test_reversal_leaves_the_reversed_entry_intact(self):
        original = next(e for e in self.state.journal if e.event_id == "E7")
        self.assertEqual(original.amount, Decimal("-620.00"))
        reversal = next(e for e in self.state.journal if e.event_id == "E9")
        self.assertEqual(reversal.reverses_seq, original.seq)
        self.assertEqual(reversal.amount, -original.amount)
        self.assertEqual(reversal.value_date, original.value_date)
        # Both entries are on the books; the pair nets to zero.
        self.assertEqual(original.amount + reversal.amount, Decimal("0.00"))

    def test_replay_is_deterministic(self):
        again = Engine(ACCOUNTS).replay(EVENTS)
        self.assertEqual(
            [dataclasses.astuple(e) for e in self.state.journal],
            [dataclasses.astuple(e) for e in again.journal],
        )

    def test_rejected_and_declined_events_write_no_entries(self):
        for result in self.state.results:
            if result.outcome in (Outcome.REJECTED, Outcome.DECLINED):
                self.assertEqual(
                    self.state.journal.entries_for_event(result.event_id), (),
                    f"{result.event_id} must not post",
                )


class Precision(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = Engine(ACCOUNTS).replay(EVENTS)

    def test_every_entry_sits_at_its_own_currency_precision(self):
        for entry in self.state.journal:
            currency = self.state.accounts[entry.account_id].currency
            self.assertEqual(
                entry.amount, currency.quantize(entry.amount),
                f"entry #{entry.seq} carries sub-{currency.code} precision",
            )
            self.assertLessEqual(-entry.amount.as_tuple().exponent, currency.places)

    def test_aed_is_two_places_bhd_is_three(self):
        self.assertEqual((AED.places, BHD.places), (2, 3))
        self.assertEqual(AED.quantum, Decimal("0.01"))
        self.assertEqual(BHD.quantum, Decimal("0.001"))

    def test_over_precise_input_is_refused_not_rounded(self):
        with self.assertRaises(ValueError):
            AED.parse("1.005")
        with self.assertRaises(ValueError):
            BHD.parse("1.0005")

    def test_split_preserves_the_total_at_every_size(self):
        for parts in range(1, 13):
            for literal in ("10.000", "0.001", "100.000", "7.777"):
                total = BHD.parse(literal)
                shares = split_evenly(BHD, total, parts)
                self.assertEqual(len(shares), parts)
                self.assertEqual(sum(shares, BHD.zero()), total)
                # Shares differ by at most one quantum.
                self.assertLessEqual(max(shares) - min(shares), BHD.quantum)


class FeeRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = Engine(ACCOUNTS).replay(EVENTS)

    def test_at_most_one_fee_per_account_per_day(self):
        seen = set()
        for entry in self.state.journal:
            if entry.kind != "FEE":
                continue
            key = (entry.account_id, entry.value_date)
            self.assertNotIn(key, seen, f"second fee for {key}")
            seen.add(key)

    def test_fee_value_date_equals_the_day_assessed(self):
        for entry in self.state.journal:
            if entry.kind == "FEE":
                self.assertEqual(entry.value_date, entry.posting_day)

    def test_fee_is_assessed_exactly_when_the_day_closes_negative(self):
        for day, reports in self.state.days.items():
            for report in reports:
                expected = OVERDRAFT_FEE[
                    self.state.accounts[report.account_id].currency.code
                ] if report.closing_before_fee < 0 else Decimal(0)
                self.assertEqual(
                    report.fee_assessed,
                    self.state.accounts[report.account_id].currency.quantize(expected),
                    f"day {day} {report.account_id}",
                )

    def test_account_that_never_goes_negative_is_never_charged(self):
        self.assertEqual(self.state.fees_for("ACC-002"), [])
        for day in self.state.days:
            self.assertGreaterEqual(
                self.state.report(day, "ACC-002").closing_balance, Decimal("0.000")
            )


class InterestRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = Engine(ACCOUNTS).replay(EVENTS)

    def test_no_accrual_on_zero_or_negative_balances(self):
        for day, reports in self.state.days.items():
            for report in reports:
                if report.closing_balance <= 0:
                    self.assertEqual(
                        report.interest_accrued,
                        self.state.accounts[report.account_id].currency.zero(),
                        f"day {day} {report.account_id} accrued on a non-positive balance",
                    )

    def test_each_accrual_is_the_rate_applied_to_that_days_closing_balance(self):
        for day, reports in self.state.days.items():
            for report in reports:
                currency = self.state.accounts[report.account_id].currency
                expected = (currency.quantize(report.closing_balance * DAILY_INTEREST_RATE)
                            if report.closing_balance > 0 else currency.zero())
                self.assertEqual(report.interest_accrued, expected)

    def test_capitalization_is_a_single_credit_on_the_final_day(self):
        for account_id in self.state.accounts:
            interest = [e for e in self.state.journal.for_account(account_id)
                        if e.kind == "INTEREST"]
            self.assertLessEqual(len(interest), 1)
            for entry in interest:
                self.assertEqual(entry.value_date, 6)
                self.assertEqual(entry.posting_day, 6)
                self.assertGreater(entry.amount, 0)

    def test_accruals_sum_exactly_to_the_capitalized_total(self):
        for account_id, accruals in self.state.accruals.items():
            currency = self.state.accounts[account_id].currency
            booked = sum(
                (e.amount for e in self.state.journal.for_account(account_id)
                 if e.kind == "INTEREST"), currency.zero())
            self.assertEqual(booked, sum(accruals, currency.zero()))

    def test_capitalized_interest_does_not_accrue_on_itself(self):
        """Day 6's accrual is taken on the pre-capitalization balance."""
        report = self.state.report(6, "ACC-001")
        self.assertEqual(
            report.interest_accrued,
            AED.quantize(report.closing_balance * DAILY_INTEREST_RATE),
        )
        self.assertEqual(report.closing_after_capitalization, Decimal("440.83"))


class AuthorizationGate(unittest.TestCase):
    def _run(self, events, accounts=None):
        return Engine(accounts or ACCOUNTS).replay(events)

    def test_hold_taking_available_to_exactly_zero_is_approved(self):
        """"at or above zero" -- zero is approved, not declined."""
        state = self._run([
            Event("C1", 1, T.CREDIT, "ACC-001", value_date=1, amount=AED.parse("100.00")),
            Event("A1", 1, T.AUTHORIZATION, "ACC-001", value_date=1,
                  amount=AED.parse("100.00"), auth_id="Auth-X"),
        ])
        self.assertIs(state.result_for("A1").outcome, Outcome.APPROVED)
        self.assertEqual(state.report(1, "ACC-001").available_balance, Decimal("0.00"))

    def test_hold_one_fil_beyond_available_is_declined(self):
        state = self._run([
            Event("C1", 1, T.CREDIT, "ACC-001", value_date=1, amount=AED.parse("100.00")),
            Event("A1", 1, T.AUTHORIZATION, "ACC-001", value_date=1,
                  amount=AED.parse("100.01"), auth_id="Auth-X"),
        ])
        self.assertIs(state.result_for("A1").outcome, Outcome.DECLINED)

    def test_holds_stack_against_one_another(self):
        state = self._run([
            Event("C1", 1, T.CREDIT, "ACC-001", value_date=1, amount=AED.parse("100.00")),
            Event("A1", 1, T.AUTHORIZATION, "ACC-001", value_date=1,
                  amount=AED.parse("60.00"), auth_id="Auth-X"),
            Event("A2", 1, T.AUTHORIZATION, "ACC-001", value_date=1,
                  amount=AED.parse("60.00"), auth_id="Auth-Y"),
        ])
        self.assertIs(state.result_for("A1").outcome, Outcome.APPROVED)
        self.assertIs(state.result_for("A2").outcome, Outcome.DECLINED)

    def test_double_settlement_of_one_auth_is_rejected(self):
        state = self._run([
            Event("C1", 1, T.CREDIT, "ACC-001", value_date=1, amount=AED.parse("100.00")),
            Event("A1", 1, T.AUTHORIZATION, "ACC-001", value_date=1,
                  amount=AED.parse("50.00"), auth_id="Auth-X"),
            Event("S1", 2, T.SETTLEMENT, "ACC-001", value_date=2,
                  amount=AED.parse("50.00"), auth_id="Auth-X"),
            Event("S2", 3, T.SETTLEMENT, "ACC-001", value_date=3,
                  amount=AED.parse("50.00"), auth_id="Auth-X"),
        ])
        self.assertIs(state.result_for("S1").outcome, Outcome.POSTED)
        self.assertIs(state.result_for("S2").outcome, Outcome.REJECTED)
        self.assertEqual(state.journal.entries_for_event("S2"), ())

    def test_reversing_a_rejected_event_is_rejected(self):
        """E6 posted nothing, so there is nothing to reverse."""
        state = self._run(list(EVENTS) + [
            Event("E11", 6, T.REVERSAL, "ACC-001", value_date=4, reverses="E6"),
        ])
        self.assertIs(state.result_for("E11").outcome, Outcome.REJECTED)

    def test_double_reversal_is_rejected(self):
        state = self._run(list(EVENTS) + [
            Event("E12", 6, T.REVERSAL, "ACC-001", value_date=2, reverses="E7"),
        ])
        self.assertIs(state.result_for("E9").outcome, Outcome.POSTED)
        self.assertIs(state.result_for("E12").outcome, Outcome.REJECTED)


class EventValidation(unittest.TestCase):
    def test_signed_amounts_are_refused(self):
        with self.assertRaises(ValueError):
            Event("X", 1, T.DEBIT, "ACC-001", value_date=1, amount=Decimal("-5.00"))

    def test_settlement_without_auth_id_is_refused(self):
        with self.assertRaises(ValueError):
            Event("X", 1, T.SETTLEMENT, "ACC-001", value_date=1, amount=Decimal("5.00"))

    def test_reversal_without_a_target_is_refused(self):
        with self.assertRaises(ValueError):
            Event("X", 1, T.REVERSAL, "ACC-001", value_date=1)

    def test_opening_balances_are_zero_as_specified(self):
        state = Engine(ACCOUNTS).replay([])
        self.assertEqual(state.report(1, "ACC-001").closing_balance, Decimal("0.00"))
        self.assertEqual(state.report(1, "ACC-002").closing_balance, Decimal("0.000"))
        # A zero opening balance writes no entry at all.
        self.assertEqual(len(state.journal), 0)


if __name__ == "__main__":
    unittest.main()
