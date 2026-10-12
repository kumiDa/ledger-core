# Worklog

Single session, 2026-10-12, 14:43–15:10 IST. The build ran 14:43–14:59; the
history was then restructured on request, which is the final entry. Timestamps
below are from `git log` and from `date` calls made during the work; they are
not reconstructed. The original commit hashes are preserved in that final
entry, which also explains why they are no longer the hashes in `git log`.

The wrong turns are in here with the rest. Three of them are arithmetic errors I
made in my own documentation and caught by checking claims I had already written
down — those are the entries worth reading.

---

## 14:43 — Read the brief, surveyed the directory, checked the toolchain

`/home/rahul/code/labs` is not a git repository and holds unrelated projects, so
`ledger-core/` is a fresh repo rather than a subdirectory of something existing.

Toolchain: Python 3.14.6, Node available, no Go or Rust. Picked Python for
`decimal` in the standard library — exact base-10 arithmetic, per-context
rounding modes, and `quantize` to a currency's precision. The brief's two
currencies at 2 and 3 decimal places with a 0.04% daily rate is a problem where
float would be wrong in a way that only surfaces in the last fil.

## 14:44 — Computed every expected figure by hand before writing any code

Wrote a throwaway script in the scratchpad (`calc.py`, not committed) to settle
the arithmetic *first*, so test expectations came from an independent
calculation rather than from whatever the engine happened to produce.

This is the step that decided the whole build. It produced:

- Day 2 restated at the end of Day 5 = **−370.00** → criterion 1 is correct
- Auth-B's availability at E8 = **−155.00**, so a 90.00 hold → −245.00 → **declined**.
  Criterion 5's premise never holds.
- `3.334 × 3 = 10.002` → criterion 7 creates BHD 0.002 → refusable on arithmetic
- Restated balances at end of Day 5 negative on days **2, 4 and 5** → criterion 2's
  "exactly one fee, on Day 2" is wrong under *both* candidate fee policies
- Day 6 closing 440.00 with the fee standing → criterion 6 is wrong about fees

Four refusals and one vacuous criterion, all identified before a line of
production code existed. Had I coded first and checked after, the natural move
would have been to make the tests agree with the brief.

## 14:44:48 — `git init`

## 14:45:41 — Money primitives and append-only journal

`ledger/money.py` and `ledger/entries.py`.

Two decisions here that the rest of the build leans on:

- `Currency.parse` **raises** on over-precise input instead of rounding it.
  `AED.parse("1.005")` is a caller error, and catching it at the boundary beats
  finding a half-fil discrepancy on Day 6.
- `Journal.balance` takes **both** `value_date_through` and `known_through_day`.
  This came directly from the 14:44 calculation — I already knew criterion 1
  needed a two-date query, so the signature was right the first time.

## 14:48:12 — Engine, scenario, report

Wrote `ledger/engine.py` with the day loop (apply events → assess fee → accrue
interest → capitalize on the final day), plus the scenario transcription and the
report renderer.

**Wrong turn, caught immediately.** I left a stub in `report.py` — a restatement
section that looped over value dates and printed nothing but a header, with a
`before = state  # readability only` line that did nothing at all. Spotted it on
first run of `replay.py` and replaced it with the real (value date × as-of day)
table. That table turned out to be the most useful thing in the output; the stub
would have shipped a section that looked implemented and wasn't.

First full run matched the 14:44 hand calculation on every figure, including
0.83 and 0.008 capitalized.

## 14:51:42 — Tests, the failing test, the abandoned prototype

42 green tests across `test_acceptance.py` (criteria, each labelled accepted or
refused) and `test_invariants.py` (append-only, precision, fee rules, interest
rules, the authorization gate at both boundaries).

**Wrong turn.** The intentionally-failing test failed on the wrong assertion. I
iterated `range(1, 7)` over restated days at `as_of_day=5`, which includes Day 6
— not a closed day at that point — so it failed on `[2,4,5,6] != [2,4,5]`, a bug
in my premise rather than the design gap I meant to expose. Narrowed to
`range(1, 6)` and it now fails on the fee comparison with the annotated message.
A deliberately-failing test failing for an accidental reason is worse than no
test at all; it looks like evidence and isn't.

**Built the thing I was about to claim I had built.** The failing test's
docstring said the retroactive fee approach "was built" — so I built it, as
`prototypes/retroactive_fees.py`, rather than leave an unverifiable claim in a
deliverable. Running it produced two findings I had not predicted:

- The literal fee rule charges **75.00 at the close of Day 5 and 0.00 at the
  close of Day 6** for the same six days, because E9's reversal makes every
  restated day positive. The fee total depends on when you ask.
- Day 3 restates to +30.00, and the Day 2 retroactive fee drops it to **+5.00**.
  It clears a cascade by five dirhams. Had E4 been 395.00 instead of 400.00, fee
  assessment would have become a self-feeding iteration.

The second one is the real argument against the approach, and I only have it
because I ran the prototype instead of reasoning about it.

## 14:53:06 — REJECTED.md

Four refusals, the vacuous criterion, and three abandoned approaches (retroactive
fees, mutable running balances, float arithmetic).

## 14:54 — Caught my own error in REJECTED.md §8

I had written that the independent interest formula gives "0.83 here by luck" and
only diverges from the daily sum in principle. Checked it rather than leaving it:

```
sum of positive closing balances = 2,055.00
round(2,055.00 x 0.0004) = round(0.822) = 0.82
sum of rounded dailies            = 0.83
```

**It diverges on this stream, by AED 0.01.** My claim was wrong and the truth is
a stronger refusal — criterion 8's "discard the remainder" would lose a fil on
six days and two accounts, not on some hypothetical edge case. Rewrote the
section around the real figure and added
`test_c8_refused_independent_formula_would_lose_a_fil` so the divergence is
asserted, not just described. 43 tests green.

## 14:56 — Wrote AMBIGUITIES.md, caught a second error

15 ambiguities. §2 (can a closed day grow a fee?) and §1 (two dates, not one) are
the ones that move money; §9–13 cover behaviour this stream never exercises,
which is where a second reviewer would disagree.

**Error caught:** §6 claimed interest-on-ledger vs interest-on-available differ
by "AED 0.08 on Day 2 and Day 3 combined". It is 0.08 on *each* day — 0.16 over
the window, capitalizing 0.67 instead of 0.83. Fixed with the per-day figures
spelled out.

## 14:57 — Wrote NUMBERS.md, caught a third error

Nine constants, each with what breaks at half and at double. (A tenth, the
report rule width, and a fifteenth ambiguity were added later during the
deliverables audit — see the final entry.) Ran the sensitivity
claims rather than asserting them, which caught the third mistake:

**Error caught:** I wrote that truncation instead of half-up takes ACC-001's
total to 0.82. It is **0.81** — truncation bites on Day 4 (0.186 → 0.18) *and*
Day 6 (0.176 → 0.17), and I had only accounted for Day 4.

Two claims that did survive checking, and are worth keeping for the asymmetry
they show: halving the rate gives 0.41, not half of 0.83 (0.415), and doubling it
gives 1.64, not 1.66. Per-day rounding makes the total non-linear in the rate —
which is exactly why the brief insists the dailies sum to the capitalized total,
and why criterion 8 had to go rather than the rule.

## 14:58 — Wrote README.md

Structured around reading the output, because the restatement table is the part
that needs explaining: rows are value dates, columns are as-of days, and a row
changing across columns is a backdated entry landing.

## 14:58:56 — README, NUMBERS, AMBIGUITIES, WORKLOG

## 14:59 — Final verification

Full `./run_tests.sh`: replay prints, 43 tests green, `test_known_gap` red as
documented with the 50.00 AED gap in its message, prototype runs.

**Wrong turn, caught on this step.** The first draft of this worklog timestamped
the README entry 15:01 and the verification 15:02 — both *ahead* of the 14:58:56
commit that contained them. Written from expectation rather than from the clock,
in the one file whose requirement is that its timestamps be real. Corrected
against `git log` and `date`.

---

## 15:10 — History restructured into one commit per capability

Done on request: the original trail was eight commits, and two of them carried
most of the build — 588 lines for engine + scenario + report together, 773 for
all three test modules plus the prototype and runner. The incremental build was
not visible inside them, and the first three commits had `.pyc` files in them
because `.gitignore` arrived late.

Rebuilt as **25 commits in dependency order**: money primitives, then the
journal, then events, then the engine one capability at a time (movements,
holds, settlement, rejection, reversal, fee, interest, capitalization,
restatement), then output, then each test group, then docs.

**How the intermediates were produced, and why they are not guesswork.** The
finished modules were sliced into named chunks by marker, and each commit
assembles the chunks that existed at that point plus hand-authored earlier
versions of the nine pieces that genuinely evolve (`Outcome`, `EventResult`,
`DayReport`, `ReplayResult`, `Engine.__init__`, `_apply`'s dispatch,
`_close_day`, `_apply_settlement`, and `replay`). Every commit is checked to
import cleanly, and the final tree is verified **byte-identical** to a snapshot
taken before the rebuild — so no intermediate can have drifted from the code
that was actually tested.

**What is and is not real about the timestamps.** The commit times on the 25
commits are rebuild times, not build times. The development record is the
session above, which is unchanged and still real. The original eight commits
were:

| Hash | Time | Subject |
|---|---|---|
| `35c97c4` | 14:45:41 | Add exact-decimal money primitives and append-only journal |
| `04ede66` | 14:48:12 | Add replay engine, six-day scenario, and per-day report |
| `07bdbd7` | 14:51:42 | Add test suite, the documented failing test, and the abandoned prototype |
| `99bcf6a` | 14:53:06 | Document the four refused criteria and the abandoned approaches |
| `7df6b93` | 14:58:56 | Add README, NUMBERS, AMBIGUITIES, and WORKLOG |
| `1b88398` | 14:59:24 | Correct forward-dated timestamps in WORKLOG |
| `ec3e966` | 14:59:59 | Correct test counts in WORKLOG and ignore bytecode |
| `f4e1e10` | 15:00:11 | Make the ledger package explicit |

Those hashes are gone from the tree, which is why the entries above no longer
cite them. The three correction commits are the reason this table is here rather
than quietly dropped: `1b88398` and `ec3e966` exist because I had written wrong
figures and a forward-dated timestamp, and a rebuilt history that hides its own
corrections would be exactly the kind of tidy fiction the restructure was not
supposed to produce. The errors stay documented in the 14:54, 14:56 and 14:57
entries.

**The honest cost of the rebuild.** The tree no longer corroborates the session
timestamps — it shows 25 commits made in one burst. Anyone reading the tree
alone sees a cleaner build than happened. That trade was made deliberately and
is recorded here rather than left to be discovered.

---

## 15:18 — Deliverables audit against the brief

Re-read the brief line by line and checked each requirement against the repo
rather than against memory. Grepped the production code for every numeric and
mode literal and diffed that list against NUMBERS.md; grepped the docs for
coverage of each non-negotiable rule.

Two real gaps found, both fixed:

**The BHD overdraft fee was an undocumented invention.** `OVERDRAFT_FEE` carries
`BHD 25.000` alongside `AED 25.00`, and NUMBERS.md §1 justified its *precision*
while silently skipping its *magnitude*. The brief prices the fee only in AED and
gives no FX rate, so carrying the numeral across currencies is an implicit 1:1
assumption between two currencies that sit roughly 1:10 at their pegs — the BHD
fee is likely an order of magnitude too large. It is never exercised, because
ACC-002 never closes negative, but unexercised is not justified. Added
AMBIGUITIES.md §15 with the three alternatives and why each is worse in kind,
and rewrote NUMBERS.md §1 to name the problem instead of stepping around it.

**One chosen constant was missing from NUMBERS.md.** The brief asks for *every*
constant; the report's 78-character rule width was not listed. Added as §10,
with a note that it lives in the render-only module and cannot touch a balance.

Everything else in the brief checks out: the four printed per-day items, the two
accounts and their precisions, all five non-negotiable rules, all ten events,
the eight criteria with four refused, the five required documents, and the one
annotated failing test.

Counts corrected across README, NUMBERS and this file (nine constants → ten,
fourteen ambiguities → fifteen).

---

## Honest assessment of what is weak

- **AMBIGUITIES.md §9 is decided by argument, not by test.** Whether availability
  uses today's value dates or the whole ledger is untestable on this stream,
  because no event is forward-value-dated. A forward-dated credit is the first
  input I would add.
- **Over-settlement is handled but never exercised.** "Accept the settlement and
  flag the overage" is a policy choice a card scheme might make differently, and
  no event in this stream settles above its hold.
- **Half-up vs half-even is not exercised either.** No accrual in this window
  lands on a tie, so the choice rests on the reasoning in NUMBERS.md §5 rather
  than on any figure in the output.
- **The BHD overdraft fee is probably wrong in magnitude** (AMBIGUITIES.md §15).
  It is latent — ACC-002 never overdraws — but if a BHD account ever closed
  negative, this engine would charge roughly ten times the intended penalty. The
  honest fix needs a per-currency fee schedule the brief does not provide.
- **Balances are O(entries) per query.** Correct and irrelevant at six days.
  A real system needs a snapshot index, and that index must be a cache, never
  the record.
- **Three of my own arithmetic claims were wrong on first writing** (14:54, 14:56,
  14:57), all in documentation rather than code, and all caught by checking
  figures I had already written down. The code was right because I calculated it
  before building; the prose was wrong where I asserted from memory instead.
  That asymmetry is the most useful thing I learned here.
