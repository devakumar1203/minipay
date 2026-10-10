import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.models import User
from app.auth.dependencies import get_current_user
from app.middleware.idempotency import require_idempotency_key
from app.funding.schemas import (
    InitiateLinkRequest,
    InitiateLinkResponse,
    CallbackLinkRequest,
    FundingSourceResponse,
    RequestLinkInput,
    LinkWebhookPayload,
    AddMoneyRequest,
    WithdrawRequest,
)
from app.funding.service import (
    initiate_bank_link,
    callback_bank_link,
    request_bank_link,
    handle_link_webhook,
    list_funding_sources,
    set_default_funding_source,
    revoke_funding_source,
    add_money,
    withdraw_to_bank,
)
from app.payment.schemas import TransactionResponse

router = APIRouter()


@router.post("/request-link", response_model=FundingSourceResponse, summary="Request async bank linking")
async def request_link_endpoint(
    req: RequestLinkInput,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    source = await request_bank_link(
        session=session,
        user_id=current_user.id,
        bank_id=req.bank_id,
        account_no=req.account_no,
    )
    return FundingSourceResponse.model_validate(source)


@router.post("/link-webhook", summary="Webhook called by bank when user approves or denies link request")
async def link_webhook_endpoint(
    payload: LinkWebhookPayload,
    session: AsyncSession = Depends(get_db),
):
    source = await handle_link_webhook(
        session=session,
        request_id=payload.request_id,
        status_str=payload.status,
        bank_id=payload.bank_id,
        token=payload.token,
        masked_account=payload.masked_account,
    )
    return {"status": "ok", "source_id": str(source.id), "source_status": source.status}


@router.post("/initiate-link", response_model=InitiateLinkResponse, summary="Initiate bank linking flow")
async def initiate_link_endpoint(
    req: InitiateLinkRequest,
    current_user: User = Depends(get_current_user),
):
    result = await initiate_bank_link(current_user.id, req.bank_id)
    return InitiateLinkResponse(**result)


@router.post("/callback", response_model=FundingSourceResponse, summary="Bank linking callback with authorization code")
async def callback_link_endpoint(
    req: CallbackLinkRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    source = await callback_bank_link(session, current_user.id, req.bank_id, req.code)
    return FundingSourceResponse.model_validate(source)


@router.get("/sources", response_model=List[FundingSourceResponse], summary="List linked funding sources")
async def list_sources_endpoint(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    sources = await list_funding_sources(session, current_user.id)
    return [FundingSourceResponse.model_validate(s) for s in sources]


@router.patch("/sources/{source_id}/default", response_model=FundingSourceResponse, summary="Set default funding source")
async def set_default_source_endpoint(
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    source = await set_default_funding_source(session, current_user.id, source_id)
    return FundingSourceResponse.model_validate(source)


@router.delete("/sources/{source_id}", summary="Revoke a linked funding source")
async def revoke_source_endpoint(
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await revoke_funding_source(session, current_user.id, source_id)
    return {"status": "REVOKED", "source_id": str(source_id)}


@router.post("/add-money", response_model=TransactionResponse, summary="Add money to wallet from linked bank account")
async def add_money_endpoint(
    req: AddMoneyRequest,
    current_user: User = Depends(get_current_user),
    idempotency_key: str = Depends(require_idempotency_key),
    session: AsyncSession = Depends(get_db),
):
    txn = await add_money(
        session=session,
        user_id=current_user.id,
        funding_source_id=req.funding_source_id,
        amount=req.amount,
        idempotency_key=idempotency_key,
    )
    return TransactionResponse.model_validate(txn)


@router.post("/withdraw", response_model=TransactionResponse, summary="Withdraw from wallet to linked bank account")
async def withdraw_endpoint(
    req: WithdrawRequest,
    current_user: User = Depends(get_current_user),
    idempotency_key: str = Depends(require_idempotency_key),
    session: AsyncSession = Depends(get_db),
):
    txn = await withdraw_to_bank(
        session=session,
        user_id=current_user.id,
        funding_source_id=req.funding_source_id,
        amount=req.amount,
        idempotency_key=idempotency_key,
    )
    return TransactionResponse.model_validate(txn)
