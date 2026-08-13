from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminUserResponse(BaseModel):
    id: int
    email: str
    name: str
    role: str
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True
