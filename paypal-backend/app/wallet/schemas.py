import uuid
from datetime import datetime
from pydantic import BaseModel


class BalanceResponse(BaseModel):
    balance: int  # in paise
    currency: str = "INR"


class LedgerEntryResponse(BaseModel):
    id: uuid.UUID
    txn_id: uuid.UUID
    account_id: uuid.UUID
    direction: str
    amount: int
    created_at: datetime

    class Config:
        from_attributes = True

