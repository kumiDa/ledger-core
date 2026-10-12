"""Currency-aware exact decimal money.

Every amount in this system is a Decimal quantized to its own currency's
precision. Floats never appear: 0.04% of 465.00 is representable exactly in
base-10 and not in base-2, and an off-by-one-cent interest accrual is a real
defect in a ledger, not a rounding curiosity.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


@dataclass(frozen=True)
class Currency:
    code: str
    places: int

    @property
    def quantum(self) -> Decimal:
        """Smallest representable unit, e.g. 0.01 for AED, 0.001 for BHD."""
        return Decimal(1).scaleb(-self.places)

    def zero(self) -> Decimal:
        return self.quantize(Decimal(0))

    def quantize(self, amount: Decimal) -> Decimal:
        """Round to this currency's precision, half-up.

        Half-up (not half-even) is a deliberate choice; see NUMBERS.md.
        """
        return Decimal(amount).quantize(self.quantum, rounding=ROUND_HALF_UP)

    def parse(self, text: str) -> Decimal:
        """Build an amount from a literal, rejecting over-precise input.

        AED 1.005 is not an AED amount. Silently rounding it would let a
        caller's precision error disappear into the ledger, so it raises.
        """
        value = Decimal(text)
        if value != self.quantize(value):
            raise ValueError(
                f"{text} has more precision than {self.code} "
                f"({self.places} places) can represent"
            )
        return self.quantize(value)

    def format(self, amount: Decimal) -> str:
        return f"{self.quantize(amount):,.{self.places}f} {self.code}"


AED = Currency("AED", 2)
BHD = Currency("BHD", 3)

CURRENCIES = {c.code: c for c in (AED, BHD)}


def split_evenly(currency: Currency, total: Decimal, parts: int) -> list[Decimal]:
    """Split `total` into `parts` amounts that sum to exactly `total`.

    Largest-remainder: every part is the floor share, then the leftover
    quanta are handed out one each from the front. BHD 10.000 over three
    parts gives 3.334 / 3.333 / 3.333 -- not three equal parts, because
    three equal parts summing to 10.000 do not exist at 3 decimal places.
    Preserving the sum is the invariant that matters; equality is the one
    that gets sacrificed. See REJECTED.md (criterion 7).
    """
    if parts <= 0:
        raise ValueError("parts must be positive")
    total = currency.quantize(total)
    quantum = currency.quantum
    units = int((total / quantum).to_integral_value())
    base, remainder = divmod(abs(units), parts)
    sign = -1 if units < 0 else 1
    shares = []
    for index in range(parts):
        unit_count = base + (1 if index < remainder else 0)
        shares.append(currency.quantize(Decimal(sign * unit_count) * quantum))
    assert sum(shares, currency.zero()) == total
    return shares
