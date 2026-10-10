from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.database import get_db
from app.config import settings
from app.api.hmac_auth import verify_hmac
from app.accounts.models import BankAccount, BankTxn, LinkConsent

logger = structlog.get_logger()
router = APIRouter(dependencies=[Depends(verify_hmac)])


class DebitRequest(BaseModel):
    reference_id: str
    token: str
    amount: int = Field(..., gt=0)


class CreditRequest(BaseModel):
    reference_id: str
    token: str
    amount: int = Field(..., gt=0)


class ExchangeCodeRequest(BaseModel):
    code: str


class BankTxnResultResponse(BaseModel):
    reference_id: str
    status: str
    balance: Optional[int] = None
    reason: Optional[str] = None


class ExchangeCodeResponse(BaseModel):
    token: str
    masked_account: str
    bank_id: str


@router.post("/debit", response_model=BankTxnResultResponse, summary="Debit user bank account via consent token")
async def debit_endpoint(
    req: DebitRequest,
    session: AsyncSession = Depends(get_db),
):
    # 1. Idempotency on reference_id
    stmt = select(BankTxn).where(BankTxn.reference_id == req.reference_id)
    res = await session.execute(stmt)
    existing_txn = res.scalar_one_or_none()
    if existing_txn:
        # Get account balance
        acc_stmt = select(BankAccount.balance).where(BankAccount.account_no == existing_txn.account_no)
        acc_res = await session.execute(acc_stmt)
        current_balance = acc_res.scalar()
        logger.info("bank_debit_idempotent_hit", reference_id=req.reference_id, status=existing_txn.status)
        return BankTxnResultResponse(
            reference_id=existing_txn.reference_id,
            status=existing_txn.status,
            balance=current_balance,
            reason=existing_txn.reason,
        )

    # 2. Verify Consent Token
    consent_stmt = select(LinkConsent).where(LinkConsent.token == req.token)
    consent_res = await session.execute(consent_stmt)
    consent = consent_res.scalar_one_or_none()
    if not consent:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Invalid consent token", "code": "INVALID_TOKEN"},
        )
    if consent.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "Consent token is revoked", "code": "TOKEN_REVOKED"},
        )
    if req.amount > consent.per_txn_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": f"Amount exceeds consent per-transaction limit of {consent.per_txn_limit}", "code": "LIMIT_EXCEEDED"},
        )

    # 3. Lock Bank Account row
    acc_stmt = select(BankAccount).where(BankAccount.account_no == consent.account_no).with_for_update()
    acc_res = await session.execute(acc_stmt)
    account = acc_res.scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Associated bank account not found", "code": "ACCOUNT_NOT_FOUND"},
        )

    # 4. Check balance
    if account.balance < req.amount:
        txn = BankTxn(
            reference_id=req.reference_id,
            account_no=account.account_no,
            type="DEBIT",
            amount=req.amount,
            status="FAILED",
            reason="INSUFFICIENT_BALANCE",
        )
        session.add(txn)
        await session.commit()
        logger.warning("bank_debit_insufficient_funds", reference_id=req.reference_id, balance=account.balance, amount=req.amount)
        return BankTxnResultResponse(
            reference_id=req.reference_id,
            status="FAILED",
            balance=account.balance,
            reason="INSUFFICIENT_BALANCE",
        )

    # 5. Perform debit
    account.balance -= req.amount
    txn = BankTxn(
        reference_id=req.reference_id,
        account_no=account.account_no,
        type="DEBIT",
        amount=req.amount,
        status="APPROVED",
    )
    session.add(txn)
    await session.commit()
    await session.refresh(account)

    logger.info("bank_debit_approved", reference_id=req.reference_id, amount=req.amount, balance=account.balance)
    return BankTxnResultResponse(
        reference_id=req.reference_id,
        status="APPROVED",
        balance=account.balance,
    )


@router.post("/credit", response_model=BankTxnResultResponse, summary="Credit user bank account via consent token")
async def credit_endpoint(
    req: CreditRequest,
    session: AsyncSession = Depends(get_db),
):
    # 1. Idempotency on reference_id
    stmt = select(BankTxn).where(BankTxn.reference_id == req.reference_id)
    res = await session.execute(stmt)
    existing_txn = res.scalar_one_or_none()
    if existing_txn:
        acc_stmt = select(BankAccount.balance).where(BankAccount.account_no == existing_txn.account_no)
        acc_res = await session.execute(acc_stmt)
        current_balance = acc_res.scalar()
        logger.info("bank_credit_idempotent_hit", reference_id=req.reference_id, status=existing_txn.status)
        return BankTxnResultResponse(
            reference_id=existing_txn.reference_id,
            status=existing_txn.status,
            balance=current_balance,
            reason=existing_txn.reason,
        )

    # 2. Verify Consent Token
    consent_stmt = select(LinkConsent).where(LinkConsent.token == req.token)
    consent_res = await session.execute(consent_stmt)
    consent = consent_res.scalar_one_or_none()
    if not consent:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Invalid consent token", "code": "INVALID_TOKEN"},
        )
    if consent.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "Consent token is revoked", "code": "TOKEN_REVOKED"},
        )

    # 3. Lock Bank Account row
    acc_stmt = select(BankAccount).where(BankAccount.account_no == consent.account_no).with_for_update()
    acc_res = await session.execute(acc_stmt)
    account = acc_res.scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Associated bank account not found", "code": "ACCOUNT_NOT_FOUND"},
        )

    # 4. Perform credit
    account.balance += req.amount
    txn = BankTxn(
        reference_id=req.reference_id,
        account_no=account.account_no,
        type="CREDIT",
        amount=req.amount,
        status="APPROVED",
    )
    session.add(txn)
    await session.commit()
    await session.refresh(account)

    logger.info("bank_credit_approved", reference_id=req.reference_id, amount=req.amount, balance=account.balance)
    return BankTxnResultResponse(
        reference_id=req.reference_id,
        status="APPROVED",
        balance=account.balance,
    )


@router.get("/status/{reference_id}", response_model=BankTxnResultResponse, summary="Query transaction status by reference_id")
async def get_txn_status_endpoint(
    reference_id: str,
    session: AsyncSession = Depends(get_db),
):
    stmt = select(BankTxn).where(BankTxn.reference_id == reference_id)
    res = await session.execute(stmt)
    txn = res.scalar_one_or_none()
    if not txn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Bank transaction not found", "code": "TXN_NOT_FOUND"},
        )

    return BankTxnResultResponse(
        reference_id=txn.reference_id,
        status=txn.status,
        reason=txn.reason,
    )


@router.post("/exchange-code", response_model=ExchangeCodeResponse, summary="Exchange authorization code for token")
async def exchange_code_endpoint(
    req: ExchangeCodeRequest,
    session: AsyncSession = Depends(get_db),
):
    stmt = select(LinkConsent).where(LinkConsent.authorization_code == req.code)
    res = await session.execute(stmt)
    consent = res.scalar_one_or_none()
    if not consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Invalid or expired authorization code", "code": "INVALID_CODE"},
        )

    # Invalidate code (single use)
    token = consent.token
    consent.authorization_code = None
    await session.commit()

    masked = f"XXXX-{consent.account_no[-4:]}" if len(consent.account_no) >= 4 else f"XXXX-{consent.account_no}"
    logger.info("authorization_code_exchanged", consent_id=consent.consent_id, masked_account=masked)
    return ExchangeCodeResponse(
        token=token,
        masked_account=masked,
        bank_id=settings.BANK_ID,
    )


@router.post("/link-request", summary="Receive link request from PayPal")
async def create_link_request_endpoint(
    req: dict,
    session: AsyncSession = Depends(get_db),
):
    from app.accounts.models import LinkRequest, BankNotification
    request_id = req.get("request_id")
    account_no = req.get("account_no", "").strip().upper()
    requester_name = req.get("requester_name", "MiniPay")
    purpose = req.get("purpose", "Link bank account for payments")
    per_txn_limit = req.get("per_txn_limit", 5000000)

    if not request_id or not account_no:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "request_id and account_no are required", "code": "INVALID_REQUEST"},
        )

    # 1. Idempotency check on request_id
    existing_stmt = select(LinkRequest).where(LinkRequest.request_id == request_id)
    existing_res = await session.execute(existing_stmt)
    existing_req = existing_res.scalar_one_or_none()
    if existing_req:
        return {
            "request_id": existing_req.request_id,
            "account_no": existing_req.account_no,
            "status": existing_req.status,
            "created_at": existing_req.created_at.isoformat(),
        }

    # 2. Look up bank account
    acc_stmt = select(BankAccount).where(BankAccount.account_no == account_no)
    acc_res = await session.execute(acc_stmt)
    account = acc_res.scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": f"Bank account {account_no} not found at {settings.BANK_NAME}", "code": "ACCOUNT_NOT_FOUND"},
        )

    # 3. Create LinkRequest
    link_req = LinkRequest(
        request_id=request_id,
        account_no=account.account_no,
        user_id=account.user_id,
        requester_name=requester_name,
        purpose=purpose,
        per_txn_limit=per_txn_limit,
        status="PENDING",
    )
    session.add(link_req)

    # 4. Create BankNotification
    limit_inr = per_txn_limit // 100
    notif = BankNotification(
        user_id=account.user_id,
        type="LINK_REQUEST",
        title="MiniPay Link Request",
        message=f"{requester_name} has requested to link your account {account.account_no} for payments up to ₹{limit_inr:,.2f}.",
        reference_id=request_id,
        is_read=False,
        is_actionable=True,
        status="PENDING",
    )
    session.add(notif)
    await session.commit()
    await session.refresh(link_req)

    logger.info("link_request_created", request_id=request_id, account_no=account_no, bank_user_id=str(account.user_id))
    return {
        "request_id": link_req.request_id,
        "account_no": link_req.account_no,
        "status": link_req.status,
        "created_at": link_req.created_at.isoformat(),
    }


