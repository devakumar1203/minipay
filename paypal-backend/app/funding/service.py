import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
import structlog

from app.config import settings
from app.auth.models import User
from app.wallet.models import Account, LedgerEntry
from app.wallet.service import (
    get_wallet,
    get_or_create_bank_external_account,
    create_ledger_entries,
)
from app.funding.models import FundingSource
from app.payment.models import Transaction, SagaState
from app.outbox.models import Outbox
from app.bank_client.client import BankClient, BankUnavailableError
from app.fraud.service import check_fraud, FraudDecision
from app.redis_client import get_redis

logger = structlog.get_logger()


async def initiate_bank_link(user_id: uuid.UUID, bank_id: str) -> dict:
    if bank_id not in ("bank_x", "bank_y"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": f"Unsupported bank_id: {bank_id}", "code": "INVALID_BANK"},
        )

    paypal_request_id = str(uuid.uuid4())
    # Bank Web UI port is 3010 for Bank X and 3020 for Bank Y
    bank_web_port = 3010 if bank_id == "bank_x" else 3020
    redirect_url = f"http://localhost:{bank_web_port}/consent?paypal_request_id={paypal_request_id}&bank_id={bank_id}"

    return {"redirect_url": redirect_url, "paypal_request_id": paypal_request_id}


async def callback_bank_link(
    session: AsyncSession, user_id: uuid.UUID, bank_id: str, code: str
) -> FundingSource:
    bank_client = BankClient(bank_id)
    try:
        data = await bank_client.exchange_code(code)
    except Exception as e:
        logger.error("bank_token_exchange_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Failed to exchange code with bank", "code": "TOKEN_EXCHANGE_FAILED"},
        )

    token = data.get("token")
    masked_account = data.get("masked_account", "XXXX-XXXX")

    # Check if user already has active funding sources
    stmt = select(FundingSource).where(
        FundingSource.user_id == user_id, FundingSource.status == "ACTIVE"
    )
    res = await session.execute(stmt)
    existing_sources = res.scalars().all()
    is_default = len(existing_sources) == 0

    source = FundingSource(
        user_id=user_id,
        bank_id=bank_id,
        token=token,
        masked_account=masked_account,
        is_default=is_default,
        status="ACTIVE",
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)

    logger.info("funding_source_linked", user_id=str(user_id), source_id=str(source.id), masked=masked_account)
    return source


async def request_bank_link(
    session: AsyncSession,
    user_id: uuid.UUID,
    bank_id: str,
    account_no: str,
) -> FundingSource:
    if bank_id not in ("bank_x", "bank_y"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": f"Invalid bank_id: '{bank_id}'. Expected 'bank_x' or 'bank_y'", "code": "INVALID_BANK"},
        )

    clean_account = account_no.strip().upper()
    req_id = f"req-{uuid.uuid4()}"

    # Call Bank's link-request endpoint via BankClient
    bank_client = BankClient(bank_id)
    try:
        await bank_client.request_link(
            request_id=req_id,
            account_no=clean_account,
            requester_name="MiniPay",
            purpose="Link bank account for payments and transfers",
            per_txn_limit=5000000,
        )
    except Exception as e:
        logger.error("bank_link_request_failed", error=str(e), bank_id=bank_id, account_no=clean_account)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": f"Failed to send link request to bank: {str(e)}", "code": "BANK_ERROR"},
        )

    masked = f"XXXX-{clean_account[-4:]}" if len(clean_account) >= 4 else f"XXXX-{clean_account}"

    # Create FundingSource with status PENDING
    source = FundingSource(
        user_id=user_id,
        bank_id=bank_id,
        token="PENDING",
        masked_account=masked,
        status="PENDING",
        link_request_id=req_id,
        is_default=False,
    )
    session.add(source)

    # Set user onboarding_step = 4 (completed onboarding)
    user = await session.get(User, user_id)
    if user and user.onboarding_step < 4:
        user.onboarding_step = 4

    await session.commit()
    await session.refresh(source)
    logger.info("funding_source_link_requested", user_id=str(user_id), bank_id=bank_id, request_id=req_id)
    return source


async def handle_link_webhook(
    session: AsyncSession,
    request_id: str,
    status_str: str,
    bank_id: str,
    token: Optional[str] = None,
    masked_account: Optional[str] = None,
) -> FundingSource:
    stmt = select(FundingSource).where(FundingSource.link_request_id == request_id)
    res = await session.execute(stmt)
    source = res.scalar_one_or_none()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Funding source for this request_id not found", "code": "NOT_FOUND"},
        )

    if status_str == "APPROVED":
        source.status = "ACTIVE"
        if token:
            source.token = token
        if masked_account:
            source.masked_account = masked_account

        # If this user has no other default source, make this default
        count_stmt = select(func.count(FundingSource.id)).where(
            FundingSource.user_id == source.user_id,
            FundingSource.status == "ACTIVE",
            FundingSource.is_default.is_(True),
        )
        count_res = await session.execute(count_stmt)
        if (count_res.scalar() or 0) == 0:
            source.is_default = True

        logger.info("funding_source_approved_via_webhook", source_id=str(source.id), request_id=request_id)
    elif status_str in ("DENIED", "REJECTED"):
        source.status = "DENIED"
        logger.info("funding_source_denied_via_webhook", source_id=str(source.id), request_id=request_id)

    await session.commit()
    await session.refresh(source)
    return source


async def list_funding_sources(session: AsyncSession, user_id: uuid.UUID) -> List[FundingSource]:
    stmt = (
        select(FundingSource)
        .where(
            FundingSource.user_id == user_id,
            FundingSource.status.in_(["ACTIVE", "PENDING"]),
        )
        .order_by(FundingSource.is_default.desc(), FundingSource.created_at.desc())
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def set_default_funding_source(
    session: AsyncSession, user_id: uuid.UUID, source_id: uuid.UUID
) -> FundingSource:
    # Unset all default
    await session.execute(
        update(FundingSource)
        .where(FundingSource.user_id == user_id)
        .values(is_default=False)
    )
    # Set this one
    target = await session.get(FundingSource, source_id)
    if not target or target.user_id != user_id or target.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Active funding source not found", "code": "SOURCE_NOT_FOUND"},
        )
    target.is_default = True
    await session.commit()
    await session.refresh(target)
    return target


async def revoke_funding_source(
    session: AsyncSession, user_id: uuid.UUID, source_id: uuid.UUID
) -> None:
    target = await session.get(FundingSource, source_id)
    if not target or target.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Funding source not found", "code": "SOURCE_NOT_FOUND"},
        )
    target.status = "REVOKED"
    target.is_default = False
    await session.commit()
    logger.info("funding_source_revoked_locally", source_id=str(source_id), user_id=str(user_id))


# ==============================================================================
# SAGA 1: ADD MONEY (Bank -> Wallet)
# ==============================================================================
async def add_money(
    session: AsyncSession,
    user_id: uuid.UUID,
    funding_source_id: uuid.UUID,
    amount: int,
    idempotency_key: str,
) -> Transaction:
    # Idempotency check
    stmt = select(Transaction).where(Transaction.idempotency_key == idempotency_key)
    res = await session.execute(stmt)
    existing_txn = res.scalar_one_or_none()
    if existing_txn:
        return existing_txn

    # Lookup funding source
    source = await session.get(FundingSource, funding_source_id)
    if not source or source.user_id != user_id or source.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Invalid or revoked funding source", "code": "INVALID_FUNDING_SOURCE"},
        )

    # Fraud check
    redis = await get_redis()
    decision = await check_fraud(user_id, amount, "ADD_MONEY", redis, session)
    if decision == FraudDecision.BLOCK:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "Transaction blocked by fraud rules", "code": "FRAUD_BLOCKED"},
        )

    user_wallet = await get_wallet(session, user_id)
    bank_external_account = await get_or_create_bank_external_account(session, source.bank_id)

    # Step 1: Create Transaction PENDING
    txn_status = "UNDER_REVIEW" if decision == FraudDecision.REVIEW else "PENDING"
    txn = Transaction(
        idempotency_key=idempotency_key,
        type="ADD_MONEY",
        status=txn_status,
        amount=amount,
        from_account_id=bank_external_account.id,
        to_account_id=user_wallet.id,
        funding_source_id=source.id,
    )
    session.add(txn)
    await session.flush()

    saga_step_1 = SagaState(
        txn_id=txn.id,
        step="CREATE_TXN",
        status="COMPLETED",
    )
    session.add(saga_step_1)
    await session.commit()

    if decision == FraudDecision.REVIEW:
        return txn

    # Step 2: Bank Debit
    bank_client = BankClient(source.bank_id)
    try:
        debit_res = await bank_client.debit(
            reference_id=str(txn.id),
            token=source.token,
            amount=amount,
        )
    except BankUnavailableError as e:
        txn.status = "FAILED"
        saga_fail = SagaState(txn_id=txn.id, step="BANK_DEBIT", status="FAILED", error_detail=str(e))
        session.add(saga_fail)
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"detail": str(e), "code": "BANK_UNAVAILABLE"},
        )
    except Exception as e:
        # Keep PENDING for reconciliation
        saga_pending = SagaState(txn_id=txn.id, step="BANK_DEBIT", status="PENDING", error_detail=str(e))
        session.add(saga_pending)
        await session.commit()
        return txn

    if debit_res.get("status") != "APPROVED":
        txn.status = "FAILED"
        reason = debit_res.get("reason", "DEBIT_FAILED")
        error_msg = "Insufficient bank balance" if reason == "INSUFFICIENT_BALANCE" else f"Bank debit failed: {reason}"
        saga_fail = SagaState(
            txn_id=txn.id,
            step="BANK_DEBIT",
            status="FAILED",
            error_detail=error_msg,
        )
        session.add(saga_fail)
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": error_msg, "code": "INSUFFICIENT_BALANCE" if reason == "INSUFFICIENT_BALANCE" else "DEBIT_FAILED"},
        )

    saga_step_2 = SagaState(txn_id=txn.id, step="BANK_DEBIT", status="COMPLETED")
    session.add(saga_step_2)

    # Step 3: Credit Wallet on Ledger
    try:
        ledger_entries = [
            {"account_id": bank_external_account.id, "direction": "DEBIT", "amount": amount},
            {"account_id": user_wallet.id, "direction": "CREDIT", "amount": amount},
        ]
        await create_ledger_entries(session, txn.id, ledger_entries)
        txn.status = "COMPLETED"

        outbox_event = Outbox(
            event_type="PaymentCompleted",
            payload={
                "txn_id": str(txn.id),
                "type": "ADD_MONEY",
                "amount": amount,
                "user_id": str(user_id),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            published=False,
        )
        session.add(outbox_event)

        saga_step_3 = SagaState(txn_id=txn.id, step="CREDIT_WALLET", status="COMPLETED")
        session.add(saga_step_3)
        await session.commit()
        await session.refresh(txn)
        return txn

    except Exception as e:
        # Compensation: refund money back to bank account
        logger.error("add_money_ledger_failed_compensating", txn_id=str(txn.id), error=str(e))
        try:
            await bank_client.credit(
                reference_id=f"{txn.id}-comp",
                token=source.token,
                amount=amount,
            )
        except Exception as comp_err:
            logger.critical("compensation_failed", txn_id=str(txn.id), error=str(comp_err))

        txn.status = "FAILED"
        saga_comp = SagaState(
            txn_id=txn.id, step="COMPENSATION", status="COMPLETED", error_detail=str(e)
        )
        session.add(saga_comp)
        await session.commit()
        return txn


# ==============================================================================
# SAGA 2: P2P FROM BANK (Bank -> Recipient Wallet)
# ==============================================================================
async def transfer_bank_to_wallet(
    session: AsyncSession,
    sender_id: uuid.UUID,
    recipient_email: str,
    funding_source_id: uuid.UUID,
    amount: int,
    idempotency_key: str,
) -> Transaction:
    # Idempotency check
    stmt = select(Transaction).where(Transaction.idempotency_key == idempotency_key)
    res = await session.execute(stmt)
    existing_txn = res.scalar_one_or_none()
    if existing_txn:
        return existing_txn

    # Lookup recipient
    clean_email = recipient_email.lower().strip()
    stmt = select(User).where(User.email == clean_email)
    res = await session.execute(stmt)
    recipient = res.scalar_one_or_none()
    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Recipient user not found", "code": "RECIPIENT_NOT_FOUND"},
        )
    if sender_id == recipient.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Cannot send money to yourself", "code": "SELF_TRANSFER_NOT_ALLOWED"},
        )
    if recipient.status == "BLOCKED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Recipient account is blocked", "code": "RECIPIENT_BLOCKED"},
        )

    source = await session.get(FundingSource, funding_source_id)
    if not source or source.user_id != sender_id or source.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Invalid or revoked funding source", "code": "INVALID_FUNDING_SOURCE"},
        )

    # Fraud check
    redis = await get_redis()
    decision = await check_fraud(sender_id, amount, "P2P_BANK", redis, session)
    if decision == FraudDecision.BLOCK:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "Transaction blocked by fraud rules", "code": "FRAUD_BLOCKED"},
        )

    recipient_wallet = await get_wallet(session, recipient.id)
    bank_external_account = await get_or_create_bank_external_account(session, source.bank_id)

    # Step 1: Create Transaction PENDING
    txn_status = "UNDER_REVIEW" if decision == FraudDecision.REVIEW else "PENDING"
    txn = Transaction(
        idempotency_key=idempotency_key,
        type="P2P_BANK",
        status=txn_status,
        amount=amount,
        from_account_id=bank_external_account.id,
        to_account_id=recipient_wallet.id,
        funding_source_id=source.id,
    )
    session.add(txn)
    await session.flush()

    saga_step_1 = SagaState(txn_id=txn.id, step="CREATE_TXN", status="COMPLETED")
    session.add(saga_step_1)
    await session.commit()

    if decision == FraudDecision.REVIEW:
        return txn

    # Step 2: Bank Debit
    bank_client = BankClient(source.bank_id)
    try:
        debit_res = await bank_client.debit(
            reference_id=str(txn.id),
            token=source.token,
            amount=amount,
        )
    except BankUnavailableError as e:
        txn.status = "FAILED"
        saga_fail = SagaState(txn_id=txn.id, step="BANK_DEBIT", status="FAILED", error_detail=str(e))
        session.add(saga_fail)
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"detail": str(e), "code": "BANK_UNAVAILABLE"},
        )
    except Exception as e:
        # Keep PENDING for reconciliation
        saga_pending = SagaState(txn_id=txn.id, step="BANK_DEBIT", status="PENDING", error_detail=str(e))
        session.add(saga_pending)
        await session.commit()
        return txn

    if debit_res.get("status") != "APPROVED":
        txn.status = "FAILED"
        saga_fail = SagaState(
            txn_id=txn.id,
            step="BANK_DEBIT",
            status="FAILED",
            error_detail=debit_res.get("reason", "DEBIT_FAILED"),
        )
        session.add(saga_fail)
        await session.commit()
        return txn

    saga_step_2 = SagaState(txn_id=txn.id, step="BANK_DEBIT", status="COMPLETED")
    session.add(saga_step_2)

    # Step 3: Credit Recipient Wallet
    try:
        ledger_entries = [
            {"account_id": bank_external_account.id, "direction": "DEBIT", "amount": amount},
            {"account_id": recipient_wallet.id, "direction": "CREDIT", "amount": amount},
        ]
        await create_ledger_entries(session, txn.id, ledger_entries)
        txn.status = "COMPLETED"

        outbox_event = Outbox(
            event_type="PaymentCompleted",
            payload={
                "txn_id": str(txn.id),
                "type": "P2P_BANK",
                "amount": amount,
                "from_user_id": str(sender_id),
                "to_user_id": str(recipient.id),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            published=False,
        )
        session.add(outbox_event)

        saga_step_3 = SagaState(txn_id=txn.id, step="CREDIT_RECIPIENT", status="COMPLETED")
        session.add(saga_step_3)
        await session.commit()
        await session.refresh(txn)
        return txn

    except Exception as e:
        logger.error("p2p_bank_ledger_failed_compensating", txn_id=str(txn.id), error=str(e))
        try:
            await bank_client.credit(
                reference_id=f"{txn.id}-comp",
                token=source.token,
                amount=amount,
            )
        except Exception as comp_err:
            logger.critical("compensation_failed", txn_id=str(txn.id), error=str(comp_err))

        txn.status = "FAILED"
        saga_comp = SagaState(
            txn_id=txn.id, step="COMPENSATION", status="COMPLETED", error_detail=str(e)
        )
        session.add(saga_comp)
        await session.commit()
        return txn


# ==============================================================================
# SAGA 3: WITHDRAW (Wallet -> Bank, Reserve-First Pattern)
# ==============================================================================
async def withdraw_to_bank(
    session: AsyncSession,
    user_id: uuid.UUID,
    funding_source_id: uuid.UUID,
    amount: int,
    idempotency_key: str,
) -> Transaction:
    # Idempotency check
    stmt = select(Transaction).where(Transaction.idempotency_key == idempotency_key)
    res = await session.execute(stmt)
    existing_txn = res.scalar_one_or_none()
    if existing_txn:
        return existing_txn

    source = await session.get(FundingSource, funding_source_id)
    if not source or source.user_id != user_id or source.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Invalid or revoked funding source", "code": "INVALID_FUNDING_SOURCE"},
        )

    # Fraud check
    redis = await get_redis()
    decision = await check_fraud(user_id, amount, "WITHDRAW", redis, session)
    if decision == FraudDecision.BLOCK:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "Withdrawal blocked by fraud rules", "code": "FRAUD_BLOCKED"},
        )

    user_wallet = await get_wallet(session, user_id)
    bank_external_account = await get_or_create_bank_external_account(session, source.bank_id)

    # Step 1: RESERVE FIRST in local DB transaction
    # Lock user wallet row
    wallet_stmt = select(Account).where(Account.id == user_wallet.id).with_for_update()
    wallet_res = await session.execute(wallet_stmt)
    locked_wallet = wallet_res.scalar_one()

    if locked_wallet.balance < amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Insufficient wallet balance for withdrawal", "code": "INSUFFICIENT_BALANCE"},
        )

    txn = Transaction(
        idempotency_key=idempotency_key,
        type="WITHDRAW",
        status="UNDER_REVIEW" if decision == FraudDecision.REVIEW else "PENDING",
        amount=amount,
        from_account_id=locked_wallet.id,
        to_account_id=bank_external_account.id,
        funding_source_id=source.id,
    )
    session.add(txn)
    await session.flush()

    if decision != FraudDecision.REVIEW:
        # Reserve funds: DEBIT wallet, CREDIT bank external
        ledger_entries = [
            {"account_id": locked_wallet.id, "direction": "DEBIT", "amount": amount},
            {"account_id": bank_external_account.id, "direction": "CREDIT", "amount": amount},
        ]
        await create_ledger_entries(session, txn.id, ledger_entries)

    saga_step_1 = SagaState(txn_id=txn.id, step="RESERVE", status="COMPLETED")
    session.add(saga_step_1)
    await session.commit()

    if decision == FraudDecision.REVIEW:
        return txn

    # Step 2: Call Bank /credit
    bank_client = BankClient(source.bank_id)
    try:
        credit_res = await bank_client.credit(
            reference_id=str(txn.id),
            token=source.token,
            amount=amount,
        )
    except BankUnavailableError as e:
        # Reverse hold immediately
        await _reverse_withdrawal_hold(session, txn, user_wallet.id, bank_external_account.id, amount)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"detail": str(e), "code": "BANK_UNAVAILABLE"},
        )
    except Exception as e:
        # Bank call timed out or failed to connect — DO NOT GUESS! Keep PENDING.
        saga_pending = SagaState(txn_id=txn.id, step="BANK_CREDIT", status="PENDING", error_detail=str(e))
        session.add(saga_pending)
        await session.commit()
        return txn

    if credit_res.get("status") == "APPROVED":
        txn.status = "COMPLETED"
        outbox_event = Outbox(
            event_type="WithdrawalCompleted",
            payload={
                "txn_id": str(txn.id),
                "user_id": str(user_id),
                "amount": amount,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            published=False,
        )
        session.add(outbox_event)
        saga_step_2 = SagaState(txn_id=txn.id, step="BANK_CREDIT", status="COMPLETED")
        session.add(saga_step_2)
        await session.commit()
        await session.refresh(txn)
        return txn
    else:
        # Bank returned FAILED -> reverse the hold and refund wallet
        await _reverse_withdrawal_hold(session, txn, user_wallet.id, bank_external_account.id, amount)
        reason = credit_res.get("reason", "CREDIT_FAILED")
        error_msg = f"Bank withdrawal failed: {reason}"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": error_msg, "code": "WITHDRAWAL_FAILED"},
        )


async def _reverse_withdrawal_hold(
    session: AsyncSession,
    txn: Transaction,
    user_wallet_id: uuid.UUID,
    bank_external_id: uuid.UUID,
    amount: int,
) -> None:
    # Compensating ledger entries: DEBIT bank_external, CREDIT user_wallet
    reversal_entries = [
        {"account_id": bank_external_id, "direction": "DEBIT", "amount": amount},
        {"account_id": user_wallet_id, "direction": "CREDIT", "amount": amount},
    ]
    await create_ledger_entries(session, txn.id, reversal_entries)
    txn.status = "FAILED"
    saga_comp = SagaState(txn_id=txn.id, step="REVERSE_HOLD", status="COMPLETED")
    session.add(saga_comp)
    await session.commit()
    logger.info("withdrawal_hold_reversed_refunded", txn_id=str(txn.id), amount=amount)

