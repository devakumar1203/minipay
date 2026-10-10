import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ProfileUpdateRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    mobile_no: str = Field(..., pattern=r"^\+?[0-9]{10,15}$", description="Mobile phone number")


class AddressUpdateRequest(BaseModel):
    address_line1: str = Field(..., min_length=3, max_length=500)
    address_line2: Optional[str] = Field(default="", max_length=500)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    pincode: str = Field(..., pattern=r"^\d{6}$", description="6-digit PIN code")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    onboarding_step: int = 1


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    status: str
    onboarding_step: int = 1
    email_verified: bool = False
    full_name: Optional[str] = None
    mobile_no: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    blocked_reason: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
