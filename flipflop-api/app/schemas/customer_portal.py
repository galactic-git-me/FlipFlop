from datetime import datetime
from urllib.parse import urlsplit
from pydantic import AnyHttpUrl, BaseModel, Field, field_validator
from typing import Any, Literal


def _safe_customer_tracking_url(value: Any) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    if not candidate or len(candidate) > 1000:
        return None
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return None
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return None
    return candidate


class CustomerProblemCreate(BaseModel):
    category: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=10, max_length=5000)


class CustomerRepairTrackingEventOut(BaseModel):
    status_code: str
    description: str
    location: str | None = None
    occurred_at: datetime
    tracking_url: str | None = None

    @field_validator("tracking_url", mode="before")
    @classmethod
    def expose_only_safe_event_tracking_urls(cls, value: Any) -> str | None:
        return _safe_customer_tracking_url(value)

    model_config = {"extra": "ignore"}


class CustomerRepairTrackingOut(BaseModel):
    """Allow-listed carrier details safe to expose in a customer portal."""

    purpose: Literal["customer_return", "replacement"] | None = None
    carrier: str | None = None
    tracking_number: str | None = None
    tracking_url: str | None = None
    events: list[CustomerRepairTrackingEventOut] = Field(default_factory=list)

    @field_validator("tracking_url", mode="before")
    @classmethod
    def expose_only_safe_tracking_urls(cls, value: Any) -> str | None:
        return _safe_customer_tracking_url(value)

    model_config = {"extra": "ignore"}


class CustomerRepairShipmentEventOut(CustomerRepairTrackingEventOut):
    pass


class CustomerRepairShipmentOut(BaseModel):
    id: int
    purpose: Literal["customer_return", "replacement"]
    carrier: str
    tracking_number: str
    tracking_url: str | None = None
    created_at: datetime
    events: list[CustomerRepairShipmentEventOut] = Field(default_factory=list)

    @field_validator("tracking_url", mode="before")
    @classmethod
    def expose_only_safe_shipment_url(cls, value: Any) -> str | None:
        return _safe_customer_tracking_url(value)

    model_config = {"from_attributes": True, "extra": "ignore"}


class AdminCustomerRepairShipmentOut(CustomerRepairShipmentOut):
    provider: str | None = None
    provider_reference: str | None = None


class CustomerProblemOut(BaseModel):
    id: int
    order_id: int | None = None
    manual_build_id: int | None = None
    category: str
    description: str
    status: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    repair_tracking: CustomerRepairTrackingOut | None = None
    repair_shipments: list[CustomerRepairShipmentOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminCustomerProblemOut(CustomerProblemOut):
    """Admin-only provider linkage needed to reconcile repair shipments."""

    repair_tracking_provider_reference: str | None = None
    repair_shipments: list[AdminCustomerRepairShipmentOut] = Field(default_factory=list)


class CustomerProblemStatusUpdate(BaseModel):
    status: str = Field(pattern="^(received|reviewing|claim_opened|approved|awaiting_customer_return|return_in_transit|received_for_inspection|repair_in_progress|waiting_for_parts|replacement_ordered|replacement_dispatched|resolved|rejected|closed)$")
    repair_tracking_purpose: Literal["customer_return", "replacement"] | None = None
    repair_carrier: str | None = Field(default=None, min_length=1, max_length=100)
    repair_tracking_number: str | None = Field(default=None, min_length=1, max_length=160)
    repair_tracking_url: AnyHttpUrl | None = Field(default=None, max_length=500)
    repair_tracking_provider_reference: str | None = Field(default=None, min_length=1, max_length=120)
    repair_tracking_note: str | None = Field(default=None, max_length=1000)

    @field_validator("repair_tracking_url")
    @classmethod
    def tracking_url_must_use_https(cls, value: AnyHttpUrl | None) -> AnyHttpUrl | None:
        if value is not None:
            parsed = urlsplit(str(value))
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("Repair tracking links must use HTTPS and cannot contain embedded credentials")
        return value


class CustomerDocumentOut(BaseModel):
    id: int
    document_type: str
    status: str
    version: int
    pdf_url: str | None = None
    generated_at: datetime | None = None
    content_json: dict[str, Any] | None = None
