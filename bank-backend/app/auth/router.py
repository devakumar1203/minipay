from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.models import BankUser
from app.auth.schemas import (
    BankRegisterRequest,
    BankLoginRequest,
    BankTokenResponse,
    BankUserResponse,
)
from app.auth.service import (
    register_bank_user,
    login_bank_user,
    get_current_bank_user,
)

router = APIRouter()


@router.post(
    "/register",
    response_model=BankUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new bank user",
)
async def register_endpoint(
    req: BankRegisterRequest,
    session: AsyncSession = Depends(get_db),
):
    user = await register_bank_user(
        session=session,
        email=req.email,
        password=req.password,
        full_name=req.full_name,
        gender=req.gender,
        date_of_birth=req.date_of_birth,
        aadhaar_no=req.aadhaar_no,
        pan_no=req.pan_no,
    )
    return user


@router.post(
    "/login",
    response_model=BankTokenResponse,
    summary="Bank user login",
)
async def login_endpoint(
    req: BankLoginRequest,
    session: AsyncSession = Depends(get_db),
):
    token = await login_bank_user(session, req.email, req.password)
    return BankTokenResponse(access_token=token)


@router.get(
    "/me",
    response_model=BankUserResponse,
    summary="Get current bank user profile",
)
async def me_endpoint(
    current_user: BankUser = Depends(get_current_bank_user),
):
    return current_user

