"""Versioned, server-authored commercial policy for one canonical Playbook cell."""
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.commerce_pricing import Condition

Money = Annotated[Decimal, Field(ge=0, allow_inf_nan=False, decimal_places=2)]
Rate = Annotated[Decimal, Field(ge=0, lt=1, allow_inf_nan=False)]
Mode = Literal["fast_track", "standard", "flexible"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OperatingCosts(StrictModel):
    """GBP costs net of recoverable VAT; zero must be supplied explicitly."""
    build_labour: Money
    packaging: Money
    outbound_delivery: Money
    insurance: Money
    payment_fixed: Money
    expected_failure_cost: Money
    allocated_overhead: Money
    other_variable_costs: Money


class ModePolicy(StrictModel):
    costs: OperatingCosts
    minimum_contribution_gbp: Money
    minimum_margin_fraction: Annotated[Decimal, Field(ge=Decimal("0.10"), lt=1, allow_inf_nan=False)]
    premium_gbp: Money
    # Includes queue, assembly, QA and packing, after the slowest part arrives.
    workshop_working_days: int = Field(ge=1, le=60)
    courier_working_days: int = Field(ge=1, le=30)
    maximum_delivery_working_days: int | None = Field(ge=1, le=90)


class MarketPolicy(StrictModel):
    condition: Condition
    sold_median_gbp: Money | None = None
    sold_p75_gbp: Money | None = None
    sold_sample_size: int = Field(ge=0)
    minimum_sold_sample_size: int | None = Field(default=None, ge=8)
    cap_method: Literal["sold_p75_linear_interpolation"] | None = None
    observed_at: str
    evidence_source: str = Field(min_length=1, max_length=160)
    evidence_ref: str = Field(min_length=1, max_length=500)

    @field_validator("observed_at")
    @classmethod
    def aware_observation(cls, value):
        if datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is None:
            raise ValueError("Market observation must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_high_end_cap_evidence(self):
        cap_fields = (self.sold_p75_gbp, self.minimum_sold_sample_size, self.cap_method)
        if any(value is not None for value in cap_fields):
            if (self.sold_p75_gbp is None or self.sold_sample_size < 8
                    or self.minimum_sold_sample_size != 8 or self.cap_method != "sold_p75_linear_interpolation"):
                raise ValueError("A High-end market cap requires the reviewed P75 method and at least eight sold comparisons")
        elif self.sold_median_gbp is None or self.sold_sample_size < 3:
            raise ValueError("Market evidence requires a median and at least three sold comparisons")
        return self

class CellCommercialPolicy(StrictModel):
    version: int = Field(ge=1)
    definition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    # Exact product keys, including case and any separately procured licence.
    required_part_keys: list[str] = Field(min_length=1, max_length=40)
    # Supplier evidence records a unit price; BOM quantities are server-owned.
    part_quantities: dict[str, Annotated[int, Field(strict=True, ge=1, le=128)]] = Field(default_factory=dict)
    condition: Condition
    vat_rate: Decimal = Field(ge=0, le=1, allow_inf_nan=False)
    payment_rate: Rate
    warranty_rate: Decimal = Field(ge=Decimal("0.05"), lt=1, allow_inf_nan=False)
    returns_rate: Rate
    market_tolerance_fraction: Decimal = Field(default=0, ge=0, le=Decimal("0.25"), allow_inf_nan=False)
    # Optional comparable-PC ceiling; supplier/catalogue costs own pricing.
    market: MarketPolicy | None = None
    modes: dict[Mode, ModePolicy]
    enabled_modes: list[Mode] = Field(default_factory=lambda: ["fast_track", "standard", "flexible"], min_length=1, max_length=3)
    checkout_enabled: bool = False
    # Explicitly reviewed catalogue selection -> exact supplier product key.
    checkout_slot_parts: dict[int, tuple[int, str]] = Field(default_factory=dict)
    checkout_case: tuple[int, str] | None = None

    @model_validator(mode="after")
    def validate_policy(self):
        if len(set(self.enabled_modes)) != len(self.enabled_modes):
            raise ValueError("Enabled delivery modes must be unique")
        keys = self.required_part_keys
        if set(self.part_quantities)-set(keys):
            raise ValueError("Quantities must reference exact required BOM product keys")
        if len(set(keys)) != len(keys) or any(not key.strip() or len(key) > 160 for key in keys):
            raise ValueError("Part keys must be nonblank, unique and at most 160 characters")
        if set(self.modes) != {"fast_track", "standard", "flexible"}:
            raise ValueError("All three delivery modes require explicit policy")
        if any(self.modes[name].maximum_delivery_working_days is None for name in ('fast_track','standard')):
            raise ValueError("Fast Track and Standard require an explicit delivery promise")
        if self.market is not None and self.market.condition != self.condition:
            raise ValueError("Sold-market condition must match the selected build")
        net_fraction = Decimal(1) / (1 + self.vat_rate)
        rates = self.payment_rate + self.warranty_rate + self.returns_rate
        for mode in self.modes.values():
            if net_fraction * (1 - mode.minimum_margin_fraction) - rates < Decimal("0.01"):
                raise ValueError("Sale-based costs and margin leave insufficient revenue to price safely")
        if self.checkout_enabled:
            if not self.checkout_slot_parts or self.checkout_case is None:
                raise ValueError("Checkout requires reviewed slot and case mappings")
            mapped = [part for _, part in self.checkout_slot_parts.values()] + [self.checkout_case[1]]
            if len(set(mapped)) != len(mapped) or set(mapped) != set(keys):
                raise ValueError("Checkout mappings must cover each exact BOM product once")
            if self.checkout_case[0] <= 0 or any(slot <= 0 or variant <= 0 for slot, (variant, _) in self.checkout_slot_parts.items()):
                raise ValueError("Checkout catalogue identifiers must be positive")
            if self.condition != Condition.NEW:
                raise ValueError("Customer checkout currently supports new-condition builds only")
        return self
