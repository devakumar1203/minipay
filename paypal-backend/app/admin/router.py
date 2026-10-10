import json
import uuid
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
import httpx

from app.database import get_db
from app.config import settings
from app.auth.models import User
from app.auth.schemas import UserResponse
from app.auth.dependencies import require_admin
from app.wallet.models import Account, LedgerEntry
from app.wallet.schemas import LedgerEntryResponse
from app.funding.models import FundingSource
from app.funding.schemas import FundingSourceResponse
from app.payment.models import Transaction, SagaState
from app.payment.schemas import (
    TransactionResponse,
    TransactionDetailResponse,
    PaginatedTransactionsResponse,
    SagaStateResponse,
)
from app.admin.models import AdminAction
from app.admin.schemas import (
    AdminDashboardResponse,
    AdminUserDetailResponse,
    AdminActionRequest,
    AdminActionResponse,
    FraudConfigResponse,
    UpdateFraudConfigRequest,
)
from app.admin.service import (
    get_dashboard_metrics,
    block_user,
    unblock_user,
    approve_review_transaction,
    reject_review_transaction,
    reverse_completed_p2p_transaction,
)
from app.fraud.service import get_fraud_config
from app.reconciliation.job import reconciliation_job
from app.redis_client import get_redis

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/dashboard", response_model=AdminDashboardResponse, summary="Admin dashboard statistics")
async def dashboard_endpoint(
    session: AsyncSession = Depends(get_db),
):
    metrics = await get_dashboard_metrics(session)
    return AdminDashboardResponse(**metrics)


@router.get("/users", response_model=Dict[str, Any], summary="List and search users")
async def list_users_endpoint(
    search: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    query = select(User)
    if search:
        query = query.where(User.email.ilike(f"%{search.strip()}%"))
    if status_filter:
        query = query.where(User.status == status_filter)

    count_res = await session.execute(select(func.count()).select_from(query.subquery()))
    total = count_res.scalar() or 0

    items_stmt = query.order_by(User.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    items_res = await session.execute(items_stmt)
    users = items_res.scalars().all()

    return {
        "items": [UserResponse.model_validate(u) for u in users],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/users/{user_id}", response_model=AdminUserDetailResponse, summary="Get user details with wallet and funding sources")
async def get_user_detail_endpoint(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "User not found", "code": "USER_NOT_FOUND"},
        )

    # Wallet balance
    wallet_stmt = select(Account).where(Account.user_id == user.id, Account.type == "USER_WALLET")
    wallet_res = await session.execute(wallet_stmt)
    wallet = wallet_res.scalar_one_or_none()
    wallet_balance = wallet.balance if wallet else 0

    # Funding sources (tokens masked!)
    sources_stmt = select(FundingSource).where(FundingSource.user_id == user.id)
    sources_res = await session.execute(sources_stmt)
    sources = sources_res.scalars().all()

    return AdminUserDetailResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        status=user.status,
        blocked_reason=user.blocked_reason,
        blocked_at=user.blocked_at,
        wallet_balance=wallet_balance,
        funding_sources=[FundingSourceResponse.model_validate(s) for s in sources],
        created_at=user.created_at,
    )


@router.post("/users/{user_id}/block", response_model=UserResponse, summary="Block a user immediately across instances")
async def block_user_endpoint(
    user_id: uuid.UUID,
    req: AdminActionRequest,
    current_admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    user = await block_user(session, redis, current_admin.id, user_id, req.reason)
    return UserResponse.model_validate(user)


@router.post("/users/{user_id}/unblock", response_model=UserResponse, summary="Unblock a user")
async def unblock_user_endpoint(
    user_id: uuid.UUID,
    req: AdminActionRequest,
    current_admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    user = await unblock_user(session, redis, current_admin.id, user_id, req.reason)
    return UserResponse.model_validate(user)


@router.post("/users/{user_id}/unlock", summary="Clear brute force login lockout for user")
async def unlock_user_lockout_endpoint(
    user_id: uuid.UUID,
    req: AdminActionRequest,
    current_admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "User not found", "code": "USER_NOT_FOUND"},
        )

    lockout_key = f"login_attempts:{user.email.lower().strip()}"
    await redis.delete(lockout_key)

    action = AdminAction(
        admin_id=current_admin.id,
        action="UNLOCK_USER",
        target_type="USER",
        target_id=str(user.id),
        reason=req.reason,
    )
    session.add(action)
    await session.commit()
    return {"status": "UNLOCKED", "email": user.email}


@router.get("/transactions", response_model=PaginatedTransactionsResponse, summary="Filter all system transactions")
async def list_admin_transactions_endpoint(
    status_filter: Optional[str] = Query(None, alias="status"),
    type_filter: Optional[str] = Query(None, alias="type"),
    user_id: Optional[uuid.UUID] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    query = select(Transaction)
    if status_filter:
        query = query.where(Transaction.status == status_filter)
    if type_filter:
        query = query.where(Transaction.type == type_filter)
    if user_id:
        acc_stmt = select(Account.id).where(Account.user_id == user_id)
        acc_res = await session.execute(acc_stmt)
        acc_ids = acc_res.scalars().all()
        query = query.where(
            or_(Transaction.from_account_id.in_(acc_ids), Transaction.to_account_id.in_(acc_ids))
        )

    count_res = await session.execute(select(func.count()).select_from(query.subquery()))
    total = count_res.scalar() or 0

    items_stmt = query.order_by(Transaction.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    items_res = await session.execute(items_stmt)
    txns = items_res.scalars().all()

    return PaginatedTransactionsResponse(
        items=[TransactionResponse.model_validate(t) for t in txns],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/transactions/{txn_id}", response_model=TransactionDetailResponse, summary="Get full transaction audit detail")
async def get_admin_transaction_detail(
    txn_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    txn = await session.get(Transaction, txn_id)
    if not txn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Transaction not found", "code": "TXN_NOT_FOUND"},
        )

    ledger_stmt = select(LedgerEntry).where(LedgerEntry.txn_id == txn_id).order_by(LedgerEntry.created_at.asc())
    ledger_res = await session.execute(ledger_stmt)
    entries = ledger_res.scalars().all()

    saga_stmt = select(SagaState).where(SagaState.txn_id == txn_id).order_by(SagaState.updated_at.asc())
    saga_res = await session.execute(saga_stmt)
    sagas = saga_res.scalars().all()

    return TransactionDetailResponse(
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
        ledger_entries=[LedgerEntryResponse.model_validate(e) for e in entries],
        saga_states=[SagaStateResponse.model_validate(s) for s in sagas],
    )


@router.get("/review-queue", response_model=List[TransactionResponse], summary="List transactions pending manual review")
async def list_review_queue(
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Transaction)
        .where(Transaction.status == "UNDER_REVIEW")
        .order_by(Transaction.created_at.asc())
    )
    res = await session.execute(stmt)
    return [TransactionResponse.model_validate(t) for t in res.scalars().all()]


@router.post("/transactions/{txn_id}/approve", response_model=TransactionResponse, summary="Approve transaction under review")
async def approve_txn_endpoint(
    txn_id: uuid.UUID,
    req: AdminActionRequest,
    current_admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    txn = await approve_review_transaction(session, current_admin.id, txn_id, req.reason)
    return TransactionResponse.model_validate(txn)


@router.post("/transactions/{txn_id}/reject", response_model=TransactionResponse, summary="Reject transaction under review")
async def reject_txn_endpoint(
    txn_id: uuid.UUID,
    req: AdminActionRequest,
    current_admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    txn = await reject_review_transaction(session, current_admin.id, txn_id, req.reason)
    return TransactionResponse.model_validate(txn)


@router.post("/transactions/{txn_id}/reverse", response_model=TransactionResponse, summary="Reverse completed P2P transaction via compensating entries")
async def reverse_txn_endpoint(
    txn_id: uuid.UUID,
    req: AdminActionRequest,
    current_admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    txn = await reverse_completed_p2p_transaction(session, current_admin.id, txn_id, req.reason)
    return TransactionResponse.model_validate(txn)


@router.get("/fraud-config", response_model=FraudConfigResponse, summary="Get active fraud detection thresholds")
async def get_fraud_config_endpoint(
    redis: aioredis.Redis = Depends(get_redis),
):
    config = await get_fraud_config(redis)
    return FraudConfigResponse(**config)


@router.put("/fraud-config", response_model=FraudConfigResponse, summary="Update fraud detection thresholds")
async def update_fraud_config_endpoint(
    req: UpdateFraudConfigRequest,
    current_admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    updates = {}
    if req.max_txn_amount is not None:
        updates["max_txn_amount"] = str(req.max_txn_amount)
    if req.daily_max_amount is not None:
        updates["daily_max_amount"] = str(req.daily_max_amount)
    if req.max_txn_per_minute is not None:
        updates["max_txn_per_minute"] = str(req.max_txn_per_minute)
    if req.new_account_days is not None:
        updates["new_account_days"] = str(req.new_account_days)
    if req.new_account_max_txn is not None:
        updates["new_account_max_txn"] = str(req.new_account_max_txn)

    if updates:
        await redis.hset("fraud_config", mapping=updates)

    action = AdminAction(
        admin_id=current_admin.id,
        action="CONFIG_CHANGE",
        target_type="FRAUD_CONFIG",
        target_id="fraud_config",
        reason=f"Updated fraud thresholds: {updates}",
    )
    session.add(action)
    await session.commit()

    config = await get_fraud_config(redis)
    return FraudConfigResponse(**config)


@router.get("/audit-log", response_model=Dict[str, Any], summary="View immutable audit log of administrative actions")
async def list_audit_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    count_res = await session.execute(select(func.count(AdminAction.id)))
    total = count_res.scalar() or 0

    stmt = select(AdminAction).order_by(AdminAction.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    res = await session.execute(stmt)
    actions = res.scalars().all()

    return {
        "items": [AdminActionResponse.model_validate(a) for a in actions],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/reconciliation/status", summary="Get last reconciliation report")
async def get_recon_status(
    redis: aioredis.Redis = Depends(get_redis),
):
    last_run = await redis.get("reconciliation_last_run")
    discrepancies_raw = await redis.get("reconciliation_discrepancies")
    discrepancies = json.loads(discrepancies_raw) if discrepancies_raw else []
    return {"last_run": last_run, "discrepancies": discrepancies}


@router.post("/reconciliation/run", summary="Trigger reconciliation job manually")
async def trigger_recon_endpoint():
    result = await reconciliation_job()
    return result


@router.post("/banks/{bank_id}/chaos", summary="Trigger bank chaos controls via admin proxy")
async def proxy_bank_chaos(
    bank_id: str,
    payload: Dict[str, Any],
):
    url = f"{settings.BANK_X_API_URL}/admin/chaos" if bank_id == "bank_x" else f"{settings.BANK_Y_API_URL}/admin/chaos"
    async with httpx.AsyncClient(timeout=5.0) as client:
        res = await client.post(url, json=payload)
        return res.json()
