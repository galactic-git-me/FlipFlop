"""
Schemas for buying flow data collection.
Progressive disclosure during curated journey.
"""
from pydantic import BaseModel, Field
from typing import Optional


class BuyingFlowData(BaseModel):
    """
    Buying flow preferences collected during curated journey.
    All fields optional for progressive disclosure.
    """
    # Gift vs self
    is_gift: bool = Field(default=False, description="Is this a gift for someone else?")
    recipient_age_band: Optional[str] = Field(
        None, 
        description="If gift: child/teen/adult/senior"
    )
    
    # Packaging & delivery
    discreet_packaging: bool = Field(default=False, description="Use discreet packaging?")
    urgency: Optional[str] = Field(
        None,
        description="Need-by urgency: asap/this_week/flexible"
    )
    
    # PC experience
    is_first_pc: Optional[bool] = Field(None, description="Is this your first PC or an upgrade?")
    current_gpu: Optional[str] = Field(
        None,
        description="If upgrade: current GPU model or 'dont_know'"
    )
    
    # Business
    is_business_buyer: bool = Field(default=False, description="Buying as a business?")
    wants_vat_invoice: bool = Field(default=False, description="Need VAT invoice?")
    
    # Aesthetics
    aesthetic_preference: Optional[str] = Field(
        None,
        description="Aesthetic preference: quiet/rgb"
    )
    
    # Journey context (from wizard)
    journey_budget_min: Optional[float] = Field(None, description="Selected budget minimum")
    journey_budget_max: Optional[float] = Field(None, description="Selected budget maximum")
    journey_customer_type: Optional[str] = Field(None, description="Selected customer type")
    journey_tier: Optional[str] = Field(None, description="Selected tier: budget/mid/high")

    class Config:
        json_schema_extra = {
            "example": {
                "is_gift": False,
                "discreet_packaging": False,
                "urgency": "flexible",
                "is_first_pc": True,
                "is_business_buyer": False,
                "wants_vat_invoice": False,
                "aesthetic_preference": "rgb",
                "journey_budget_min": 800,
                "journey_budget_max": 1200,
                "journey_customer_type": "Great-value Gaming",
                "journey_tier": "mid"
            }
        }


class SessionAnalyticsEvent(BaseModel):
    """
    Analytics event with buying flow context.
    Emitted at each step: budget → type → tier → playbook → case → rgb → ar.
    """
    event_type: str = Field(..., description="Event type: budget_chosen/customer_type_picked/etc")
    curated_build_id: Optional[str] = Field(None, description="Curated build ID if applicable")
    metadata: dict = Field(default_factory=dict, description="Event-specific metadata")
    
    # Buying flow context (carried through session)
    buying_flow: Optional[BuyingFlowData] = Field(None, description="Buying flow preferences")
    
    # Customer context (if authenticated)
    customer_id: Optional[int] = Field(None, description="Customer ID if logged in")
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "playbook_tier_shown",
                "curated_build_id": "FF-GVG-02",
                "metadata": {
                    "segment": "Great-value Gaming",
                    "tier": "Mid-range",
                    "price_gbp": 899
                },
                "buying_flow": {
                    "journey_budget_min": 800,
                    "journey_budget_max": 1200,
                    "journey_customer_type": "Great-value Gaming",
                    "journey_tier": "mid",
                    "aesthetic_preference": "rgb"
                },
                "customer_id": 123
            }
        }
