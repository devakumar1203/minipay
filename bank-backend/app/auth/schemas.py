import uuid
from datetime import datetime, date
from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, Field


class BankRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2)
    gender: Literal["MALE", "FEMALE", "OTHER"]
    date_of_birth: date
    aadhaar_no: str = Field(..., pattern=r"^\d{12}$", description="12-digit Aadhaar number")
    pan_no: str = Field(..., pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$", description="10-character PAN number")


class BankLoginRequest(BaseModel):
    email: EmailStr
    password: str


class BankTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class BankUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    gender: str
    date_of_birth: date
    aadhaar_no: str
    pan_no: str
    created_at: datetime

    class Config:
        from_attributes = True
