# Every constant, and why that value and not half it

Nine constants. Four are dictated by the brief and are reproduced here with the
consequence of changing them; five are mine, and those carry the real argument.

Each entry says what the constant is, where it lives, and what breaks at half
and at double. "Why not half it" is the useful question for the chosen ones —
for the dictated ones the answer is "because the brief says so", so the entry
instead states what the value *does*, which is what matters if it is ever
renegotiated.

---

## Dictated by the brief

### 1. Overdraft fee — AED 25.00 (flat)

`ledger/engine.py: OVERDRAFT_FEE`

Given. Flat, not tiered by depth: Day 5 closing at −155.00 costs exactly what a
day closing at −1.00 would.

**At half (12.50).** Day 6 would close at 452.50 and the capitalized interest
would change, because the fee is inside the balance that Day 6's accrual is taken
on: 452.50 × 0.0004 = 0.181 → 0.18, so the total stays 0.83 by coincidence. At
AED 12.51 it would not. This coupling — fee changes interest — is the reason the
fee is a named constant rather than a literal at the one site that books it.

**Stored per currency**, as a dict keyed by currency code, with BHD 25.000
alongside AED 25.00. ACC-002 never goes negative so the BHD entry is never used
on this stream, but the alternative is a single AED-shaped literal applied to a
3-decimal account, which quantizes silently and gives the wrong precision in the
journal. The dict makes the gap a `KeyError` at the moment a third currency
appears, rather than a rounding artifact.

### 2. Daily interest rate — 0.0004 (0.04% per day)

`ledger/engine.py: DAILY_INTEREST_RATE`

Given. Written as `Decimal("0.0004")`, not `0.04 / 100`, and not a float. Simple
daily, not compounding — accruals sit outside the balance until Day 6, so no
day's accrual earns on an earlier day's.

**At half (0.0002).** ACC-001's dailies become 0.05 / 0.05 / 0.13 / 0.09 / 0.00 /
0.09 = 0.41 — which is *not* 0.83 / 2 = 0.415. Halving the rate does not halve
the total, because each day is rounded independently. That non-linearity is the
whole reason the brief insists the dailies sum exactly to the capitalized total,
and the reason §8 of REJECTED.md refuses the discard criterion.

**At double (0.0008).** 0.20 / 0.20 / 0.52 / 0.37 / 0.00 / 0.35 = 1.64, against
0.83 × 2 = 1.66. Off by two fils in the other direction, for the same reason.

### 3. AED precision — 2 decimal places

`ledger/money.py: AED = Currency("AED", 2)`

Given. Drives the quantum (0.01), the rounding of every AED amount, and the
format width.

**Not a display setting.** It is the storage precision: `AED.parse("1.005")`
raises rather than rounding, so an over-precise amount is a caller error caught
at the boundary, not a half-fil discrepancy discovered six days later.

### 4. BHD precision — 3 decimal places

`ledger/money.py: BHD = Currency("BHD", 3)`

Given, and the reason this problem has teeth. BHD 10.000 split three ways is
3.334 / 3.333 / 3.333; at 2 places it would be 3.34 / 3.33 / 3.33, and at 4
places 2.5000 / 2.5000 — different allocations, all correct for their precision.
Precision is a property of the currency, never of the system.

**The interest figure is precision-sensitive too.** BHD 10.000 × 0.0004 = 0.004
exactly at 3 places. At 2 places it would round to 0.00 and ACC-002 would earn
nothing at all over six days.

---

## Chosen

### 5. Rounding mode — ROUND_HALF_UP

`ledger/money.py: Currency.quantize`

**Chosen over half-even (banker's rounding)**, which is the more common default
in financial code and is what Python's `Decimal` uses if you do not say.

**Why half-up.** Day 4's accrual is the case: 465.00 × 0.0004 = 0.186, which both
modes round to 0.19 — no tie, so this stream never actually exercises the
difference. The choice is therefore made on grounds other than this data:
half-up is what a retail banking statement does, it is explainable to a customer
in one sentence, and it is the mode a reconciliation against an external
statement will assume. Half-even's advantage is that it does not bias a long run
of ties upward — a real advantage at scale, and the reason I would revisit this
for a portfolio rather than two accounts.

**Why it is a single chokepoint.** Every amount in the system passes through
`Currency.quantize`. There is no second rounding site, so switching modes is one
line, and no code path can round differently from the rest by accident.

**At "half it" — i.e. truncation toward zero.** Day 4's 0.186 → 0.18 and Day 6's
0.176 → 0.17, taking ACC-001's total from 0.83 to **0.81**. Interest is then
understated on every day that is not already exact, always in the bank's
favour — a systematic bias, not a rounding wash, and not defensible on a
customer-facing balance.

### 6. Interest allocation — largest remainder, front-loaded

`ledger/money.py: split_evenly`

**Chosen over three alternatives:** equal-with-drift (3.334 × 3, which creates
money and is refused as criterion 7), equal-with-plug (3.333 × 3 plus a 0.001
adjustment entry, which is four entries for a three-instalment credit), and
back-loading the remainder.

Largest remainder gives every part the floor share, then hands out the leftover
quanta one each from the front. Two properties fall out: the total is exact
(asserted inside the function), and no two parts differ by more than one quantum.

**Front-loaded over back-loaded** for no deep reason — it is deterministic and
reproducible, which is the only property that matters here. If instalments ever
map to dated collections, who gets the extra fil becomes a real question needing
a real rule. Flagged in AMBIGUITIES.md §3.

**"Half it" does not apply** to an allocation rule. The nearest thing is
splitting into 2 parts instead of 3: BHD 10.000 → 5.000 / 5.000, exact, no
remainder, and the problem disappears. The constant that creates the difficulty
is the instalment count 3 against a 3-decimal currency — which is the brief's,
not mine.

### 7. Window length — 6 days

`ledger/engine.py: WINDOW_DAYS`

Given as the window, but a **named parameter** rather than a hardcoded range,
because the engine uses it for two distinct things: the replay bound, and the
trigger for capitalization (`if day == self.window`).

**At half (3 days).** E5 through E10 fall outside the window and
`Engine.replay` raises on them rather than dropping them silently. Capitalization
would fire at the close of Day 3, crediting 0.46 — the sum of three dailies, and
still exactly equal to them, which is the property worth preserving under
reparameterization.

**At double (12 days).** Days 7–12 close on the unchanged Day 6 balance, so
ACC-001 accrues 440.00 × 0.0004 = 0.176 → 0.18 six more times, capitalizing 1.91
on Day 12. Nothing in the engine assumes six.

### 8. Fixpoint iteration cap — 50 passes

`prototypes/retroactive_fees.py: MAX_PASSES`

Lives only in the abandoned prototype. Bounds the retroactive fee loop so a
cascade terminates with `RuntimeError` instead of hanging.

**Why 50 and not 6.** Each pass can only add fees, and there are at most 6
chargeable days, so 7 passes is a hard structural bound and 50 is deliberate
slack — if the loop ever needs an eighth pass, the invariant "each pass only
adds" has been broken and I want the stack trace, not a tidy cap that masks it.
The real run converges in 2 passes.

**That this constant has to exist at all** is the argument against the approach.
Forward-only assessment needs no iteration cap, because it does not iterate.
See REJECTED.md §9.

### 9. Opening balances — AED 0.00 and BHD 0.000

`scenario.py: ACCOUNTS`

Given as zero. Handled as a special case worth naming: **a zero opening balance
writes no entry at all**. Asserted in `test_opening_balances_are_zero_as_specified`
— replaying an empty stream leaves a journal of length 0, not 2.

**Why not book a zero entry for symmetry.** A zero-amount entry is a movement
that did not happen. It would appear in the journal, in every balance query, and
in the audit trail, carrying no information. The engine books an opening entry
only for a non-zero opening balance, so the "12 entries" in the replay output are
twelve actual movements.

**At "half it"** — any non-zero opening balance changes every downstream figure,
including whether Day 5 goes negative at all. An opening balance of AED 155.00 or
more on ACC-001 means no overdraft fee, no Day 5 trigger, and the entire fee
question in this brief evaporates.

---

## The derived figures

Not constants — outputs. Listed so the expected numbers are in one place.

| | ACC-001 (AED) | ACC-002 (BHD) |
|---|---|---|
| Day 1 closing | 250.00 | 0.000 |
| Day 2 closing | 250.00 | 0.000 |
| Day 3 closing | 650.00 | 0.000 |
| Day 4 closing | 465.00 | 0.000 |
| Day 5 closing (pre-fee) | −155.00 | 10.000 |
| Day 5 fee | 25.00 | — |
| Day 5 closing | −180.00 | 10.000 |
| Day 6 closing | 440.00 | 10.000 |
| Daily accruals | 0.10, 0.10, 0.26, 0.19, 0.00, 0.18 | 0.000 ×4, 0.004, 0.004 |
| Capitalized | 0.83 | 0.008 |
| Day 6 after capitalization | 440.83 | 10.008 |

Restated Day 2 balance, as seen at the close of Day 5, pre-fee: **−370.00**
(criterion 1). As seen at the close of Day 6, after E9: **+250.00**.
