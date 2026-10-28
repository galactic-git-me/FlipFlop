"""Validate captured supplier evidence before recording commercial facts."""
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import urlsplit, urlunsplit
import re

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.services.commercial_quote_evidence import supplier_identity


class ImportEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    part_key: str = Field(min_length=1, max_length=160)
    observation_id: int = Field(gt=0)
    source_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    fees_gbp: Decimal = Field(ge=0, decimal_places=2, allow_inf_nan=False)
    risk_gbp: Decimal = Field(ge=0, decimal_places=2, allow_inf_nan=False)
    supplier_confidence: Decimal = Field(gt=0, le=1, allow_inf_nan=False)
    stock_confirmed: bool


def delivery_estimate_source_label(value: str | None) -> str:
    """Fit collector labels into the persisted source column without losing meaning."""
    label = str(value or "unknown")
    aliases = {
        "amazon_displayed_default_destination": "amazon_default_destination",
        "structured_product_offer_calendar_days": "structured_offer_calendar",
    }
    label = aliases.get(label, label)
    return label if len(label) <= 32 else "captured_supplier_offer"


def bounded_evidence_reference(url: str) -> str:
    """Keep exact product identity in the bounded evidence_ref column.

    Amazon search links often carry several hundred characters of tracking
    data. Store the canonical ASIN URL as the compact evidence reference; the
    unmodified captured URL remains in the proposal/audit evidence JSON.
    """
    reference = str(url or "")
    if len(reference) <= 500:
        return reference
    parsed = urlsplit(reference)
    host = (parsed.hostname or "").lower()
    if host == "amazon.co.uk" or host.endswith(".amazon.co.uk"):
        match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/?]|$)", parsed.path, re.I)
        if match:
            return f"https://www.amazon.co.uk/dp/{match.group(1).upper()}"
    if host == "overclockers.co.uk" or host.endswith(".overclockers.co.uk"):
        compact = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        if len(compact) <= 500:
            return compact
    raise HTTPException(422, "The exact supplier URL is longer than the evidence store allows; refresh the product capture")


def source_values(source: dict, entry: ImportEntry) -> dict:
    """Convert one reviewed capture into immutable supplier evidence values."""
    if (source.get("observation_id") != entry.observation_id
            or source.get("fingerprint") != entry.source_fingerprint):
        raise HTTPException(409, "Collector evidence changed; refresh before importing")
    if not source.get("fresh") or not source.get("active_listing"):
        if entry.stock_confirmed:
            raise HTTPException(409, "Stale or inactive listings cannot be confirmed as available")
    if source.get("commercial_capture_verified") is False:
        raise HTTPException(409,
            "The exact listing and current item-price capture are not verified; unknown buying postage is costed at £0.00")

    reference = str(source.get("url") or "")
    try:
        parsed = urlsplit(reference)
        hostname = parsed.hostname
    except ValueError:
        hostname = None
        parsed = None
    if (not parsed or parsed.scheme != "https" or not hostname
            or parsed.username or parsed.password):
        raise HTTPException(422, "An exact credential-free HTTPS listing URL is required")

    try:
        observed_at = datetime.fromisoformat(str(source["observed_at"]).replace("Z", "+00:00"))
        item = Decimal(str(source["item_gbp"]))
        # Inbound postage is a costing input. If the retailer did not provide a
        # verifiable amount, use the owner's £0 fallback instead of blocking
        # evidence review or pricing. This never marks free delivery as verified.
        delivery_value = (source.get("delivery_gbp")
            if source.get("postage_verified") is True else "0.00")
        delivery = Decimal(str(delivery_value))
    except (KeyError, ValueError, TypeError, ArithmeticError) as exc:
        raise HTTPException(422, "Captured item price or observation timestamp is missing; unknown buying postage defaults to £0.00") from exc
    if (observed_at.tzinfo is None or observed_at > datetime.now(timezone.utc)
            or not item.is_finite() or not delivery.is_finite()
            or item < 0 or delivery < 0
            or item != item.quantize(Decimal("0.01"))
            or delivery != delivery.quantize(Decimal("0.01"))):
        raise HTTPException(422, "Captured item price, buying postage fallback or observation timestamp is invalid")

    identity = supplier_identity(source.get("source"), reference)
    software = source.get("evidence_kind") == "official_free_software"
    free_ubuntu = (
        software and identity == "ubuntu"
        and source.get("identity_source") == "official_free_software"
        and source.get("source") == "Ubuntu"
        and source.get("stock_status") == "available"
        and source.get("delivery_working_days") == 0
        and item == 0 and delivery == 0
    )
    if item == 0 and not free_ubuntu:
        raise HTTPException(422, "Zero-cost software requires verified official Ubuntu download evidence")
    if identity in {"royalcdkeys", "gamers_outlet"} and source.get("licence_source_reviewed") is not True:
        raise HTTPException(409, "The exact licence source requires review")

    return {
        "part_key": entry.part_key,
        "supplier": "Ubuntu" if software else identity,
        "channel": "software" if software or identity in {"royalcdkeys", "gamers_outlet"} else (
            "marketplace" if identity in {"ebay", "vinted"} else "retail"
        ),
        "condition": source.get("condition") or "new",
        "item_gbp": item,
        "delivery_gbp": delivery,
        "fees_gbp": entry.fees_gbp,
        "risk_gbp": entry.risk_gbp,
        "supplier_confidence": entry.supplier_confidence,
        "stock_confirmed": entry.stock_confirmed,
        "observed_at": observed_at,
        "delivery_working_days": source.get("delivery_working_days"),
        "delivery_estimate_source": delivery_estimate_source_label(source.get("delivery_estimate_source")),
        "prime_eligible": source.get("prime_eligible"),
        "evidence_ref": bounded_evidence_reference(reference),
        "evidence_source": f"catalogue_import:{entry.observation_id}:{entry.source_fingerprint[:16]}",
    }
