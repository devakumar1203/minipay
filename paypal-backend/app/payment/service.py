import uuid
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
import structlog

from app.auth.models import User
from app.wallet.models import Account, LedgerEntry
from app.wallet.service import create_ledger_entries
from app.payment.models import Transaction, SagaState
from app.outbox.models import Outbox
from app.fraud.service import check_fraud, FraudDecision
from app.redis_client import get_redis

logger = structlog.get_logger()


async def transfer_wallet_to_wallet(
    session: AsyncSession,
    sender_id: uuid.UUID,
    recipient_email: str,
    amount: int,
    idempotency_key: str,
) -> Transaction:
    # 1. Check idempotency: if transaction exists with this key, return it immediately
    stmt = select(Transaction).where(Transaction.idempotency_key == idempotency_key)
    result = await session.execute(stmt)
    existing_txn = result.scalar_one_or_none()
    if existing_txn:
        logger.info("idempotent_request_returned", idempotency_key=idempotency_key, txn_id=str(existing_txn.id))
        return existing_txn

    # 2. Lookup recipient
    clean_email = recipient_email.lower().strip()
    stmt = select(User).where(User.email == clean_email)
    result = await session.execute(stmt)
    recipient = result.scalar_one_or_none()
    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Recipient user not found", "code": "RECIPIENT_NOT_FOUND"},
        )

    # Check sender != recipient
    if sender_id == recipient.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Cannot send money to yourself", "code": "SELF_TRANSFER_NOT_ALLOWED"},
        )

    # Check recipient status
    if recipient.status == "BLOCKED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Recipient account is blocked", "code": "RECIPIENT_BLOCKED"},
        )

    # 3. Fraud check
    redis = await get_redis()
    fraud_decision = await check_fraud(sender_id, amount, "P2P_WALLET", redis, session)
    if fraud_decision == FraudDecision.BLOCK:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "Payment blocked by fraud detection rules", "code": "FRAUD_BLOCKED"},
        )

    # 4. Lookup sender and recipient wallet accounts
    sender_wallet_stmt = select(Account).where(
        Account.user_id == sender_id, Account.type == "USER_WALLET"
    )
    result = await session.execute(sender_wallet_stmt)
    sender_wallet = result.scalar_one_or_none()
    if not sender_wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Sender wallet not found", "code": "SENDER_WALLET_NOT_FOUND"},
        )

    recipient_wallet_stmt = select(Account).where(
        Account.user_id == recipient.id, Account.type == "USER_WALLET"
    )
    result = await session.execute(recipient_wallet_stmt)
    recipient_wallet = result.scalar_one_or_none()
    if not recipient_wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Recipient wallet not found", "code": "RECIPIENT_WALLET_NOT_FOUND"},
        )

    # 5. Handle Fraud Review Case (UNDER_REVIEW)
    if fraud_decision == FraudDecision.REVIEW:
        txn = Transaction(
            idempotency_key=idempotency_key,
            type="P2P_WALLET",
            status="UNDER_REVIEW",
            amount=amount,
            from_account_id=sender_wallet.id,
            to_account_id=recipient_wallet.id,
        )
        session.add(txn)
        await session.commit()
        await session.refresh(txn)
        logger.info("payment_under_review", txn_id=str(txn.id), sender_id=str(sender_id))
        return txn

    # 6. Deadlock prevention: Lock accounts in a fixed order (lower UUID first)
    lower_id, higher_id = (
        (sender_wallet.id, recipient_wallet.id)
        if str(sender_wallet.id) < str(recipient_wallet.id)
        else (recipient_wallet.id, sender_wallet.id)
    )

    # Lock lower id row
    stmt_lock_1 = select(Account).where(Account.id == lower_id).with_for_update()
    res1 = await session.execute(stmt_lock_1)
    acc_1 = res1.scalar_one()

    # Lock higher id row
    stmt_lock_2 = select(Account).where(Account.id == higher_id).with_for_update()
    res2 = await session.execute(stmt_lock_2)
    acc_2 = res2.scalar_one()

    # Re-identify locked objects
    locked_sender = acc_1 if acc_1.id == sender_wallet.id else acc_2
    locked_recipient = acc_2 if acc_2.id == recipient_wallet.id else acc_1

    # Verify balance
    if locked_sender.balance < amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Insufficient wallet balance", "code": "INSUFFICIENT_BALANCE"},
        )

    # 7. Create Transaction record (COMPLETED)
    txn = Transaction(
        idempotency_key=idempotency_key,
        type="P2P_WALLET",
        status="COMPLETED",
        amount=amount,
        from_account_id=locked_sender.id,
        to_account_id=locked_recipient.id,
    )
    session.add(txn)
    await session.flush()

    # 8. Create Double-Entry Ledger records
    ledger_entries = [
        {"account_id": locked_sender.id, "direction": "DEBIT", "amount": amount},
        {"account_id": locked_recipient.id, "direction": "CREDIT", "amount": amount},
    ]
    await create_ledger_entries(session, txn.id, ledger_entries)

    # 9. Outbox event (same DB transaction)
    event_payload = {
        "txn_id": str(txn.id),
        "type": "P2P_WALLET",
        "amount": amount,
        "from_user_id": str(sender_id),
        "to_user_id": str(recipient.id),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    outbox_event = Outbox(
        event_type="PaymentCompleted",
        payload=event_payload,
        published=False,
    )
    session.add(outbox_event)

    await session.commit()
    await session.refresh(txn)

    logger.info(
        "wallet_transfer_completed",
        txn_id=str(txn.id),
        sender_id=str(sender_id),
        recipient_id=str(recipient.id),
        amount=amount,
    )
    return txn


async def get_user_transactions(
    session: AsyncSession,
    user_id: uuid.UUID,
    status_filter: Optional[str] = None,
    type_filter: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> Tuple[List[Transaction], int]:
    # Find user's wallet account
    wallet_stmt = select(Account.id).where(
        Account.user_id == user_id, Account.type == "USER_WALLET"
    )
    wallet_res = await session.execute(wallet_stmt)
    wallet_id = wallet_res.scalar_one_or_none()
    if not wallet_id:
        return [], 0

    base_query = select(Transaction).where(
        or_(
            Transaction.from_account_id == wallet_id,
            Transaction.to_account_id == wallet_id,
        )
    )

    if status_filter:
        base_query = base_query.where(Transaction.status == status_filter)
    if type_filter:
        base_query = base_query.where(Transaction.type == type_filter)

    # Count
    count_stmt = select(func.count()).select_from(base_query.subquery())
    total_res = await session.execute(count_stmt)
    total = total_res.scalar() or 0

    # Paginated items
    items_stmt = (
        base_query.order_by(Transaction.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    items_res = await session.execute(items_stmt)
    items = list(items_res.scalars().all())

    return items, total


async def get_transaction_detail(
    session: AsyncSession,
    txn_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Transaction:
    # Verify user is involved or is admin
    wallet_stmt = select(Account.id).where(
        Account.user_id == user_id, Account.type == "USER_WALLET"
    )
    wallet_res = await session.execute(wallet_stmt)
    wallet_id = wallet_res.scalar_one_or_none()

    stmt = select(Transaction).where(Transaction.id == txn_id)
    result = await session.execute(stmt)
    txn = result.scalar_one_or_none()
    if not txn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Transaction not found", "code": "TXN_NOT_FOUND"},
        )

    # Verify authorization
    user = await session.get(User, user_id)
    is_admin = user and user.role == "ADMIN"
    if not is_admin and (txn.from_account_id != wallet_id and txn.to_account_id != wallet_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "Access denied to transaction", "code": "ACCESS_DENIED"},
        )

    return txn

