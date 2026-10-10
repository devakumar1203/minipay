import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, BigInteger, DateTime, ForeignKey, CheckConstraint, Uuid, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("bank_users.id"), nullable=False, index=True
    )
    balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_bank_balance_non_negative"),
    )


class BankTxn(Base):
    __tablename__ = "bank_txns"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reference_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    account_no: Mapped[str] = mapped_column(
        String(30), ForeignKey("bank_accounts.account_no"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(10), nullable=False)  # DEBIT | CREDIT
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # APPROVED | FAILED | PENDING
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_bank_txn_amount_positive"),
        CheckConstraint("type IN ('DEBIT', 'CREDIT')", name="ck_bank_txn_type"),
        CheckConstraint("status IN ('APPROVED', 'FAILED', 'PENDING')", name="ck_bank_txn_status"),
    )


class LinkConsent(Base):
    __tablename__ = "link_consents"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    consent_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("bank_users.id"), nullable=False, index=True
    )
    account_no: Mapped[str] = mapped_column(
        String(30), ForeignKey("bank_accounts.account_no"), nullable=False, index=True
    )
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    per_txn_limit: Mapped[int] = mapped_column(BigInteger, default=5000000, nullable=False)  # 50,000 INR
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)  # ACTIVE | REVOKED
    authorization_code: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'REVOKED')", name="ck_consent_status"),
    )


class LinkRequest(Base):
    __tablename__ = "link_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    request_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    account_no: Mapped[str] = mapped_column(
        String(30), ForeignKey("bank_accounts.account_no"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("bank_users.id"), nullable=False, index=True
    )
    requester_name: Mapped[str] = mapped_column(String(255), nullable=False, default="MiniPay")
    purpose: Mapped[str] = mapped_column(String(500), nullable=False, default="Link bank account for payments")
    per_txn_limit: Mapped[int] = mapped_column(BigInteger, default=5000000, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)  # PENDING | APPROVED | DENIED
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('PENDING', 'APPROVED', 'DENIED')", name="ck_link_request_status"),
    )


class BankNotification(Base):
    __tablename__ = "bank_notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("bank_users.id"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # "LINK_REQUEST" | "TXN_DEBIT" | "TXN_CREDIT"
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    reference_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_actionable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)  # PENDING | APPROVED | DENIED | COMPLETED
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

