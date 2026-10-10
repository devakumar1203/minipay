import pytest
import uuid
from app.wallet.models import Account
from app.wallet.service import create_ledger_entries


@pytest.mark.asyncio
async def test_unbalanced_ledger_entries_rejected(db_session):
    txn_id = uuid.uuid4()
    acc1 = Account(user_id=uuid.uuid4(), type="USER_WALLET", balance=1000, version=1)
    acc2 = Account(user_id=uuid.uuid4(), type="USER_WALLET", balance=0, version=1)
    db_session.add_all([acc1, acc2])
    await db_session.commit()

    # Unbalanced: debit 500, credit 400
    entries = [
        {"account_id": acc1.id, "direction": "DEBIT", "amount": 500},
        {"account_id": acc2.id, "direction": "CREDIT", "amount": 400},
    ]

    with pytest.raises(ValueError, match="Unbalanced ledger entries"):
        await create_ledger_entries(db_session, txn_id, entries)


@pytest.mark.asyncio
async def test_balanced_ledger_entries_success(db_session):
    txn_id = uuid.uuid4()
    acc1 = Account(user_id=uuid.uuid4(), type="USER_WALLET", balance=1000, version=1)
    acc2 = Account(user_id=uuid.uuid4(), type="USER_WALLET", balance=0, version=1)
    db_session.add_all([acc1, acc2])
    await db_session.commit()

    entries = [
        {"account_id": acc1.id, "direction": "DEBIT", "amount": 500},
        {"account_id": acc2.id, "direction": "CREDIT", "amount": 500},
    ]

    records = await create_ledger_entries(db_session, txn_id, entries)
    await db_session.commit()

    assert len(records) == 2
    await db_session.refresh(acc1)
    await db_session.refresh(acc2)
    assert acc1.balance == 500
    assert acc2.balance == 500

