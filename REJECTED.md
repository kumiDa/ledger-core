# Refused criteria and abandoned approaches

Eight acceptance criteria were given. **Four are correct, three are wrong, and
one is true but vacuous** — its premise never holds, which makes asserting it
as given a way to look compliant while testing nothing.

| # | Criterion (abbreviated) | Verdict |
|---|---|---|
| 1 | Day 2 closing balance at end of Day 5, pre-fee, is AED −370.00 | **Accepted** |
| 2 | E7 causes exactly one overdraft fee, on Day 2 | **Refused** |
| 3 | The Day 4 settlement of Auth-A must be accepted | **Accepted** |
| 4 | Settlement with no matching authorization is rejected, funds stay | **Accepted** |
| 5 | If Auth-B is approved, its hold cuts available but not ledger balance | **Vacuous** |
| 6 | After E9, all balances *and fees* return to pre-E7 values | **Refused** |
| 7 | The three BHD instalments must each be BHD 3.334 | **Refused** |
| 8 | Any interest remainder is discarded | **Refused** |

Each refusal below names the arithmetic or the rule it breaks. Every verdict is
asserted in `tests/test_acceptance.py`, in the form the engine implements rather
than the form the brief states.

---

## 1. Accepted — Day 2 closing balance is AED −370.00

`1,200.00 − 950.00 − 620.00 = −370.00`.

E7 arrives on Day 5 carrying value date Day 2. The fee rule defines a day's
closing balance as "all entries with value_date ≤ that day", so E7 belongs to
the Day 2 balance from the moment it is booked. Evaluated at the end of Day 5,
before fees, Day 2 reads −370.00.

This criterion is about **reporting**, and the engine supports it directly:
`Journal.balance(value_date_through=2, known_through_day=5)`. The restatement
table in the replay output is this query run across every (value date, as-of
day) pair. Note that it is *only* about reporting — the criterion says nothing
about fees, which is where criterion 2 goes wrong.

---

## 2. Refused — the only fee lands on Day 5, not Day 2

> "E7 causes exactly one overdraft fee to be assessed, on Day 2."

The count is right. The day is wrong. And under the reading that would put a
fee on Day 2, the count stops being one — so **no single policy produces the
criterion as written**. That is what makes it refusable rather than merely
debatable.

**Under forward-only assessment (what this engine does).** A day's fee is
decided once, when that day closes, from the balance known at that moment. Day 2
closed on Day 2 at **+250.00** — E7 did not exist yet and could not have been
known. Day 5 closes at **−155.00**, so one fee is assessed, value-dated Day 5.
One fee, Day 5.

**Under retroactive assessment (the literal reading).** If a backdated entry can
make a closed day chargeable, then at the close of Day 5 the restated balances
are:

| Value date | Restated at end of Day 5 | Overdrawn? |
|---|---|---|
| Day 1 | +250.00 | |
| Day 2 | −370.00 | yes |
| Day 3 | +30.00 | |
| Day 4 | −155.00 | yes |
| Day 5 | −155.00 | yes |

Three overdrawn days, so **three fees, AED 75.00** — not one. Verified by
running `prototypes/retroactive_fees.py`.

So the criterion is wrong on the day under one reading and wrong on the count
under the other. The engine implements forward-only; §9 below explains why, and
`tests/test_known_gap.py` fails on purpose to record what that choice costs.

---

## 3. Accepted — the Auth-A settlement is accepted

Auth-A was approved on Day 2 for AED 200.00 and the hold was still active on
Day 4. A settlement of AED 185.00 is within it. The engine posts −185.00 value
dated Day 4, releases the hold, and marks it settled by E5.

The AED 15.00 difference between hold and settlement **moves no money**. It is
released availability, not a ledger movement — booking it would invent an entry
for a transaction that never happened. Asserted in
`test_c3_unused_hold_remainder_is_released_not_posted`.

---

## 4. Accepted — settlement without an authorization is rejected

> "Any settlement referencing an authorization ID not present in the ledger must
> be rejected and the funds must not leave the account."

Correct, and the sharpest criterion in the set, because it names the failure
mode that matters. A weaker system would "reject" the settlement while still
posting the debit, or release a hold that never existed. E6 (Auth-Z, AED 180.00)
is rejected and **writes zero entries**: `journal.entries_for_event("E6") == ()`.
Day 4 closes at 465.00, untouched by the 180.00.

The rejection is recorded as an `EventResult` with outcome `REJECTED` and
surfaces in the Day 4 error list, so the attempt is auditable without being
financial. Keeping events (requests) separate from entries (movements) is what
makes "rejected but recorded" expressible at all.

---

## 5. Vacuous — Auth-B is declined, so the criterion never fires

> "If Auth-B is approved, its hold reduces available balance but not ledger
> balance."

The consequent is a correct statement of hold semantics. The **antecedent is
false**: Auth-B is declined.

At E8 (Day 5, applied after E7 in stream order):

```
ledger balance, value_date <= Day 5   = -155.00
active holds (Auth-A released Day 4)  =    0.00
available balance                     = -155.00
available after a 90.00 hold          = -245.00   -> below zero, DECLINED
```

The approval rule requires available balance to remain "at or above zero after
the hold is applied". −245.00 is not. Auth-B never exists, holds nothing, and
posts nothing.

This is listed separately from the refusals because it is not false — it is
**unfalsifiable on this stream**. Writing `assertTrue` against a conditional
whose premise fails produces a green test that verifies nothing, which is worse
than a red one. The engine instead does two things:

- asserts the real outcome — `test_c5_auth_b_is_declined_so_the_criterion_never_fires`
- verifies the consequent where it *does* apply, on Auth-A —
  `test_c5_hold_semantics_hold_where_they_do_apply`: Day 2 ledger balance stays
  250.00 while availability drops to 50.00.

The hold semantics the criterion describes are implemented and tested. They are
just not tested via Auth-B, because Auth-B does not happen.

---

## 6. Refused — balances return after E9, fees do not

> "After E9, all balances and fees return to their pre-E7 values."

Half true, and the false half contradicts a non-negotiable rule in the same
brief.

**Balances do return.** E9 appends +620.00 value dated Day 2, so the restated
Day 2 balance goes back to +250.00 and the Day 6 movement total returns to
465.00. Asserted in `test_c6_refused_restated_day2_balance_does_return`.

**Fees do not return.** The Day 5 overdraft fee is a booked entry. The brief
states: *"The ledger is append-only. No event record is ever mutated or
deleted."* Making the fee "return to its pre-E7 value" requires either deleting
that entry or rewriting it to zero. Both are banned.

Nor can it be quietly reversed. A fee contra-entry is a *new* economic decision —
a fee waiver — not a mechanical consequence of reversing the debit. The brief
grants no waiver rule, and inventing one would mean a system that silently
refunds fees whenever a debit is reversed, regardless of why it was reversed.

So Day 6 closes at:

```
465.00  (movements, E7 and E9 netted to zero)
-25.00  (Day 5 overdraft fee -- stands)
--------
440.00  closing ledger balance
 +0.83  capitalized interest
--------
440.83
```

Pre-E7 Day 4 closed at 465.00. Day 6 closes at 440.00. They are AED 25.00
apart, permanently, and that gap is the fee. A reversal undoes a movement; it
does not undo the consequences that were booked while the movement stood.

---

## 7. Refused — three BHD instalments of 3.334 do not exist

> "The three BHD instalments in E10 must each be BHD 3.334."

```
3.334 x 3 = 10.002
```

The credit is BHD 10.000. Three instalments of 3.334 sum to 10.002, inventing
**BHD 0.002 out of nothing**. Accepting this criterion means the journal no
longer balances against the event that caused it.

The brief's own phrasing — "posted as three equal instalments" — is the deeper
problem: at BHD's three decimal places, three *equal* instalments summing to
10.000 do not exist, because 10.000 is not divisible by 3 in thousandths. One of
two properties has to go:

| Keep | Give up | Result |
|---|---|---|
| Equality | The sum | 3.334 × 3 = 10.002 — money created |
| The sum | Equality | 3.334 + 3.333 + 3.333 = 10.000 |

The engine keeps the sum. `split_evenly` allocates the floor share to every
part, then distributes the leftover quanta one each from the front:
**3.334 / 3.333 / 3.333**. No two parts differ by more than one quantum, and
the total is exact by assertion inside the function.

A ledger that cannot reproduce its own inputs is not a ledger. "Equal" is a
convenience; conservation is the invariant.

---

## 8. Refused — nothing is discarded, because no remainder can exist

> "If the rounded daily interest accruals do not sum to the capitalized total,
> the remainder is discarded."

This directly contradicts a non-negotiable rule stated two lines earlier in the
same brief: *"The rounded daily accruals must sum exactly to the capitalized
total."* A criterion whose precondition is "if the invariant is violated" cannot
be satisfied by a system that maintains the invariant.

The refusal is not just about precedence between two contradictory lines. The
criterion presumes an architecture in which the capitalized total is computed
**independently** of the daily accruals — typically as
`round(balance × rate × days)` or interest on an unrounded running total — and
then reconciled against their sum, leaving a remainder to dispose of.

This engine does not have that architecture. The capitalized credit is
*defined* as the sum of the rounded daily accruals:

```python
total = sum(self.state.accruals[account_id], account.currency.zero())
```

Equality holds **by construction**, not by reconciliation. There is no second
figure to disagree with and no remainder to discard, keep, or round away.

```
ACC-001  0.10 + 0.10 + 0.26 + 0.19 + 0.00 + 0.18 = 0.83  capitalized 0.83
ACC-002  0.000 x4 + 0.004 + 0.004            = 0.008  capitalized 0.008
```

The discrepancy the criterion anticipates is real, and it is **present on this
very stream** — which is the clearest possible reason to refuse the criterion
rather than the rule. Taking the independent route on ACC-001:

```
sum of positive closing balances   250.00 + 250.00 + 650.00 + 465.00 + 440.00 = 2,055.00
independent total   round(2,055.00 x 0.0004) = round(0.822) = 0.82
sum of rounded daily accruals                                 = 0.83
                                                          remainder = 0.01
```

So a system built the way criterion 8 presumes would capitalize AED **0.82**,
find AED 0.01 left over, discard it, and thereby violate the non-negotiable rule
that the accruals must sum exactly to the capitalized total. The remainder is not
a hypothetical edge case to be swept up — it is one fil, on a six-day window, on
the first account.

Defining the total *as* the sum removes the second figure entirely, so there is
nothing to reconcile and nothing to discard. Asserted in
`test_c8_refused_independent_formula_would_lose_a_fil`.

---

## 9. Abandoned mid-build — retroactive fee assessment

Built, measured, dropped. Kept runnable at `prototypes/retroactive_fees.py` so
this section is verifiable rather than merely asserted.

The literal reading of the fee rule makes a day's fee a function of its
*restated* balance, so a backdated entry can make a closed day chargeable later.
Fees are appended, never mutated, which keeps the append-only rule intact. The
implementation is a fixpoint loop: scan every closed day, append a fee to any day
that is overdrawn and unfeed, repeat until a pass changes nothing.

It works. Three things killed it.

**The answer depends on when you ask.** Same six days, same event stream:

| Evaluated at | Fees | Total |
|---|---|---|
| Close of Day 5 | Days 2, 4, 5 | AED 75.00 |
| Close of Day 6 (E9 included) | none | AED 0.00 |

E9's reversal makes every restated day positive, so on the final books *no day
is overdrawn at all*. The Day 2 fee was assessed on a balance that the completed
ledger says never existed. Charging it is hard to defend; un-charging it means
deleting booked entries, which is banned.

**Convergence is incidental, not structural.** Appending a fee value-dated Day 2
reduces every later day's balance by 25.00. On this stream Day 3 restates to
+30.00 and survives at **+5.00** — a margin of five dirhams. Had E4 been AED
395.00 instead of 400.00, the Day 2 fee alone would have pushed Day 3 negative,
triggering a fee that pushes Day 4 further negative, and so on. Fee assessment
stops being a function of the event stream and becomes an iteration whose
termination depends on the data. A fee engine that can cascade on an input it
has not seen yet is not shippable.

**It contradicts how overdraft fees actually work.** A bank that re-bills closed
days whenever a backdated item lands issues statements that change after the
customer has read them.

Forward-only assessment has none of these properties: one fee per day, decided
once, never revisited, and a closed day's statement stays closed. What it costs
on this stream is AED 50.00 of unassessed fees, and that cost is not buried in
prose — `tests/test_known_gap.py` asserts it and fails.

---

## 10. Abandoned mid-build — mutable running balances

The first engine kept a running balance per account and adjusted it as events
applied. It survived until E7.

A backdated entry means "the Day 2 balance" is not one number — it is a function
of two dates, the value date and the day you ask. A single running balance can
represent one of those and silently loses the other, which makes criterion 1
(Day 2 = −370.00 as seen on Day 5) literally inexpressible: the running balance
after E7 is −155.00, the *Day 5* figure, and nothing in the structure can
recover −370.00.

Replaced with derived balances: nothing is stored but entries, and every balance
is a query with both dates as parameters. `Journal.balance` takes
`value_date_through` and `known_through_day`, and the restatement table in the
replay output falls out of running that query over every pair. Slower, and
irrelevant at this scale — the correctness is the point.

---

## 11. Rejected as a design option — float arithmetic

Never built; recording it because it is the default mistake in this problem
domain. `0.0004 × 465.00` is exact in base 10 and not in base 2, and BHD's three
decimal places give rounding errors one more digit to hide in. Every amount is
`Decimal`, quantized to its own currency's precision. `Currency.parse` raises on
over-precise input rather than rounding it, so a caller's precision bug surfaces
at the boundary instead of becoming a half-fil discrepancy six days later.
