import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.database import get_db
from app.auth.models import BankUser
from app.auth.service import get_current_bank_user
from app.accounts.models import BankNotification
from app.accounts.schemas import BankNotificationResponse

logger = structlog.get_logger()
router = APIRouter()


@router.get("", response_model=List[BankNotificationResponse], summary="Get notifications for current bank user")
async def list_notifications_endpoint(
    current_user: BankUser = Depends(get_current_bank_user),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(BankNotification)
        .where(BankNotification.user_id == current_user.id)
        .order_by(BankNotification.created_at.desc())
    )
    res = await session.execute(stmt)
    notifications = res.scalars().all()
    return notifications


@router.get("/unread-count", summary="Get unread notification count")
async def get_unread_count_endpoint(
    current_user: BankUser = Depends(get_current_bank_user),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(func.count(BankNotification.id))
        .where(
            BankNotification.user_id == current_user.id,
            BankNotification.is_read.is_(False),
        )
    )
    res = await session.execute(stmt)
    count = res.scalar() or 0
    return {"unread_count": count}


@router.patch("/{notification_id}/read", summary="Mark notification as read")
async def mark_notification_read_endpoint(
    notification_id: uuid.UUID,
    current_user: BankUser = Depends(get_current_bank_user),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(BankNotification).where(
        BankNotification.id == notification_id,
        BankNotification.user_id == current_user.id,
    )
    res = await session.execute(stmt)
    notif = res.scalar_one_or_none()
    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Notification not found", "code": "NOT_FOUND"},
        )
    notif.is_read = True
    await session.commit()
    return {"status": "success", "id": str(notification_id)}

