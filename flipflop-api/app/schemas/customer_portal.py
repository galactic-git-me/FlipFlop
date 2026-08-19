from datetime import datetime
from pydantic import BaseModel, Field


class CustomerProblemCreate(BaseModel):
    category: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=10, max_length=5000)


class CustomerProblemOut(BaseModel):
    id: int
    order_id: int
    category: str
    description: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CustomerProblemStatusUpdate(BaseModel):
    status: str = Field(pattern="^(received|reviewing|claim_opened|resolved|closed)$")


class CustomerDocumentOut(BaseModel):
    id: int
    document_type: str
    status: str
    version: int
    pdf_url: str | None = None
    generated_at: datetime | None = None
