import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, ForeignKey, CheckConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class FundingSource(Base):
    __tablename__ = "funding_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    bank_id: Mapped[str] = mapped_column(String(50), nullable=False)  # "bank_x" | "bank_y"
    token: Mapped[str] = mapped_column(String(255), nullable=False)  # Never expose to frontend
    masked_account: Mapped[str] = mapped_column(String(50), nullable=False)  # "XXXX-4521"
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)  # ACTIVE | PENDING | REVOKED | DENIED
    link_request_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'PENDING', 'REVOKED', 'DENIED')", name="ck_funding_source_status"),
    )
