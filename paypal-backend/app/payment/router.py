import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.models import User
from app.auth.dependencies import get_current_user
from app.middleware.idempotency import require_idempotency_key
from app.payment.schemas import (
    SendMoneyRequest,
    TransactionResponse,
    TransactionDetailResponse,
    PaginatedTransactionsResponse,
    SagaStateResponse,
)
from app.payment.service import (
    transfer_wallet_to_wallet,
    get_user_transactions,
    get_transaction_detail,
)
from app.wallet.models import LedgerEntry
from app.wallet.schemas import LedgerEntryResponse
from app.payment.models import SagaState

router = APIRouter()


@router.post(
    "/send",
    response_model=TransactionResponse,
    status_code=status.HTTP_200_OK,
    summary="Send money to another user (P2P from Wallet or Bank)",
)
async def send_money_endpoint(
    req: SendMoneyRequest,
    current_user: User = Depends(get_current_user),
    idempotency_key: str = Depends(require_idempotency_key),
    session: AsyncSession = Depends(get_db),
):
    if req.source == "WALLET":
        txn = await transfer_wallet_to_wallet(
            session=session,
            sender_id=current_user.id,
            recipient_email=req.recipient_email,
            amount=req.amount,
            idempotency_key=idempotency_key,
        )
        return txn
    else:
        # Bank-funded P2P flow (handled by funding/saga service)
        from app.funding.service import transfer_bank_to_wallet
        try:
            funding_source_id = uuid.UUID(req.source)
        except ValueError:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "Invalid funding source ID", "code": "INVALID_FUNDING_SOURCE"},
            )
        txn = await transfer_bank_to_wallet(
            session=session,
            sender_id=current_user.id,
            recipient_email=req.recipient_email,
            funding_source_id=funding_source_id,
            amount=req.amount,
            idempotency_key=idempotency_key,
        )
        return txn


@router.get(
    "",
    response_model=PaginatedTransactionsResponse,
    summary="List transactions for the current user",
)
async def list_transactions_endpoint(
    status_filter: Optional[str] = Query(None, alias="status"),
    type_filter: Optional[str] = Query(None, alias="type"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    items, total = await get_user_transactions(
        session=session,
        user_id=current_user.id,
        status_filter=status_filter,
        type_filter=type_filter,
        page=page,
        per_page=per_page,
    )
    return PaginatedTransactionsResponse(
        items=[TransactionResponse.model_validate(t) for t in items],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get(
    "/{txn_id}",
    response_model=TransactionDetailResponse,
    summary="Get transaction detail with ledger entries and saga steps",
)
async def get_transaction_detail_endpoint(
    txn_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    txn = await get_transaction_detail(session, txn_id, current_user.id)

    # Fetch ledger entries
    ledger_stmt = (
        select(LedgerEntry)
        .where(LedgerEntry.txn_id == txn_id)
        .order_by(LedgerEntry.created_at.asc())
    )
    ledger_res = await session.execute(ledger_stmt)
    ledger_entries = ledger_res.scalars().all()

    # Fetch saga states
    saga_stmt = (
        select(SagaState)
        .where(SagaState.txn_id == txn_id)
        .order_by(SagaState.updated_at.asc())
    )
    saga_res = await session.execute(saga_stmt)
    saga_states = saga_res.scalars().all()

    detail = TransactionDetailResponse(
        id=txn.id,
        idempotency_key=txn.idempotency_key,
        type=txn.type,
        status=txn.status,
        amount=txn.amount,
        from_account_id=txn.from_account_id,
        to_account_id=txn.to_account_id,
        funding_source_id=txn.funding_source_id,
        created_at=txn.created_at,
        updated_at=txn.updated_at,
        ledger_entries=[LedgerEntryResponse.model_validate(e) for e in ledger_entries],
        saga_states=[SagaStateResponse.model_validate(s) for s in saga_states],
    )
    return detail
