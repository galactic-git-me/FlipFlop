"""Public trader disclosures, persisted like the existing uploaded settings guide."""
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

BUSINESS_DETAILS_PATH = Path(__file__).resolve().parents[2] / 'data' / 'storefront-business-details.json'


class BusinessDetails(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    tradingName: str = Field(default='FlipFlop', min_length=1, max_length=150)
    legalName: str = Field(default='', max_length=200)
    address: str = Field(default='', max_length=1000)
    phone: str = Field(default='', max_length=50)
    email: str = Field(default='mac@theflipflop.shop', min_length=3, max_length=254)
    vatNumber: str | None = Field(default=None, max_length=100)
    weeeRegistration: str | None = Field(default=None, max_length=100)
    weeeTakebackRoute: Literal['unconfirmed', 'direct', 'dts'] = 'unconfirmed'
    returnsAddress: str | None = Field(default=None, max_length=1000)

    @field_validator('email')
    @classmethod
    def email_address(cls, value):
        import re
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('Enter a valid public contact email address')
        return value


def read_business_details() -> BusinessDetails:
    if not BUSINESS_DETAILS_PATH.exists():
        return BusinessDetails()
    return BusinessDetails.model_validate_json(BUSINESS_DETAILS_PATH.read_text(encoding='utf-8'))


def save_business_details(details: BusinessDetails) -> BusinessDetails:
    BUSINESS_DETAILS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode='w', encoding='utf-8', dir=BUSINESS_DETAILS_PATH.parent, suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(details.model_dump(), stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        temporary.replace(BUSINESS_DETAILS_PATH)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    return read_business_details()
