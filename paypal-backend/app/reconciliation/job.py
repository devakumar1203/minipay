import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from sqlalchemy import select, func
import structlog

from app.config import settings
from app.database import AsyncSessionLocal
from app.wallet.models import Account, LedgerEntry
from app.wallet.service import create_ledger_entries
from app.payment.models import Transaction, SagaState
from app.funding.models import FundingSource
from app.bank_client.client import BankClient
from app.redis_client import get_redis

logger = structlog.get_logger()


async def reconciliation_job() -> Dict[str, Any]:
    """Scheduled & on-demand reconciliation job."""
    logger.info("reconciliation_job_started")
    redis = await get_redis()
    resolved_txns = []
    discrepancies = []

    async with AsyncSessionLocal() as session:
        # Part 1: Resolve stale PENDING bank transactions
        stale_cutoff = datetime.now(timezone.utc) - timedelta(
            minutes=settings.RECONCILIATION_PENDING_MINUTES
        )
        stmt = (
            select(Transaction)
            .where(
                Transaction.status == "PENDING",
                Transaction.created_at < stale_cutoff,
                Transaction.type.in_(["P2P_BANK", "ADD_MONEY", "WITHDRAW"]),
            )
            .with_for_update(skip_locked=True)
        )
        res = await session.execute(stmt)
        pending_txns = res.scalars().all()

        for txn in pending_txns:
            try:
                if not txn.funding_source_id:
                    continue
                source = await session.get(FundingSource, txn.funding_source_id)
                if not source:
                    continue

                bank_client = BankClient(source.bank_id)
                status_res = await bank_client.get_status(str(txn.id))
                bank_status = status_res.get("status")

                if bank_status == "APPROVED":
                    if txn.type in ("ADD_MONEY", "P2P_BANK"):
                        # Complete wallet credit if not already done
                        to_account = await session.get(Account, txn.to_account_id)
                        from_account = await session.get(Account, txn.from_account_id)
                        if to_account and from_account:
                            ledger_entries = [
                                {"account_id": from_account.id, "direction": "DEBIT", "amount": txn.amount},
                                {"account_id": to_account.id, "direction": "CREDIT", "amount": txn.amount},
                            ]
                            await create_ledger_entries(session, txn.id, ledger_entries)
                    txn.status = "COMPLETED"
                    resolved_txns.append({"txn_id": str(txn.id), "new_status": "COMPLETED"})

                elif bank_status == "FAILED":
                    if txn.type == "WITHDRAW":
                        # Reverse withdrawal hold
                        to_account = await session.get(Account, txn.to_account_id)  # bank external
                        from_account = await session.get(Account, txn.from_account_id)  # user wallet
                        if to_account and from_account:
                            reversal = [
                                {"account_id": to_account.id, "direction": "DEBIT", "amount": txn.amount},
                                {"account_id": from_account.id, "direction": "CREDIT", "amount": txn.amount},
                            ]
                            await create_ledger_entries(session, txn.id, reversal)
                    txn.status = "FAILED"
                    resolved_txns.append({"txn_id": str(txn.id), "new_status": "FAILED"})

            except Exception as e:
                logger.error("error_reconciling_transaction", txn_id=str(txn.id), error=str(e))

        await session.commit()

        # Part 2: Audit Ledger Integrity
        # 1. Check all completed transactions have equal debits and credits
        txn_stmt = (
            select(
                LedgerEntry.txn_id,
                func.sum(
                    func.case((LedgerEntry.direction == "DEBIT", LedgerEntry.amount), else_=0)
                ).label("total_debits"),
                func.sum(
                    func.case((LedgerEntry.direction == "CREDIT", LedgerEntry.amount), else_=0)
                ).label("total_credits"),
            )
            .group_by(LedgerEntry.txn_id)
            .having(
                func.sum(
                    func.case((LedgerEntry.direction == "DEBIT", LedgerEntry.amount), else_=0)
                )
                != func.sum(
                    func.case((LedgerEntry.direction == "CREDIT", LedgerEntry.amount), else_=0)
                )
            )
        )
        unbalanced_res = await session.execute(txn_stmt)
        for row in unbalanced_res.fetchall():
            discrepancies.append({
                "type": "UNBALANCED_TRANSACTION_LEDGER",
                "txn_id": str(row.txn_id),
                "debits": row.total_debits,
                "credits": row.total_credits,
            })

        # 2. Check each account balance matches ledger sum (sum credits - sum debits)
        acc_stmt = select(Account)
        acc_res = await session.execute(acc_stmt)
        accounts = acc_res.scalars().all()

        for acc in accounts:
            if acc.type == "USER_WALLET":
                ledger_sum_stmt = select(
                    func.sum(
                        func.case((LedgerEntry.direction == "CREDIT", LedgerEntry.amount), else_=0)
                    ).label("sum_credits"),
                    func.sum(
                        func.case((LedgerEntry.direction == "DEBIT", LedgerEntry.amount), else_=0)
                    ).label("sum_debits"),
                ).where(LedgerEntry.account_id == acc.id)
                l_res = await session.execute(ledger_sum_stmt)
                sums = l_res.fetchone()
                sum_credits = (sums.sum_credits or 0) if sums else 0
                sum_debits = (sums.sum_debits or 0) if sums else 0
                expected_balance = sum_credits - sum_debits

                if acc.balance != expected_balance:
                    discrepancies.append({
                        "type": "ACCOUNT_BALANCE_MISMATCH",
                        "account_id": str(acc.id),
                        "user_id": str(acc.user_id),
                        "stored_balance": acc.balance,
                        "ledger_computed_balance": expected_balance,
                    })

    # Save to Redis
    last_run_time = datetime.now(timezone.utc).isoformat()
    await redis.set("reconciliation_last_run", last_run_time)
    await redis.set("reconciliation_discrepancies", json.dumps(discrepancies))

    logger.info("reconciliation_job_completed", resolved=len(resolved_txns), discrepancies=len(discrepancies))
    return {
        "last_run": last_run_time,
        "resolved_transactions": resolved_txns,
        "discrepancies": discrepancies,
    }
