import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class InitiateLinkRequest(BaseModel):
    bank_id: str = Field(..., description="'bank_x' or 'bank_y'")


class InitiateLinkResponse(BaseModel):
    redirect_url: str
    paypal_request_id: str


class CallbackLinkRequest(BaseModel):
    bank_id: str
    code: str
    paypal_request_id: str


class RequestLinkInput(BaseModel):
    bank_id: str = Field(..., description="'bank_x' or 'bank_y'")
    account_no: str = Field(..., min_length=4, description="Bank account number")


class LinkWebhookPayload(BaseModel):
    request_id: str
    status: str  # "APPROVED" | "DENIED"
    bank_id: str
    token: Optional[str] = None
    masked_account: Optional[str] = None


class FundingSourceResponse(BaseModel):
    id: uuid.UUID
    bank_id: str
    masked_account: str
    is_default: bool
    status: str
    link_request_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AddMoneyRequest(BaseModel):
    funding_source_id: uuid.UUID
    amount: int = Field(..., gt=0, description="Amount in paise")


class WithdrawRequest(BaseModel):
    funding_source_id: uuid.UUID
    amount: int = Field(..., gt=0, description="Amount in paise")
