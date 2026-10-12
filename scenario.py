"""The six-day event stream under test, transcribed from the brief.

Nothing here is computed; it is the input, verbatim. Ordering within a day
is the order given in the brief, and that ordering is load-bearing: E7
(Day 5 debit) is applied before E8 (Day 5 authorization), which is why
Auth-B is tested against a balance E7 has already driven negative.
"""

from ledger.engine import Account
from ledger.events import Event, EventType as T
from ledger.money import AED, BHD

ACCOUNTS = [
    Account("ACC-001", AED, AED.parse("0.00")),
    Account("ACC-002", BHD, BHD.parse("0.000")),
]

EVENTS = [
    Event("E1", 1, T.CREDIT, "ACC-001", value_date=1, amount=AED.parse("1200.00")),
    Event("E2", 1, T.DEBIT, "ACC-001", value_date=1, amount=AED.parse("950.00")),
    Event("E3", 2, T.AUTHORIZATION, "ACC-001", value_date=2,
          amount=AED.parse("200.00"), auth_id="Auth-A"),
    Event("E4", 3, T.CREDIT, "ACC-001", value_date=3, amount=AED.parse("400.00")),
    Event("E5", 4, T.SETTLEMENT, "ACC-001", value_date=4,
          amount=AED.parse("185.00"), auth_id="Auth-A"),
    # Auth-Z has no preceding authorization event anywhere in the stream.
    Event("E6", 4, T.SETTLEMENT, "ACC-001", value_date=4,
          amount=AED.parse("180.00"), auth_id="Auth-Z"),
    # Booked on Day 5, value-dated back to Day 2.
    Event("E7", 5, T.DEBIT, "ACC-001", value_date=2, amount=AED.parse("620.00")),
    Event("E8", 5, T.AUTHORIZATION, "ACC-001", value_date=5,
          amount=AED.parse("90.00"), auth_id="Auth-B"),
    Event("E9", 6, T.REVERSAL, "ACC-001", value_date=2, reverses="E7"),
    Event("E10", 5, T.CREDIT, "ACC-002", value_date=5,
          amount=BHD.parse("10.000"), instalments=3),
]
