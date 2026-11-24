"""
Tests for Money value type.

Verifies:
1. Immutability and precision (no float rounding errors)
2. Type-safe arithmetic (same currency only)
3. Currency conversions
4. Database storage (pennies encoding)
5. Business logic (pricing calculations)
"""

import pytest
from decimal import Decimal
from app.services.money import Money, CURRENCY_DECIMALS


@pytest.mark.unit
class TestMoneyCreation:
    """Test Money value creation and initialization."""

    def test_create_from_float(self):
        """Create Money from float."""
        m = Money(79.99, "GBP")
        assert m.amount == Decimal("79.99")
        assert m.currency == "GBP"

    def test_create_from_string(self):
        """Create Money from string (precise)."""
        m = Money("79.99", "GBP")
        assert m.amount == Decimal("79.99")

    def test_create_from_decimal(self):
        """Create Money from Decimal."""
        m = Money(Decimal("79.99"), "GBP")
        assert m.amount == Decimal("79.99")

    def test_supports_multiple_currencies(self):
        """Money supports GBP, USD, EUR."""
        gbp = Money(100, "GBP")
        usd = Money(100, "USD")
        eur = Money(100, "EUR")
        assert gbp.currency == "GBP"
        assert usd.currency == "USD"
        assert eur.currency == "EUR"

    def test_rejects_unsupported_currency(self):
        """Unsupported currency raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported currency"):
            Money(100, "XYZ")

    def test_rejects_negative_amount(self):
        """Negative amount raises ValueError."""
        with pytest.raises(ValueError, match="cannot be negative"):
            Money(-50, "GBP")

    def test_zero_amount_allowed(self):
        """Zero is allowed (free item)."""
        m = Money(0, "GBP")
        assert m.amount == Decimal("0")


@pytest.mark.unit
class TestMoneyPrecision:
    """Test that Money prevents float precision loss."""

    def test_avoids_float_rounding_error(self):
        """0.1 + 0.2 = 0.3 (exact, not 0.30000000000000004)."""
        m1 = Money(0.1, "GBP")
        m2 = Money(0.2, "GBP")
        result = m1 + m2
        assert result.amount == Decimal("0.3")

    def test_pennies_storage_no_loss(self):
        """Store as pennies, restore with 100% precision."""
        original = Money(Decimal("79.99"), "GBP")
        pennies = original.to_pennies()
        assert pennies == 7999
        restored = Money.from_pennies(pennies, "GBP")
        assert restored == original

    def test_many_decimal_operations_no_drift(self):
        """Repeated operations don't accumulate rounding errors."""
        base = Money(100, "GBP")
        # Divide by 3, multiply by 3 (should round-trip)
        third = base / 3  # 33.33...
        triple = third * 3  # Should be back to ~100
        assert abs(triple.amount - Decimal("100")) < Decimal("0.01")


@pytest.mark.unit
class TestMoneyArithmetic:
    """Test arithmetic operations (addition, subtraction, multiplication)."""

    def test_add_same_currency(self):
        """Add two Money values of same currency."""
        m1 = Money(50, "GBP")
        m2 = Money(30, "GBP")
        result = m1 + m2
        assert result == Money(80, "GBP")

    def test_add_different_currency_raises(self):
        """Adding different currencies raises error (use convert_to first)."""
        gbp = Money(50, "GBP")
        usd = Money(50, "USD")
        with pytest.raises(ValueError, match="Cannot add"):
            gbp + usd

    def test_subtract_same_currency(self):
        """Subtract two Money values."""
        m1 = Money(80, "GBP")
        m2 = Money(30, "GBP")
        result = m1 - m2
        assert result == Money(50, "GBP")

    def test_multiply_by_scalar(self):
        """Multiply Money by scalar (discount, markup, etc.)."""
        price = Money(100, "GBP")
        discounted = price * 0.9  # 10% off
        assert discounted == Money(90, "GBP")

    def test_scalar_multiply_money(self):
        """Support scalar * Money (commutative)."""
        price = Money(100, "GBP")
        discounted = 0.9 * price
        assert discounted == Money(90, "GBP")

    def test_divide_by_scalar(self):
        """Divide Money by scalar (split payment, etc.)."""
        total = Money(100, "GBP")
        per_person = total / 5
        assert per_person == Money(20, "GBP")

    def test_divide_by_zero_raises(self):
        """Division by zero raises ValueError."""
        m = Money(100, "GBP")
        with pytest.raises(ValueError, match="divide.*zero"):
            m / 0

    def test_immutability(self):
        """Money is immutable (arithmetic returns new instances)."""
        original = Money(100, "GBP")
        result = original * 0.9
        assert original == Money(100, "GBP")  # Unchanged
        assert result == Money(90, "GBP")


@pytest.mark.unit
class TestMoneyConversions:
    """Test currency conversions."""

    def test_convert_gbp_to_usd_with_rate(self):
        """Convert GBP to USD with explicit rate."""
        gbp = Money(100, "GBP")
        usd = gbp.convert_to("USD", rate=1.27)
        assert usd.currency == "USD"
        assert usd.amount == Decimal("127")

    def test_convert_uses_default_rate(self):
        """If no rate provided, uses DEFAULT_EXCHANGE_RATES."""
        gbp = Money(100, "GBP")
        usd = gbp.convert_to("USD")  # No rate argument
        # Default rate is 1.27
        assert usd.amount == Decimal("127")

    def test_convert_same_currency_no_op(self):
        """Converting to same currency is identity."""
        gbp = Money(100, "GBP")
        same = gbp.convert_to("GBP")
        assert same == gbp

    def test_convert_missing_rate_raises(self):
        """Missing rate and no default raises ValueError."""
        gbp = Money(100, "GBP")
        with pytest.raises(ValueError, match="No exchange rate"):
            gbp.convert_to("JPY")  # No default rate

    def test_round_trip_conversion(self):
        """Convert GBP → USD → GBP (with reverse rate)."""
        original = Money(100, "GBP")
        usd = original.convert_to("USD", rate=1.27)
        gbp_back = usd.convert_to("GBP", rate=Decimal("0.79"))
        # Should be close to original (some rounding)
        assert abs(gbp_back.amount - Decimal("100")) < Decimal("1")


@pytest.mark.unit
class TestMoneyComparison:
    """Test comparison operations."""

    def test_equality(self):
        """Two Money values with same amount and currency are equal."""
        m1 = Money(79.99, "GBP")
        m2 = Money("79.99", "GBP")
        assert m1 == m2

    def test_inequality(self):
        """Different amounts are not equal."""
        m1 = Money(79.99, "GBP")
        m2 = Money(80.00, "GBP")
        assert m1 != m2

    def test_different_currency_not_equal(self):
        """Same amount, different currency, not equal."""
        gbp = Money(100, "GBP")
        usd = Money(100, "USD")
        assert gbp != usd

    def test_less_than(self):
        """Less-than comparison."""
        m1 = Money(50, "GBP")
        m2 = Money(100, "GBP")
        assert m1 < m2
        assert not (m2 < m1)

    def test_less_than_different_currency_raises(self):
        """Comparing different currencies raises ValueError."""
        gbp = Money(100, "GBP")
        usd = Money(100, "USD")
        with pytest.raises(ValueError, match="Cannot compare"):
            gbp < usd

    def test_hash_allows_use_in_sets(self):
        """Money instances can be used in sets/dicts."""
        m1 = Money(100, "GBP")
        m2 = Money(100, "GBP")
        m3 = Money(200, "GBP")
        s = {m1, m2, m3}
        assert len(s) == 2  # m1 and m2 are same


@pytest.mark.unit
class TestMoneyRounding:
    """Test rounding behavior."""

    def test_round_to_default_decimals(self):
        """Round to currency's default decimal places."""
        m = Money(79.996, "GBP")
        rounded = m.round()
        assert rounded.amount == Decimal("80.00")

    def test_round_to_custom_decimals(self):
        """Round to custom decimal places."""
        m = Money(79.9567, "GBP")
        rounded = m.round(decimals=1)
        assert rounded.amount == Decimal("80.0")


@pytest.mark.unit
class TestMoneyDisplay:
    """Test string representation."""

    def test_str_shows_currency_symbol(self):
        """String shows formatted currency (e.g., £79.99)."""
        m = Money(79.99, "GBP")
        assert "79.99" in str(m)
        assert "£" in str(m)

    def test_repr_shows_constructor(self):
        """Repr shows constructor for debugging."""
        m = Money(79.99, "GBP")
        assert "Money" in repr(m)
        assert "79.99" in repr(m)


@pytest.mark.unit
class TestMoneyBusinessLogic:
    """Test real-world pricing calculations."""

    def test_profit_calculation(self):
        """Calculate profit = selling price - cost."""
        selling_price = Money(99.99, "GBP")
        cost = Money(60.00, "GBP")
        profit = selling_price - cost
        assert profit == Money(39.99, "GBP")

    def test_markup_calculation(self):
        """Calculate markup = cost * (1 + markup_pct)."""
        cost = Money(50, "GBP")
        marked_up = cost * 1.5  # 50% markup
        assert marked_up == Money(75, "GBP")

    def test_discount_calculation(self):
        """Calculate discount = price * (1 - discount_pct)."""
        original_price = Money(100, "GBP")
        discounted = original_price * 0.9  # 10% off
        assert discounted == Money(90, "GBP")

    def test_split_payment(self):
        """Split total among multiple parties."""
        total = Money(150, "GBP")
        per_person = total / 3
        assert per_person.amount == Decimal("50")

    def test_fee_calculation(self):
        """Calculate fees and margin."""
        sale_price = Money(100, "GBP")
        fee_rate = 0.0275  # 2.75% eBay fee
        fee = sale_price * fee_rate
        # 100 * 0.0275 = 2.75
        assert fee.amount == Decimal("2.75")
