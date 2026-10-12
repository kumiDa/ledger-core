"""In-memory account ledger core.

Append-only journal, two-date entries (posting day and value date), exact
decimal money at each currency's own precision. No persistence, no web layer,
no database -- see README.md.
"""
