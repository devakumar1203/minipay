import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, func, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
import redis.asyncio as aioredis
import structlog

from app.config import settings
from app.auth.models import User
from app.wallet.models import Account, LedgerEntry
from app.wallet.service import get_wallet, create_ledger_entries
from app.funding.models import FundingSource
from app.payment.models import Transaction, SagaState
from app.outbox.models import Outbox
from app.admin.models import AdminAction
from app.bank_client.client import BankClient
from app.reconciliation.job import reconciliation_job

logger = structlog.get_logger()


async def get_dashboard_metrics(session: AsyncSession) -> Dict[str, Any]:
    # 1. Total & Blocked Users
    user_counts_stmt = select(
        func.count(User.id).label("total"),
        func.count(func.nullif(User.status != "BLOCKED", True)).label("blocked"),
    )
    user_res = await session.execute(user_counts_stmt)
    u_row = user_res.fetchone()
    total_users = u_row.total if u_row else 0
    blocked_users = u_row.blocked if u_row else 0

    # 2. Transaction status counts & volume
    txn_status_stmt = select(
        Transaction.status,
        func.count(Transaction.id),
        func.sum(Transaction.amount),
    ).group_by(Transaction.status)
    txn_res = await session.execute(txn_status_stmt)
    status_counts = {}
    total_volume = 0
    total_txns = 0
    failed_txns = 0

    for row in txn_res.fetchall():
        status_counts[row[0]] = row[1]
        total_txns += row[1]
        if row[0] == "COMPLETED":
            total_volume += (row[2] or 0)
        elif row[0] == "FAILED":
            failed_txns += row[1]

    failure_rate = (failed_txns / total_txns * 100.0) if total_txns > 0 else 0.0

    # 3. Last 24h activity
    twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    last_24h_stmt = select(func.count(Transaction.id)).where(Transaction.created_at >= twenty_four_hours_ago)
    last_24h_res = await session.execute(last_24h_stmt)
    last_24h_count = last_24h_res.scalar() or 0

    return {
        "total_users": total_users,
        "blocked_users": blocked_users,
        "txn_counts_by_status": status_counts,
        "total_volume": total_volume,
        "failure_rate": round(failure_rate, 2),
        "last_24h_txns": last_24h_count,
    }


async def block_user(
    session: AsyncSession,
    redis: aioredis.Redis,
    admin_id: uuid.UUID,
    user_id: uuid.UUID,
    reason: str,
) -> User:
    if admin_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Admins cannot block themselves", "code": "CANNOT_BLOCK_SELF"},
        )

    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "User not found", "code": "USER_NOT_FOUND"},
        )

    if user.role == "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Cannot block an administrator", "code": "CANNOT_BLOCK_ADMIN"},
        )

    user.status = "BLOCKED"
    user.blocked_reason = reason
    user.blocked_at = datetime.now(timezone.utc)

    # 1. Immediate multi-instance propagation via Redis
    await redis.sadd("blocked_users", str(user.id))

    # 2. Append-only Admin Audit Log
    action = AdminAction(
        admin_id=admin_id,
        action="BLOCK_USER",
        target_type="USER",
        target_id=str(user.id),
        reason=reason,
    )
    session.add(action)

    # 3. Outbox Event
    outbox_event = Outbox(
        event_type="UserBlocked",
        payload={
            "user_id": str(user.id),
            "reason": reason,
            "admin_id": str(admin_id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        published=False,
    )
    session.add(outbox_event)

    await session.commit()
    await session.refresh(user)
    logger.info("admin_blocked_user", admin_id=str(admin_id), user_id=str(user.id), reason=reason)
    return user


async def unblock_user(
    session: AsyncSession,
    redis: aioredis.Redis,
    admin_id: uuid.UUID,
    user_id: uuid.UUID,
    reason: str,
) -> User:
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "User not found", "code": "USER_NOT_FOUND"},
        )

    user.status = "ACTIVE"
    user.blocked_reason = None
    user.blocked_at = None

    # Remove from Redis
    await redis.srem("blocked_users", str(user.id))

    action = AdminAction(
        admin_id=admin_id,
        action="UNBLOCK_USER",
        target_type="USER",
        target_id=str(user.id),
        reason=reason,
    )
    session.add(action)

    outbox_event = Outbox(
        event_type="UserUnblocked",
        payload={
            "user_id": str(user.id),
            "admin_id": str(admin_id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        published=False,
    )
    session.add(outbox_event)

    await session.commit()
    await session.refresh(user)
    logger.info("admin_unblocked_user", admin_id=str(admin_id), user_id=str(user.id), reason=reason)
    return user


async def approve_review_transaction(
    session: AsyncSession,
    admin_id: uuid.UUID,
    txn_id: uuid.UUID,
    reason: str,
) -> Transaction:
    txn = await session.get(Transaction, txn_id)
    if not txn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Transaction not found", "code": "TXN_NOT_FOUND"},
        )

    if txn.status != "UNDER_REVIEW":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": f"Transaction status is '{txn.status}', not UNDER_REVIEW", "code": "INVALID_TXN_STATUS"},
        )

    # Resume the payment flow depending on type
    if txn.type == "P2P_WALLET":
        from_wallet = await session.get(Account, txn.from_account_id)
        to_wallet = await session.get(Account, txn.to_account_id)

        if from_wallet.balance < txn.amount:
            txn.status = "FAILED"
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "Sender wallet balance insufficient to complete approved transaction", "code": "INSUFFICIENT_BALANCE"},
            )

        ledger_entries = [
            {"account_id": from_wallet.id, "direction": "DEBIT", "amount": txn.amount},
            {"account_id": to_wallet.id, "direction": "CREDIT", "amount": txn.amount},
        ]
        await create_ledger_entries(session, txn.id, ledger_entries)
        txn.status = "COMPLETED"

    elif txn.type in ("P2P_BANK", "ADD_MONEY"):
        source = await session.get(FundingSource, txn.funding_source_id)
        bank_client = BankClient(source.bank_id)
        debit_res = await bank_client.debit(reference_id=str(txn.id), token=source.token, amount=txn.amount)

        if debit_res.get("status") == "APPROVED":
            from_acc = await session.get(Account, txn.from_account_id)
            to_acc = await session.get(Account, txn.to_account_id)
            ledger_entries = [
                {"account_id": from_acc.id, "direction": "DEBIT", "amount": txn.amount},
                {"account_id": to_acc.id, "direction": "CREDIT", "amount": txn.amount},
            ]
            await create_ledger_entries(session, txn.id, ledger_entries)
            txn.status = "COMPLETED"
        else:
            txn.status = "FAILED"

    elif txn.type == "WITHDRAW":
        user_wallet = await session.get(Account, txn.from_account_id)
        bank_ext = await session.get(Account, txn.to_account_id)
        if user_wallet.balance < txn.amount:
            txn.status = "FAILED"
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "Insufficient wallet balance", "code": "INSUFFICIENT_BALANCE"},
            )
        # Reserve hold
        ledger_entries = [
            {"account_id": user_wallet.id, "direction": "DEBIT", "amount": txn.amount},
            {"account_id": bank_ext.id, "direction": "CREDIT", "amount": txn.amount},
        ]
        await create_ledger_entries(session, txn.id, ledger_entries)
        source = await session.get(FundingSource, txn.funding_source_id)
        bank_client = BankClient(source.bank_id)
        credit_res = await bank_client.credit(reference_id=str(txn.id), token=source.token, amount=txn.amount)
        if credit_res.get("status") == "APPROVED":
            txn.status = "COMPLETED"
        else:
            # Reversal
            rev = [
                {"account_id": bank_ext.id, "direction": "DEBIT", "amount": txn.amount},
                {"account_id": user_wallet.id, "direction": "CREDIT", "amount": txn.amount},
            ]
            await create_ledger_entries(session, txn.id, rev)
            txn.status = "FAILED"

    action = AdminAction(
        admin_id=admin_id,
        action="APPROVE_TXN",
        target_type="TRANSACTION",
        target_id=str(txn.id),
        reason=reason,
    )
    session.add(action)
    await session.commit()
    await session.refresh(txn)

    logger.info("admin_approved_transaction", admin_id=str(admin_id), txn_id=str(txn.id), final_status=txn.status)
    return txn


async def reject_review_transaction(
    session: AsyncSession,
    admin_id: uuid.UUID,
    txn_id: uuid.UUID,
    reason: str,
) -> Transaction:
    txn = await session.get(Transaction, txn_id)
    if not txn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Transaction not found", "code": "TXN_NOT_FOUND"},
        )

    if txn.status != "UNDER_REVIEW":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": f"Transaction status is '{txn.status}', not UNDER_REVIEW", "code": "INVALID_TXN_STATUS"},
        )

    txn.status = "FAILED"
    action = AdminAction(
        admin_id=admin_id,
        action="REJECT_TXN",
        target_type="TRANSACTION",
        target_id=str(txn.id),
        reason=reason,
    )
    session.add(action)
    await session.commit()
    await session.refresh(txn)

    logger.info("admin_rejected_transaction", admin_id=str(admin_id), txn_id=str(txn.id), reason=reason)
    return txn


async def reverse_completed_p2p_transaction(
    session: AsyncSession,
    admin_id: uuid.UUID,
    txn_id: uuid.UUID,
    reason: str,
) -> Transaction:
    txn = await session.get(Transaction, txn_id)
    if not txn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Transaction not found", "code": "TXN_NOT_FOUND"},
        )

    if txn.type not in ("P2P_WALLET", "P2P_BANK") or txn.status != "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Only COMPLETED P2P transactions can be reversed", "code": "CANNOT_REVERSE"},
        )

    recipient_wallet = await session.get(Account, txn.to_account_id)
    sender_wallet = await session.get(Account, txn.from_account_id)

    # Check recipient wallet has sufficient balance to claw back
    if recipient_wallet.balance < txn.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": f"Recipient wallet balance (₹{recipient_wallet.balance/100:.2f}) is insufficient to reverse ₹{txn.amount/100:.2f}",
                "code": "INSUFFICIENT_RECIPIENT_BALANCE",
            },
        )

    # Create NEW compensating ledger entries (DEBIT recipient, CREDIT sender)
    # NEVER edit or delete existing ledger entries!
    reversal_entries = [
        {"account_id": recipient_wallet.id, "direction": "DEBIT", "amount": txn.amount},
        {"account_id": sender_wallet.id, "direction": "CREDIT", "amount": txn.amount},
    ]
    await create_ledger_entries(session, txn.id, reversal_entries)
    txn.status = "REVERSED"

    action = AdminAction(
        admin_id=admin_id,
        action="REVERSE_TXN",
        target_type="TRANSACTION",
        target_id=str(txn.id),
        reason=reason,
    )
    session.add(action)
    await session.commit()
    await session.refresh(txn)

    logger.info("admin_reversed_transaction", admin_id=str(admin_id), txn_id=str(txn.id), reason=reason)
    return txn

