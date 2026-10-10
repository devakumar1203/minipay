import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class BankAccountResponse(BaseModel):
    id: uuid.UUID
    account_no: str
    balance: int
    created_at: datetime

    class Config:
        from_attributes = True


class BankTxnResponse(BaseModel):
    id: uuid.UUID
    reference_id: str
    account_no: str
    type: str
    amount: int
    status: str
    reason: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class LinkConsentResponse(BaseModel):
    id: uuid.UUID
    consent_id: str
    account_no: str
    masked_account: str
    per_txn_limit: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class BankNotificationResponse(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    message: str
    reference_id: Optional[str] = None
    is_read: bool
    is_actionable: bool
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class LinkRequestCreate(BaseModel):
    request_id: str
    account_no: str
    requester_name: str = "MiniPay"
    purpose: str = "Link bank account for payments"
    per_txn_limit: int = 5000000


class LinkRequestResponse(BaseModel):
    request_id: str
    account_no: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
