import secrets
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.database import get_db
from app.config import settings
from app.auth.models import BankUser
from app.auth.service import get_current_bank_user
from app.accounts.models import BankAccount, LinkConsent
from app.accounts.schemas import LinkConsentResponse

logger = structlog.get_logger()
router = APIRouter()


class CreateConsentRequest(BaseModel):
    account_no: str
    per_txn_limit: int = Field(default=5000000, gt=0)  # Default 50,000 INR
    paypal_request_id: str


class CreateConsentResponse(BaseModel):
    authorization_code: str
    consent_id: str
    paypal_request_id: str


@router.get("/consents", response_model=List[LinkConsentResponse], summary="List consents for current bank user")
async def list_user_consents(
    current_user: BankUser = Depends(get_current_bank_user),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(LinkConsent)
        .where(LinkConsent.user_id == current_user.id)
        .order_by(LinkConsent.created_at.desc())
    )
    res = await session.execute(stmt)
    consents = res.scalars().all()
    results = []
    for c in consents:
        masked = f"XXXX-{c.account_no[-4:]}" if len(c.account_no) >= 4 else f"XXXX-{c.account_no}"
        results.append(
            LinkConsentResponse(
                id=c.id,
                consent_id=c.consent_id,
                account_no=c.account_no,
                masked_account=masked,
                per_txn_limit=c.per_txn_limit,
                status=c.status,
                created_at=c.created_at,
            )
        )
    return results


@router.post("/consent", response_model=CreateConsentResponse, summary="Approve link consent and generate authorization code")
async def approve_consent_endpoint(
    req: CreateConsentRequest,
    current_user: BankUser = Depends(get_current_bank_user),
    session: AsyncSession = Depends(get_db),
):
    # Verify account belongs to user
    acc_stmt = select(BankAccount).where(
        BankAccount.account_no == req.account_no, BankAccount.user_id == current_user.id
    )
    acc_res = await session.execute(acc_stmt)
    account = acc_res.scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Bank account not found or not owned by user", "code": "ACCOUNT_NOT_FOUND"},
        )

    consent_id = f"consent-{uuid.uuid4()}"
    token = f"tok_{secrets.token_hex(32)}"
    auth_code = f"code_{secrets.token_hex(16)}"

    consent = LinkConsent(
        consent_id=consent_id,
        user_id=current_user.id,
        account_no=req.account_no,
        token=token,
        per_txn_limit=req.per_txn_limit,
        status="ACTIVE",
        authorization_code=auth_code,
    )
    session.add(consent)
    await session.commit()

    logger.info("consent_granted", user_id=str(current_user.id), consent_id=consent_id, account_no=req.account_no)
    return CreateConsentResponse(
        authorization_code=auth_code,
        consent_id=consent_id,
        paypal_request_id=req.paypal_request_id,
    )


@router.post("/revoke/{consent_id}", summary="Revoke a linked consent")
async def revoke_consent_endpoint(
    consent_id: str,
    current_user: BankUser = Depends(get_current_bank_user),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(LinkConsent).where(
        LinkConsent.consent_id == consent_id, LinkConsent.user_id == current_user.id
    )
    res = await session.execute(stmt)
    consent = res.scalar_one_or_none()
    if not consent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Consent not found", "code": "CONSENT_NOT_FOUND"},
        )

    consent.status = "REVOKED"
    await session.commit()
    logger.info("consent_revoked", consent_id=consent_id, user_id=str(current_user.id))
    return {"status": "REVOKED", "consent_id": consent_id}


async def notify_paypal_link_status(request_id: str, status_str: str, token: Optional[str] = None, masked_account: Optional[str] = None):
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                "http://paypal-backend:8000/api/funding/link-webhook",
                json={
                    "request_id": request_id,
                    "status": status_str,
                    "bank_id": settings.BANK_ID,
                    "token": token,
                    "masked_account": masked_account,
                },
            )
            logger.info("notified_paypal_link_webhook", request_id=request_id, status=status_str)
    except Exception as e:
        logger.warning("notify_paypal_webhook_failed", error=str(e), request_id=request_id)


@router.post("/approve-request/{request_id}", summary="Approve incoming link request from MiniPay")
async def approve_request_endpoint(
    request_id: str,
    current_user: BankUser = Depends(get_current_bank_user),
    session: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timezone
    from app.accounts.models import LinkRequest, BankNotification
    stmt = select(LinkRequest).where(
        LinkRequest.request_id == request_id,
        LinkRequest.user_id == current_user.id,
    )
    res = await session.execute(stmt)
    req = res.scalar_one_or_none()
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Link request not found", "code": "NOT_FOUND"},
        )
    if req.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": f"Link request is already {req.status}", "code": "ALREADY_RESOLVED"},
        )

    # Create LinkConsent
    consent_id = f"consent-{uuid.uuid4()}"
    token = f"tok_{secrets.token_hex(32)}"
    auth_code = f"code_{secrets.token_hex(16)}"

    consent = LinkConsent(
        consent_id=consent_id,
        user_id=current_user.id,
        account_no=req.account_no,
        token=token,
        per_txn_limit=req.per_txn_limit,
        status="ACTIVE",
        authorization_code=auth_code,
    )
    session.add(consent)

    # Update LinkRequest
    req.status = "APPROVED"
    req.resolved_at = datetime.now(timezone.utc)

    # Update BankNotification
    notif_stmt = select(BankNotification).where(
        BankNotification.reference_id == request_id,
        BankNotification.user_id == current_user.id,
    )
    notif_res = await session.execute(notif_stmt)
    notif = notif_res.scalar_one_or_none()
    if notif:
        notif.status = "APPROVED"
        notif.is_actionable = False
        notif.is_read = True

    await session.commit()

    masked = f"XXXX-{req.account_no[-4:]}" if len(req.account_no) >= 4 else f"XXXX-{req.account_no}"
    # Notify PayPal Webhook
    await notify_paypal_link_status(request_id, "APPROVED", token=token, masked_account=masked)

    return {
        "status": "APPROVED",
        "consent_id": consent_id,
        "token": token,
        "masked_account": masked,
    }


@router.post("/deny-request/{request_id}", summary="Deny incoming link request from MiniPay")
async def deny_request_endpoint(
    request_id: str,
    current_user: BankUser = Depends(get_current_bank_user),
    session: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timezone
    from app.accounts.models import LinkRequest, BankNotification
    stmt = select(LinkRequest).where(
        LinkRequest.request_id == request_id,
        LinkRequest.user_id == current_user.id,
    )
    res = await session.execute(stmt)
    req = res.scalar_one_or_none()
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Link request not found", "code": "NOT_FOUND"},
        )
    if req.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": f"Link request is already {req.status}", "code": "ALREADY_RESOLVED"},
        )

    req.status = "DENIED"
    req.resolved_at = datetime.now(timezone.utc)

    notif_stmt = select(BankNotification).where(
        BankNotification.reference_id == request_id,
        BankNotification.user_id == current_user.id,
    )
    notif_res = await session.execute(notif_stmt)
    notif = notif_res.scalar_one_or_none()
    if notif:
        notif.status = "DENIED"
        notif.is_actionable = False
        notif.is_read = True

    await session.commit()

    await notify_paypal_link_status(request_id, "DENIED")

    return {"status": "DENIED", "request_id": request_id}


