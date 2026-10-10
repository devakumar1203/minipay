import pytest
import uuid
from httpx import AsyncClient
from app.auth.service import hash_password, verify_password, create_access_token


@pytest.mark.asyncio
async def test_password_hashing():
    pw = "SecretPass123!"
    hashed = hash_password(pw)
    assert hashed != pw
    assert verify_password(pw, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


@pytest.mark.asyncio
async def test_jwt_creation_and_claims():
    user_id = uuid.uuid4()
    token = create_access_token(user_id, "USER")
    assert isinstance(token, str)
    assert len(token) > 20

