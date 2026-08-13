from typing import Optional
from pydantic import BaseModel


class MotherboardSpecOut(BaseModel):
    id: int
    canonical_model: str
    brand: Optional[str]
    socket: Optional[str]
    chipset: Optional[str]
    ram_type: Optional[str]
    ram_slots: Optional[int]
    max_ram_gb: Optional[int]
    pcie_x16_slots: Optional[int]
    m2_slots: Optional[int]
    sata_ports: Optional[int]
    form_factor: Optional[str]
    wifi: Optional[bool]
    source: str
    ai_confidence: Optional[float]
    ai_reasoning: Optional[str]
    reviewed: bool
    reviewed_by: Optional[str]

    model_config = {"from_attributes": True}


class MotherboardSpecBackfillRequest(BaseModel):
    title: str


class MotherboardSpecUpdate(BaseModel):
    canonical_model: Optional[str] = None
    brand: Optional[str] = None
    socket: Optional[str] = None
    chipset: Optional[str] = None
    ram_type: Optional[str] = None
    ram_slots: Optional[int] = None
    max_ram_gb: Optional[int] = None
    pcie_x16_slots: Optional[int] = None
    m2_slots: Optional[int] = None
    sata_ports: Optional[int] = None
    form_factor: Optional[str] = None
    wifi: Optional[bool] = None
    reviewed: Optional[bool] = None
