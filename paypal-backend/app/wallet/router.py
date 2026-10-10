import uuid
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.models import User
from app.auth.dependencies import get_current_user
from app.wallet.models import Account, LedgerEntry
from app.wallet.schemas import BalanceResponse, LedgerEntryResponse
from app.wallet.service import get_wallet

router = APIRouter()


@router.get("/balance", response_model=BalanceResponse, summary="Get user wallet balance")
async def get_wallet_balance(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    wallet = await get_wallet(session, current_user.id)
    return BalanceResponse(balance=wallet.balance, currency="INR")


@router.get(
    "/ledger-entries",
    response_model=List[LedgerEntryResponse],
    summary="Get user wallet ledger entries",
)
async def get_user_ledger_entries(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    wallet = await get_wallet(session, current_user.id)
    stmt = (
        select(LedgerEntry)
        .where(LedgerEntry.account_id == wallet.id)
        .order_by(LedgerEntry.created_at.desc())
        .limit(100)
    )
    result = await session.execute(stmt)
    entries = result.scalars().all()
    return entries
