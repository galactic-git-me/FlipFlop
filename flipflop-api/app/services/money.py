"""
Money value type for type-safe currency operations.

Encapsulates currency values (GBP, USD, EUR) and prevents common pitfalls:
- Float-rounding errors in arithmetic
- Accidental unit conversions
- Silent precision loss in database storage

Usage:
    price = Money(79.99, "GBP")
    cost = Money(45.50, "GBP")
    profit = price - cost  # Money(34.49, "GBP")

    # Type-safe conversions
    usd = price.convert_to("USD", rate=1.27)  # Money(101.59, "USD")

    # Safe storage (stores as pennies internally)
    db_value = price.to_pennies()  # 7999 (pennies)
    restored = Money.from_pennies(7999, "GBP")
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
import structlog

log = structlog.get_logger(__name__)

# Supported currencies and their decimal places (default 2 for GBP, USD, EUR)
CURRENCY_DECIMALS = {
    "GBP": 2,
    "USD": 2,
    "EUR": 2,
    "JPY": 0,  # No decimals
}

# Exchange rates (loaded from config in production)
# These are examples; real rates come from live APIs or config
DEFAULT_EXCHANGE_RATES = {
    ("GBP", "USD"): Decimal("1.27"),
    ("GBP", "EUR"): Decimal("1.17"),
    ("USD", "GBP"): Decimal("0.79"),
    ("USD", "EUR"): Decimal("0.92"),
    ("EUR", "GBP"): Decimal("0.85"),
    ("EUR", "USD"): Decimal("1.09"),
}


class Money:
    """
    Immutable money value object.

    Stores currency amount as Decimal internally to avoid float precision loss.
    All arithmetic returns new Money instances (never mutates).
    """

    def __init__(self, amount: float | str | Decimal, currency: str):
        """
        Create a Money value.

        Args:
            amount: Numeric value (float, str, or Decimal)
            currency: Currency code (GBP, USD, EUR, etc.)

        Raises:
            ValueError: If currency not supported or amount invalid
        """
        if currency not in CURRENCY_DECIMALS:
            raise ValueError(f"Unsupported currency: {currency}")

        # Convert to Decimal for precision
        if isinstance(amount, str):
            self._amount = Decimal(amount)
        elif isinstance(amount, float):
            # Round float to string first to avoid float representation errors
            self._amount = Decimal(str(round(amount, CURRENCY_DECIMALS[currency])))
        else:
            self._amount = Decimal(amount)

        self._currency = currency

        # Validate amount is not negative (business rule: prices >= 0)
        if self._amount < 0:
            raise ValueError(f"Money amount cannot be negative: {self._amount}")

    @property
    def amount(self) -> Decimal:
        """Get the numeric amount as Decimal."""
        return self._amount

    @property
    def currency(self) -> str:
        """Get the currency code."""
        return self._currency

    def to_float(self) -> float:
        """Convert to float (with rounding)."""
        decimals = CURRENCY_DECIMALS[self._currency]
        return float(round(self._amount, decimals))

    def to_pennies(self) -> int:
        """
        Store as integer pennies (no precision loss).

        Used for database storage: store as INTEGER pennies, restore with from_pennies().
        """
        decimals = CURRENCY_DECIMALS[self._currency]
        factor = 10 ** decimals
        return int(self._amount * factor)

    @staticmethod
    def from_pennies(pennies: int, currency: str) -> "Money":
        """Restore Money from integer pennies."""
        decimals = CURRENCY_DECIMALS.get(currency, 2)
        factor = 10 ** decimals
        amount = Decimal(pennies) / Decimal(factor)
        return Money(amount, currency)

    def __add__(self, other: "Money") -> "Money":
        """Add two Money values (must be same currency)."""
        if not isinstance(other, Money):
            raise TypeError(f"Cannot add Money and {type(other).__name__}")
        if self._currency != other._currency:
            raise ValueError(
                f"Cannot add {self._currency} and {other._currency} "
                f"(use convert_to first)"
            )
        return Money(self._amount + other._amount, self._currency)

    def __sub__(self, other: "Money") -> "Money":
        """Subtract two Money values (must be same currency)."""
        if not isinstance(other, Money):
            raise TypeError(f"Cannot subtract Money and {type(other).__name__}")
        if self._currency != other._currency:
            raise ValueError(
                f"Cannot subtract {self._currency} and {other._currency} "
                f"(use convert_to first)"
            )
        result_amount = self._amount - other._amount
        # Allow negative intermediate results (profit calc may go negative)
        # but warn if suspiciously negative
        if result_amount < Decimal(-10000):
            log.warning(
                "Large negative Money result", amount=str(result_amount), currency=self._currency
            )
        return Money(result_amount, self._currency)

    def __mul__(self, scalar: float | Decimal | int) -> "Money":
        """Multiply Money by a scalar (e.g., 0.9 for 10% discount)."""
        if isinstance(scalar, (float, int)):
            scalar = Decimal(str(scalar))
        elif not isinstance(scalar, Decimal):
            raise TypeError(f"Cannot multiply Money by {type(scalar).__name__}")

        result = self._amount * scalar
        return Money(result, self._currency)

    def __rmul__(self, scalar: float | Decimal | int) -> "Money":
        """Support scalar * Money (e.g., 0.9 * price for discount)."""
        return self.__mul__(scalar)

    def __truediv__(self, scalar: float | Decimal | int) -> "Money":
        """Divide Money by a scalar (e.g., price / 2 for split payment)."""
        if isinstance(scalar, (float, int)):
            scalar = Decimal(str(scalar))
        elif not isinstance(scalar, Decimal):
            raise TypeError(f"Cannot divide Money by {type(scalar).__name__}")

        if scalar == 0:
            raise ValueError("Cannot divide Money by zero")

        result = self._amount / scalar
        return Money(result, self._currency)

    def convert_to(self, target_currency: str, rate: float | Decimal | None = None) -> "Money":
        """
        Convert to another currency.

        Args:
            target_currency: Target currency code
            rate: Exchange rate (e.g., 1.27 for GBP to USD)
                  If None, looks up in DEFAULT_EXCHANGE_RATES

        Returns:
            New Money instance in target currency

        Raises:
            ValueError: If no rate provided and no default exists
        """
        if self._currency == target_currency:
            return Money(self._amount, self._currency)

        if rate is None:
            # Try to find rate in defaults
            key = (self._currency, target_currency)
            if key not in DEFAULT_EXCHANGE_RATES:
                raise ValueError(
                    f"No exchange rate for {self._currency}→{target_currency}. "
                    f"Provide rate explicitly."
                )
            rate = DEFAULT_EXCHANGE_RATES[key]

        if isinstance(rate, (float, int)):
            rate = Decimal(str(rate))
        elif not isinstance(rate, Decimal):
            raise TypeError(f"Exchange rate must be numeric, got {type(rate).__name__}")

        result = self._amount * rate
        return Money(result, target_currency)

    def round(self, decimals: Optional[int] = None) -> "Money":
        """
        Round to specified decimal places.

        Args:
            decimals: Number of decimals. If None, uses currency default.

        Returns:
            New Money instance, rounded
        """
        if decimals is None:
            decimals = CURRENCY_DECIMALS[self._currency]

        quantizer = Decimal(10) ** -decimals
        rounded = self._amount.quantize(quantizer, rounding=ROUND_HALF_UP)
        return Money(rounded, self._currency)

    def __eq__(self, other: object) -> bool:
        """Compare two Money values (must be same currency)."""
        if not isinstance(other, Money):
            return NotImplemented
        return self._amount == other._amount and self._currency == other._currency

    def __lt__(self, other: "Money") -> bool:
        """Compare Money values (must be same currency)."""
        if not isinstance(other, Money):
            return NotImplemented
        if self._currency != other._currency:
            raise ValueError(
                f"Cannot compare {self._currency} and {other._currency}"
            )
        return self._amount < other._amount

    def __le__(self, other: "Money") -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        if self._currency != other._currency:
            raise ValueError(f"Cannot compare {self._currency} and {other._currency}")
        return self._amount <= other._amount

    def __gt__(self, other: "Money") -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        if self._currency != other._currency:
            raise ValueError(f"Cannot compare {self._currency} and {other._currency}")
        return self._amount > other._amount

    def __ge__(self, other: "Money") -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        if self._currency != other._currency:
            raise ValueError(f"Cannot compare {self._currency} and {other._currency}")
        return self._amount >= other._amount

    def __hash__(self) -> int:
        """Hash for use in sets/dicts."""
        return hash((self._amount, self._currency))

    def __repr__(self) -> str:
        """String representation."""
        return f"Money({self._amount}, '{self._currency}')"

    def __str__(self) -> str:
        """Display as currency string (e.g., £79.99)."""
        symbol = {"GBP": "£", "USD": "$", "EUR": "€"}.get(self._currency, self._currency)
        return f"{symbol}{self.to_float():.2f}"
