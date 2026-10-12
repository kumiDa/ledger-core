#!/usr/bin/env python3
"""Replay the six-day event stream and print the per-day report.

    python3 replay.py
"""

from ledger.engine import Engine
from ledger.report import render
from scenario import ACCOUNTS, EVENTS


def main() -> None:
    state = Engine(ACCOUNTS).replay(EVENTS)
    print(render(state))


if __name__ == "__main__":
    main()
