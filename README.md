# In-memory account ledger core

A six-day account ledger replayed from an event stream. No web layer, no
persistence, no database, no UI — the journal lives in memory and the output is
a printed report.

Python 3.10+, standard library only. `Decimal` throughout; no floats touch money.

---

## Run it

Everything, in order — replay, green suite, the one intentional failure, and the
abandoned prototype:

```bash
./run_tests.sh
```

Just the per-day report:

```bash
python3 replay.py
```

Just the suite that must be green (43 tests):

```bash
python3 -m unittest tests.test_acceptance tests.test_invariants -v
```

The one test that is **supposed to fail** — see [Known gap](#the-known-gap):

```bash
python3 -m unittest tests.test_known_gap -v
```

The retroactive-fee approach that was built and abandoned:

```bash
python3 prototypes/retroactive_fees.py
```

---

## Reading the output

`replay.py` prints five sections.

### Per day, for each of the six days

```
  Events                 each event, its outcome, and why
  Authorization states   holds placed / active / released, and declines
  Errors                 events that were rejected outright
  Closing position       the four balance figures, fee, and interest
```

Outcomes are one of four, and the distinction matters:

| Outcome | Meaning | Writes entries? |
|---|---|---|
| `POSTED` | movement booked | yes |
| `APPROVED` | authorization accepted, hold placed | no |
| `DECLINED` | authorization refused on available balance | no |
| `REJECTED` | event could not be applied at all | no |

`DECLINED` and `REJECTED` both move zero money. They are separate because a
decline is a normal credit decision and a rejection is a broken reference —
E6 settles an authorization that never existed, E8 is a decline.

The closing position prints two balances that are easy to conflate:

```
closing ledger balance (pre-fee)   the figure the fee rule is tested against
closing ledger balance             after any fee, the day's actual close
active holds                       sum of holds not yet released
available balance                  ledger balance minus active holds
```

On Day 2, ACC-001 shows a ledger balance of 250.00 and an available balance of
50.00. The 200.00 Auth-A hold is the difference: a hold constrains spending
without being a movement.

### Interest reconciliation

The six daily accruals, their sum, and the capitalized credit — with an
`exact match` line. The brief requires the rounded dailies to sum exactly to the
capitalized total; this engine achieves that by *defining* the total as their
sum, so the line reads `YES` by construction rather than by reconciliation.
(This is why acceptance criterion 8 is refused — see
[REJECTED.md §8](REJECTED.md).)

### Restatement table

The part worth slowing down on.

```
    value date           @end D1         @end D2  ...        @end D5         @end D6
    Day 2                      -          250.00  ...        -370.00          250.00
```

Each **row** is a value date; each **column** is the day you are asking from. A
row that changes across columns is a backdated entry landing.

Row "Day 2" reads +250.00 from Day 2 through Day 4, then **−370.00 at the end of
Day 5** — that is E7, booked on Day 5 but value-dated Day 2 — then back to
+250.00 at the end of Day 6 when E9 reverses it. This is acceptance criterion 1,
and it is produced without rewriting any closed day: the Day 2 figure is a query
over two dates, not a stored number.

### Journal

Every entry, oldest first, with both dates, and a footer:

```
  12 entries, 0 mutated, 0 deleted
```

The journal supports exactly one operation — append. Entries are frozen
dataclasses and `Journal` exposes no delete, update, or insert; both facts are
asserted in `tests/test_invariants.py`. E7 and its E9 reversal are both present,
entries #5 and #10, netting to zero. Nothing is erased.

---

## What the numbers come out to

| | ACC-001 (AED) | ACC-002 (BHD) |
|---|---|---|
| Day 5 closing (pre-fee) | −155.00 | 10.000 |
| Day 5 overdraft fee | 25.00 | — |
| Day 6 closing | 440.00 | 10.000 |
| Capitalized interest | 0.83 | 0.008 |
| Day 6 after capitalization | **440.83** | **10.008** |

Full table in [NUMBERS.md](NUMBERS.md).

Three results that are easy to get wrong:

- **Auth-B (E8) is declined.** By Day 5 the available balance is −155.00; a
  90.00 hold would take it to −245.00, so it never exists. Acceptance criterion 5
  is phrased "if Auth-B is approved", a premise that never holds.
- **The Day 5 fee survives E9.** Reversing the debit restores the balance but not
  the fee — it is a booked entry on an append-only ledger. Day 6 closes 25.00
  below the pre-E7 position, permanently. Criterion 6 says otherwise and is
  refused.
- **The BHD instalments are 3.334 / 3.333 / 3.333**, not three equal parts.
  Three equal parts summing to 10.000 do not exist at three decimal places.
  Criterion 7 is refused.

---

## The known gap

`tests/test_known_gap.py` **fails on purpose.** It is not a bug queued for a
later commit.

The brief's fee rule, read literally, makes a day's fee a function of its
*restated* balance — so E7's arrival on Day 5 makes Day 2 and Day 4
retroactively overdrawn and chargeable. This engine assesses forward-only: a
day's fee is decided once, at that day's close, from the balance known then. The
test asserts the literal reading's AED 75.00 against the engine's AED 25.00 and
fails with a 50.00 gap.

That policy was chosen because the retroactive alternative was built, measured,
and found to produce a fee total that depends on *when you ask* — AED 75.00 at
the close of Day 5, AED 0.00 at the close of Day 6, once E9 makes every restated
day positive again. Reconciling those two answers needs booked entries deleted,
which the append-only rule forbids. Run
`python3 prototypes/retroactive_fees.py` to see it, including that Day 3 escapes
a fee cascade by only AED 5.00.

The reasoning is in [AMBIGUITIES.md §2](AMBIGUITIES.md) and
[REJECTED.md §9](REJECTED.md). The point of leaving the test red is that the
price of the decision shows up in the test output every run, instead of living
in a document nobody reopens.

---

## Layout

```
ledger/money.py      Currency, precision, rounding, exact-sum splitting
ledger/events.py     input events -- requests, validated at construction
ledger/entries.py    Entry and Journal -- append-only, as-of balance queries
ledger/engine.py     replay: day loop, holds, fees, interest, restatement
ledger/report.py     rendering only; no logic
scenario.py          the six-day event stream, transcribed from the brief
replay.py            runnable entry point
tests/               43 green, 1 intentionally red
prototypes/          the retroactive-fee approach that was abandoned
```

The split that carries the design is **events vs entries**. An event is a
request and may be approved, declined, or rejected; an entry is a movement. A
rejected settlement produces an auditable event result and zero entries, which is
what lets E6 be recorded without the funds leaving the account.

The second is **two dates on every entry**: `posting_day` (when the ledger
learned) and `value_date` (when it counts). Collapsing them makes acceptance
criterion 1 inexpressible — see [REJECTED.md §10](REJECTED.md) for the running-
balance design that was replaced because of this.

---

## Documents

| | |
|---|---|
| [NUMBERS.md](NUMBERS.md) | every constant, why that value, what breaks at half and double |
| [AMBIGUITIES.md](AMBIGUITIES.md) | 14 ambiguities in the brief and how each was resolved |
| [REJECTED.md](REJECTED.md) | 3 refused criteria, 1 vacuous one, 3 abandoned approaches |
| [WORKLOG.md](WORKLOG.md) | what was built when, including the wrong turns |
