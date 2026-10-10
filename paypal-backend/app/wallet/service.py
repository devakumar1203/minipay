import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
import structlog

from app.wallet.models import Account, LedgerEntry

logger = structlog.get_logger()


async def get_wallet(session: AsyncSession, user_id: uuid.UUID) -> Account:
    stmt = select(Account).where(
        Account.user_id == user_id, Account.type == "USER_WALLET"
    )
    result = await session.execute(stmt)
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Wallet account not found", "code": "WALLET_NOT_FOUND"},
        )
    return account


async def get_balance(session: AsyncSession, user_id: uuid.UUID) -> int:
    wallet = await get_wallet(session, user_id)
    return wallet.balance


async def get_or_create_bank_external_account(
    session: AsyncSession, bank_id: str
) -> Account:
    stmt = select(Account).where(
        Account.type == "BANK_EXTERNAL", Account.bank_id == bank_id
    )
    result = await session.execute(stmt)
    account = result.scalar_one_or_none()
    if not account:
        account = Account(
            user_id=None,
            type="BANK_EXTERNAL",
            bank_id=bank_id,
            balance=0,
            version=1,
        )
        session.add(account)
        await session.flush()
        logger.info("created_bank_external_account", bank_id=bank_id)
    return account


async def ensure_bank_external_accounts(session: AsyncSession) -> None:
    try:
        for bank_id in ["bank_x", "bank_y"]:
            await get_or_create_bank_external_account(session, bank_id)
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.info("bank_external_accounts_already_ensured", error=str(e))



async def create_ledger_entries(
    session: AsyncSession,
    txn_id: uuid.UUID,
    entries: List[Dict[str, Any]],
) -> List[LedgerEntry]:
    """
    Creates double-entry ledger records and updates account balances.
    entries format: [{"account_id": UUID, "direction": "DEBIT"|"CREDIT", "amount": int}]
    
    Convention:
      - DEBIT decreases account balance
      - CREDIT increases account balance
      - sum(DEBIT amounts) must equal sum(CREDIT amounts)
    """
    if not entries:
        raise ValueError("Ledger entries list cannot be empty")

    total_debits = sum(e["amount"] for e in entries if e["direction"] == "DEBIT")
    total_credits = sum(e["amount"] for e in entries if e["direction"] == "CREDIT")

    if total_debits != total_credits:
        raise ValueError(
            f"Unbalanced ledger entries: total debits ({total_debits}) != total credits ({total_credits})"
        )

    ledger_records = []
    for entry in entries:
        amount = entry["amount"]
        if amount <= 0:
            raise ValueError("Ledger amount must be strictly positive")

        direction = entry["direction"]
        if direction not in ("DEBIT", "CREDIT"):
            raise ValueError(f"Invalid ledger direction: {direction}")

        record = LedgerEntry(
            txn_id=txn_id,
            account_id=entry["account_id"],
            direction=direction,
            amount=amount,
        )
        session.add(record)
        ledger_records.append(record)

        # Update Account balance
        account = await session.get(Account, entry["account_id"])
        if not account:
            raise ValueError(f"Account {entry['account_id']} not found for ledger entry")

        if direction == "DEBIT":
            if account.type == "USER_WALLET" and account.balance < amount:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"detail": "Insufficient wallet balance", "code": "INSUFFICIENT_BALANCE"},
                )
            account.balance -= amount
        elif direction == "CREDIT":
            account.balance += amount

        account.version += 1

    return ledger_records


async def verify_ledger_integrity(session: AsyncSession, txn_id: uuid.UUID) -> bool:
    """Verifies that debits == credits for a given transaction."""
    stmt = select(
        LedgerEntry.direction, func.sum(LedgerEntry.amount)
    ).where(LedgerEntry.txn_id == txn_id).group_by(LedgerEntry.direction)
    result = await session.execute(stmt)
    rows = dict(result.fetchall())
    debits = rows.get("DEBIT", 0)
    credits = rows.get("CREDIT", 0)
    return debits == credits and debits > 0


async def verify_account_balance(session: AsyncSession, account_id: uuid.UUID) -> bool:
    """Verifies that account.balance == sum(CREDITs) - sum(DEBITs) from ledger entries."""
    account = await session.get(Account, account_id)
    if not account:
        return False

    stmt = select(
        LedgerEntry.direction, func.sum(LedgerEntry.amount)
    ).where(LedgerEntry.account_id == account_id).group_by(LedgerEntry.direction)
    result = await session.execute(stmt)
    rows = dict(result.fetchall())
    debits = rows.get("DEBIT", 0) or 0
    credits = rows.get("CREDIT", 0) or 0
    computed_balance = credits - debits
    return account.balance == computed_balance
