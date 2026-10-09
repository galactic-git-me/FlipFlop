from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional


class SignupRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: str | None = Field(None, min_length=8, description="Password (minimum 8 characters, or null for magic link)")
    name: str = Field(..., min_length=1, description="User full name")
    
    # Registration data (progressive disclosure - optional at signup)
    year_of_birth: int | None = Field(None, ge=1900, le=2024, description="Year of birth for age band and birthday offers")
    marketing_opt_in: bool = Field(default=False, description="Opt-in to marketing communications (separate from account)")
    acquisition_source: str | None = Field(None, description="How did you find us? (search/youtube/reddit/referral/ebay/other)")
    acquisition_detail: str | None = Field(None, max_length=255, description="Additional detail (e.g., referral code)")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123",
                "name": "John Doe",
                "year_of_birth": 1995,
                "marketing_opt_in": True,
                "acquisition_source": "reddit"
            }
        }


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123"
            }
        }


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer"
            }
        }


class CustomerResponse(BaseModel):
    id: int = Field(..., description="Customer ID")
    email: str = Field(..., description="Customer email")
    name: str = Field(..., description="Customer full name")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    created_at: datetime = Field(..., description="Account creation timestamp")
    
    # Registration data
    year_of_birth: Optional[int] = Field(None, description="Year of birth")
    marketing_opt_in: bool = Field(default=False, description="Marketing opt-in status")
    acquisition_source: Optional[str] = Field(None, description="How they found us")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "email": "user@example.com",
                "name": "John Doe",
                "last_login": "2024-06-29T12:00:00Z",
                "created_at": "2024-06-28T10:30:00Z",
                "year_of_birth": 1995,
                "marketing_opt_in": True,
                "acquisition_source": "reddit"
            }
        }


class CustomerProfileUpdateRequest(BaseModel):
    """Update customer profile (progressive disclosure)"""
    name: str | None = Field(None, min_length=1, description="Update full name")
    year_of_birth: int | None = Field(None, ge=1900, le=2024, description="Year of birth")
    marketing_opt_in: bool | None = Field(None, description="Marketing opt-in preference")
    acquisition_source: str | None = Field(None, description="How did you find us?")
    acquisition_detail: str | None = Field(None, max_length=255, description="Additional acquisition detail")
    
    class Config:
        json_schema_extra = {
            "example": {
                "year_of_birth": 1995,
                "marketing_opt_in": True
            }
        }
