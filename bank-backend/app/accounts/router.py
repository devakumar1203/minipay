from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.models import BankUser
from app.auth.service import get_current_bank_user
from app.accounts.models import BankAccount, BankTxn
from app.accounts.schemas import BankAccountResponse, BankTxnResponse

router = APIRouter()


@router.get("", response_model=List[BankAccountResponse], summary="List bank accounts for logged-in user")
async def list_accounts_endpoint(
    current_user: BankUser = Depends(get_current_bank_user),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(BankAccount)
        .where(BankAccount.user_id == current_user.id)
        .order_by(BankAccount.created_at.asc())
    )
    res = await session.execute(stmt)
    accounts = res.scalars().all()
    return accounts


@router.get(
    "/{account_no}/transactions",
    response_model=List[BankTxnResponse],
    summary="Get transaction history for a bank account",
)
async def get_account_transactions_endpoint(
    account_no: str,
    current_user: BankUser = Depends(get_current_bank_user),
    session: AsyncSession = Depends(get_db),
):
    # Verify account ownership
    acc_stmt = select(BankAccount).where(
        BankAccount.account_no == account_no, BankAccount.user_id == current_user.id
    )
    acc_res = await session.execute(acc_stmt)
    account = acc_res.scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Bank account not found", "code": "ACCOUNT_NOT_FOUND"},
        )

    stmt = (
        select(BankTxn)
        .where(BankTxn.account_no == account_no)
        .order_by(BankTxn.created_at.desc())
        .limit(100)
    )
    res = await session.execute(stmt)
    txns = res.scalars().all()
    return txns

