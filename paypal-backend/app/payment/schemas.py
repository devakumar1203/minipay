import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from app.wallet.schemas import LedgerEntryResponse


class SendMoneyRequest(BaseModel):
    recipient_email: EmailStr
    amount: int = Field(..., gt=0, description="Amount in paise (must be > 0)")
    source: str = Field(..., description="'WALLET' or funding source UUID")


class TransactionResponse(BaseModel):
    id: uuid.UUID
    idempotency_key: str
    type: str
    status: str
    amount: int
    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
    funding_source_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SagaStateResponse(BaseModel):
    id: uuid.UUID
    txn_id: uuid.UUID
    step: str
    status: str
    error_detail: Optional[str] = None
    updated_at: datetime

    class Config:
        from_attributes = True


class TransactionDetailResponse(TransactionResponse):
    ledger_entries: List[LedgerEntryResponse] = []
    saga_states: List[SagaStateResponse] = []


class PaginatedTransactionsResponse(BaseModel):
    items: List[TransactionResponse]
    total: int
    page: int
    per_page: int

