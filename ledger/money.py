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

    def format(self, amount: Decimal) -> str:
        return f"{self.quantize(amount):,.{self.places}f} {self.code}"


AED = Currency("AED", 2)
BHD = Currency("BHD", 3)

CURRENCIES = {c.code: c for c in (AED, BHD)}
