# Ambiguities found and how each was resolved

Fourteen places where the brief admits more than one reading. Each entry states
the competing readings, the one implemented, and what would change the decision.
Where a resolution has a price, the price is named.

The first three are the ones that change the numbers. The rest change behaviour
on inputs this stream does not contain, which makes them the ones a second
reviewer would trip over.

---

## 1. "value_date ≤ that day" — two dates, not one

**The ambiguity.** The brief gives every event both a day it occurs and a
`value_date`, and for most events they match. E7 (Day 5, value date Day 2) and
E9 (Day 6, value date Day 2) separate them. Once separated, "the Day 2 balance"
stops being a number and becomes a function of *two* dates: which value dates
count, and as of when you are asking.

**Resolved.** Both dates are first-class and every entry carries both.
`posting_day` is when the ledger learned about the movement; `value_date` is
when it counts. Every balance query takes both bounds:

```python
journal.balance(account, currency,
                value_date_through=2,     # which value dates count
                known_through_day=5)      # what the books knew by then
```

Nothing is stored but entries. Every balance is derived. This is what makes
criterion 1 expressible — see REJECTED.md §10 for the mutable-running-balance
design that could not express it and was replaced.

**Cost.** Balances are O(entries) per query rather than O(1). Irrelevant at six
days; a real system would need a snapshot index, and that index would be a cache,
never the record.

---

## 2. Can a closed day grow a new fee? — the decision that moves the most money

**The ambiguity.** The fee rule says a fee is assessed "once per day per account
when that day's closing ledger balance (all entries with value_date ≤ that day)
is negative", and separately that the ledger is append-only and nothing is ever
mutated. E7 arrives on Day 5 value-dated Day 2 and makes the restated Day 2
balance −370.00. Two readings, both consistent with the words:

- **Forward-only.** A day's fee is decided at that day's close from the balance
  known then. Day 2 closed at +250.00, so Day 2 has no fee, forever.
- **Retroactive.** A day's fee follows its restated balance, so Day 2 becomes
  chargeable on Day 5.

**Resolved: forward-only.** One fee on this stream, AED 25.00, value-dated Day 5.

**Why.** The retroactive reading was fully implemented before being dropped —
`prototypes/retroactive_fees.py`, still runnable. It fails on three counts: the
fee total depends on when you ask (AED 75.00 at the close of Day 5, AED 0.00 at
the close of Day 6, because E9's reversal makes every restated day positive);
reconciling those two answers requires deleting booked entries, which the
append-only rule bans; and convergence is incidental — appending a Day 2 fee
drops every later day by 25.00, and Day 3 survives at **+5.00**, so an E4 of
395.00 instead of 400.00 would have cascaded. Full argument in REJECTED.md §9.

**Cost, stated plainly.** AED 50.00 of fees go unassessed on this stream: Day 2
and Day 4 were overdrawn in restated terms and are never charged. This is not
hidden in prose — `tests/test_known_gap.py` asserts the retroactive figure and
**fails**, so the price is in the test output every time the suite runs.

**What would change it.** One sentence in the brief saying whether a closed day
is re-assessable, and if so whether a later reversal un-assesses it. Both
readings are self-consistent; the brief picks neither.

---

## 3. "Three equal instalments" of BHD 10.000 — impossible as stated

**The ambiguity.** 10.000 is not divisible by three in thousandths. "Equal
instalments" and "sums to the credit" cannot both hold.

**Resolved: the sum wins.** `split_evenly` gives 3.334 / 3.333 / 3.333 by
largest remainder — floor share to everyone, leftover quanta one each from the
front. No two parts differ by more than one quantum and the total is exact
(asserted inside the function).

**Why.** A ledger that cannot reproduce its own inputs is broken in a way that
compounds; three parts that each look tidy but sum to 10.002 create BHD 0.002
from nothing. Equality is cosmetic, conservation is structural. This is also why
criterion 7 is refused — REJECTED.md §7.

**Unresolved sub-question.** Which instalment gets the extra fil is arbitrary.
The engine front-loads it (3.334 first) because it is deterministic and
reproducible. Back-loading or distributing by index hash would be equally valid.
If a downstream consumer cares — e.g. instalments map to dated collections — this
needs a stated rule rather than a convention.

---

## 4. Does the overdraft fee itself count toward the balance that triggers it?

**The ambiguity.** The fee is booked with value date equal to the day assessed,
so it lands *inside* the balance that justified it. Does a day whose balance is
negative only *because* of its own fee get a second fee? Does the fee feed the
next day's assessment?

**Resolved.** The trigger is evaluated on the **pre-fee** closing balance, the
fee is assessed at most once per account per day, and the resulting entry is a
normal ledger entry from then on — so it does count toward every subsequent
day's balance and toward interest.

"Once per day per account" is enforced structurally, not by an ordering
accident: the check is on the pre-fee balance and the loop visits each account
once per day. `test_at_most_one_fee_per_account_per_day` asserts no (account,
day) pair is ever charged twice.

---

## 5. Fee before interest, or interest before fee?

**The ambiguity.** Both are "end of day" and the brief does not order them. The
fee is a debit; if it lands first, interest accrues on a smaller balance.

**Resolved: fee first, then interest on the post-fee balance.**

**Why it does not matter on any input.** A fee is only assessed when the balance
is negative, and a negative balance earns no interest. A fee therefore never
reduces an interest-bearing balance — it can only deepen a balance that was
already excluded. The orderings are observationally equivalent, not just here but
in general.

Documented anyway, because "the order is immaterial" is a claim that needs the
argument above to be trustworthy, and a future change — a fee on positive
balances, say, or interest on negative ones as a debit — breaks the equivalence
immediately.

---

## 6. Interest on the ledger balance or the available balance?

**The ambiguity.** On Day 2 and Day 3 ACC-001 has a 200.00 hold. Ledger balance
is 250.00 and 650.00; available is 50.00 and 450.00. Interest on which?

**Resolved: the ledger balance**, as the brief says — "0.04% per day on the
closing ledger balance".

**Why it is worth recording.** The two readings diverge by AED 0.08 on Day 2
(0.10 vs 0.02) and AED 0.08 on Day 3 (0.26 vs 0.18) — AED 0.16 over the window,
which would capitalize as **0.67 instead of 0.83**. A real fork, not a notational
one. The brief is explicit, so there is no judgement call here — but a reader who
assumes availability (defensible: held funds are economically unavailable to the
customer) gets a different capitalized total with no error anywhere in the
output. Naming it is what stops that from looking like a bug later.

---

## 7. Is a zero balance "positive"?

**The ambiguity.** Interest is on "positive balances only". ACC-002 sits at
0.000 for four days.

**Resolved: strictly greater than zero.** Zero accrues nothing. Trivially,
0.000 × 0.0004 rounds to 0.000 either way, so no figure changes — but the
*predicate* matters for the invariant test
(`test_no_accrual_on_zero_or_negative_balances`), which would be unfalsifiable if
"positive" silently meant "non-negative".

Note the matching asymmetry in the fee rule, resolved the same way: the fee
triggers on "negative", strictly less than zero, so a day closing at exactly
0.00 is neither charged nor paid. Both boundaries are exclusive of zero.

---

## 8. "At or above zero" — is a hold to exactly zero approved?

**The ambiguity.** The authorization rule says available balance must remain
"at or above zero after the hold is applied". Inclusive or exclusive?

**Resolved: inclusive.** A hold that takes available to exactly 0.00 is
approved; one fil beyond is declined. Both boundaries asserted
(`test_hold_taking_available_to_exactly_zero_is_approved`,
`test_hold_one_fil_beyond_available_is_declined`).

The brief's wording is clear. It is listed because off-by-one on this boundary is
invisible — it only shows up on an authorization that exactly drains an account,
which no event in this stream does, so nothing but a dedicated test would catch
it.

---

## 9. Does the availability check use today's balance or the full ledger?

**The ambiguity.** When E8 tests Auth-B on Day 5, which ledger balance is the
baseline — entries with value date ≤ Day 5, or every entry on the books
regardless of value date?

**Resolved: value date ≤ the current day.** Availability is a question about
funds usable *now*, so a credit value-dated into the future is not yet spendable.

**No input distinguishes them.** Every event in this stream has
`value_date ≤ posting_day` — backdated, never forward-dated — so the two
readings agree everywhere here. The decision is therefore untested by the
scenario and rests entirely on the reasoning above. A forward-value-dated credit
is the input that would separate them, and it is the first thing I would add if
the stream grew.

---

## 10. Settlement for more than its hold

**The ambiguity.** E5 settles AED 185.00 against a 200.00 hold — under. The
brief says nothing about over-settlement.

**Resolved: post the settled amount, release the hold, flag the overage.** The
settlement is a fact arriving from outside; the hold was only ever an estimate.
Truncating a settlement to its hold would silently lose money that has actually
moved.

Under-settlement releases the unused remainder — the AED 15.00 on E5 moves no
money and books no entry, it is simply availability returned.

**Not exercised by this stream.** Over-settlement never occurs here. It is
handled, and it is the branch a reviewer should question, because "accept and
flag" is a policy choice that a card scheme might make differently.

---

## 11. Settling or re-settling an authorization twice

**The ambiguity.** Not addressed by the brief.

**Resolved: the second settlement is rejected and posts nothing.** A hold has one
lifecycle — placed, then released. Once released it cannot be consumed again. The
rejection reuses the same no-entry path as E6, so an unknown auth and an
already-settled auth behave identically from the ledger's perspective: recorded
as an error, zero financial effect. Asserted in
`test_double_settlement_of_one_auth_is_rejected`.

Authorization IDs are likewise unique — a second AUTHORIZATION reusing a live
auth ID is rejected rather than silently replacing the hold.

---

## 12. What exactly does a REVERSAL reverse?

**The ambiguity.** E9 "reverses E7". An event, not an entry — and an event can
produce several entries (E10 produces three).

**Resolved: reverse every entry the target event produced, one contra-entry
each, each carrying `reverses_seq` pointing at its original.** Reversing E10
would append three entries, not one netted entry, so the correspondence stays
one-to-one and auditable.

Two guards follow from this: reversing an event that produced **no** entries is
rejected (E6 posted nothing, so there is nothing to reverse —
`test_reversing_a_rejected_event_is_rejected`), and double reversal is rejected
(`test_double_reversal_is_rejected`). Without the first, "reversing" a rejected
settlement would credit the account AED 180.00 it never lost.

---

## 13. Which value date does a reversal take?

**The ambiguity.** E9 is specified with value date Day 2 — the same as the entry
it reverses. The brief does not say whether that is required or coincidental. A
reversal could equally take the day it is booked (Day 6).

**Resolved: the value date on the reversal event is used as given.** The engine
does not copy it from the target and does not override it with the posting day.

**Why this matters more than it looks.** The two choices are economically
different. Value-dated Day 2, E9 unwinds the restated Day 2 balance back to
+250.00 as though the debit never had effect. Value-dated Day 6, Day 2 would stay
−370.00 in restatement and only the Day 6 balance would recover — the overdraft
would remain a historical fact in the value-date dimension. The brief specifies
Day 2, so Day 2 is used; had it been silent, copying the target's value date is
the behaviour I would have defaulted to, for exactly the reason above.

---

## 14. Interest capitalizes on Day 6 — does it accrue on itself?

**The ambiguity.** Accruals "capitalize as a single credit at end of Day 6". Day
6 also has its own accrual. Order matters: capitalize first and Day 6's accrual
would be computed on a balance that already includes the capitalized interest.

**Resolved: Day 6's accrual is computed first, on the pre-capitalization
balance, then the capitalization credit is appended.** Interest does not accrue
on itself. Asserted in `test_capitalized_interest_does_not_accrue_on_itself`.

The capitalization entry is value-dated Day 6 and posted Day 6, so it appears in
the closing balance *after* capitalization (AED 440.83) but not in the figure the
Day 6 accrual was taken on (AED 440.00). The report prints both lines rather than
one, because collapsing them is how an account ends up earning interest on
interest it has not been credited yet.

---

## Non-ambiguities worth stating

Three things the brief is unambiguous about, recorded because each is a place a
reasonable implementer might "improve" on the spec:

- **AED 25.00 is a flat fee, not a rate.** No tiering by overdraft depth.
- **0.04% is a simple daily rate, not compounding.** Accruals sit outside the
  balance until Day 6, so no day's accrual earns on an earlier day's.
- **The fee is charged regardless of how deeply negative the day closed.** Day 5
  at −155.00 costs the same as a day at −1.00.
