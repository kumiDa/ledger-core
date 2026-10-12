"""Human-readable rendering of a replay. Printing only; no logic lives here."""

from .engine import Outcome, ReplayResult

RULE = "=" * 78
THIN = "-" * 78


def render(state: ReplayResult) -> str:
    out: list[str] = [RULE, "SIX-DAY LEDGER REPLAY".center(78), RULE, ""]

    for account in state.accounts.values():
        out.append(f"  {account.id}  {account.currency.code} "
                   f"({account.currency.places} dp)  opening "
                   f"{account.currency.format(account.opening_balance)}")
    out.append("")

    for day in sorted(state.days):
        out += [RULE, f"DAY {day}", RULE]

        events = [r for r in state.results if r.day == day]
        out.append("  Events")
        if not events:
            out.append("    (none)")
        for r in events:
            out.append(f"    {r.event_id:<4} {r.type:<14} {r.outcome.value:<9} {r.detail}")

        errors = [r for r in events if r.is_error]
        declines = [r for r in events if r.outcome is Outcome.DECLINED]
        out.append("")
        out.append("  Authorization states")
        holds = [h for h in state.holds.values()
                 if h.placed_day <= day and (h.released_day is None or h.released_day >= day)]
        if not holds and not declines:
            out.append("    (no holds, no decisions)")
        for h in holds:
            currency = state.accounts[h.account_id].currency
            status = ("ACTIVE" if h.released_day is None or h.released_day > day
                      else f"RELEASED (settled by {h.settled_by})")
            out.append(f"    {h.auth_id:<8} {currency.format(h.amount):>16}  "
                       f"placed day {h.placed_day}  {status}")
        for r in declines:
            out.append(f"    {r.event_id:<8} {'DECLINED':>16}  {r.detail}")

        out.append("")
        out.append("  Errors")
        if not errors:
            out.append("    (none)")
        for r in errors:
            out.append(f"    {r.event_id}: {r.detail}")

        out.append("")
        out.append("  Closing position")
        for report in state.days[day]:
            currency = state.accounts[report.account_id].currency
            fee = (currency.format(report.fee_assessed)
                   if report.fee_assessed else "none")
            out.append(f"    {report.account_id}")
            out.append(f"      closing ledger balance (pre-fee) "
                       f"{currency.format(report.closing_before_fee):>18}")
            out.append(f"      overdraft fee assessed           {fee:>18}")
            out.append(f"      closing ledger balance           "
                       f"{currency.format(report.closing_balance):>18}")
            out.append(f"      active holds                     "
                       f"{currency.format(report.active_holds):>18}")
            out.append(f"      available balance                "
                       f"{currency.format(report.available_balance):>18}")
            out.append(f"      interest accrued today           "
                       f"{currency.format(report.interest_accrued):>18}")
            if report.closing_after_capitalization is not None:
                out.append(f"      interest capitalized             "
                           f"{currency.format(report.capitalized_interest):>18}")
                out.append(f"      closing after capitalization     "
                           f"{currency.format(report.closing_after_capitalization):>18}")
        out.append("")

    out += [RULE, "INTEREST RECONCILIATION", RULE]
    for account_id, accruals in state.accruals.items():
        currency = state.accounts[account_id].currency
        total = sum(accruals, currency.zero())
        out.append(f"  {account_id}")
        out.append("    daily accruals  " +
                   "  ".join(f"d{i}={a}" for i, a in enumerate(accruals, 1)))
        out.append(f"    sum of accruals {currency.format(total):>18}")
        capitalized = [e for e in state.journal.for_account(account_id)
                       if e.kind == "INTEREST"]
        booked = sum((e.amount for e in capitalized), currency.zero())
        out.append(f"    capitalized     {currency.format(booked):>18}")
        out.append(f"    exact match     {'YES' if booked == total else 'NO':>18}")
    out.append("")

    out += [RULE, "RESTATEMENT (what a backdated entry does to a closed day)", RULE,
            "  Each row is one value date, read from the books as they stood at the",
            "  end of each later day. A column changing across a row is a backdated",
            "  entry landing. Fees are excluded so the balance is the pre-fee figure.",
            ""]
    account_id = "ACC-001"
    currency = state.accounts[account_id].currency
    last_day = max(state.days)
    header = "    value date  " + "".join(
        f"{'@end D' + str(d):>16}" for d in range(1, last_day + 1))
    out.append(header)
    for value_date in range(1, last_day + 1):
        cells = []
        for as_of in range(1, last_day + 1):
            if as_of < value_date:
                cells.append(f"{'-':>16}")
                continue
            amount = state.journal.balance(
                account_id, currency,
                value_date_through=value_date,
                known_through_day=as_of,
                kinds_excluded=("FEE", "INTEREST"),
            )
            cells.append(f"{currency.quantize(amount):>16}")
        out.append(f"    Day {value_date:<8}" + "".join(cells))
    out.append("")

    out += [RULE, "JOURNAL (append-only, oldest first)", RULE,
            f"  {'#':>3}  {'event':<16} {'acct':<8} {'post':>4} {'vd':>3} "
            f"{'kind':<11} {'amount':>14}  memo"]
    for e in state.journal:
        currency = state.accounts[e.account_id].currency
        out.append(f"  {e.seq:>3}  {e.event_id:<16} {e.account_id:<8} "
                   f"{e.posting_day:>4} {e.value_date:>3} {e.kind:<11} "
                   f"{currency.quantize(e.amount):>14}  {e.memo}")
    out.append(f"\n  {len(state.journal)} entries, 0 mutated, 0 deleted")
    out.append("")
    return "\n".join(out)
