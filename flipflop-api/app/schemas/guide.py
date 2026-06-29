from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class WelcomeGuideRequest(BaseModel):
    """Request to generate a welcome guide for an order."""
    regenerate: bool = Field(False, description="Force regenerate even if exists")


class WelcomeGuideResponse(BaseModel):
    """Response containing welcome guide information."""
    order_id: int
    pdf_url: str = Field(..., description="Path or URL to download the PDF")
    generated_at: datetime
    file_size_bytes: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class WelcomeGuideDownloadResponse(BaseModel):
    """Response for guide download (wrapper for file response metadata)."""
    order_id: int
    filename: str
    content_type: str = "application/pdf"
