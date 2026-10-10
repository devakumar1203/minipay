import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field
from app.funding.schemas import FundingSourceResponse
from app.payment.schemas import TransactionResponse, TransactionDetailResponse


class AdminDashboardResponse(BaseModel):
    total_users: int
    blocked_users: int
    txn_counts_by_status: Dict[str, int]
    total_volume: int  # in paise
    failure_rate: float
    last_24h_txns: int


class AdminUserDetailResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    status: str
    full_name: Optional[str] = None
    mobile_no: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    onboarding_step: Optional[int] = 4
    blocked_reason: Optional[str] = None
    blocked_at: Optional[datetime] = None
    wallet_balance: int
    funding_sources: List[FundingSourceResponse] = []
    transactions: List[TransactionResponse] = []
    created_at: datetime


class AdminActionRequest(BaseModel):
    reason: str = Field(..., min_length=3, description="Mandatory reason for audit log")


class AdminActionResponse(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID
    action: str
    target_type: str
    target_id: str
    reason: str
    created_at: datetime

    class Config:
        from_attributes = True


class FraudConfigResponse(BaseModel):
    max_txn_amount: int
    daily_max_amount: int
    max_txn_per_minute: int
    new_account_days: int
    new_account_max_txn: int


class UpdateFraudConfigRequest(BaseModel):
    max_txn_amount: Optional[int] = None
    daily_max_amount: Optional[int] = None
    max_txn_per_minute: Optional[int] = None
    new_account_days: Optional[int] = None
    new_account_max_txn: Optional[int] = None

