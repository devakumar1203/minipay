from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.models import User
from app.auth.schemas import (
    RegisterRequest,
    LoginRequest,
    ProfileUpdateRequest,
    AddressUpdateRequest,
    TokenResponse,
    UserResponse,
)
from app.auth.service import register, login
from app.auth.dependencies import get_current_user

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user (Step 1)",
)
async def register_endpoint(
    req: RegisterRequest,
    session: AsyncSession = Depends(get_db),
):
    user = await register(session, req.email, req.password)
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and get JWT token",
)
async def login_endpoint(
    req: LoginRequest,
    session: AsyncSession = Depends(get_db),
):
    token, onboarding_step = await login(session, req.email, req.password)
    return TokenResponse(access_token=token, onboarding_step=onboarding_step)


@router.put(
    "/profile",
    response_model=UserResponse,
    summary="Update personal profile during onboarding (Step 2)",
)
async def update_profile_endpoint(
    req: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    current_user.full_name = req.full_name.strip()
    current_user.mobile_no = req.mobile_no.strip()
    if current_user.onboarding_step < 2:
        current_user.onboarding_step = 2
    await session.commit()
    await session.refresh(current_user)
    return current_user


@router.put(
    "/address",
    response_model=UserResponse,
    summary="Update address during onboarding (Step 3)",
)
async def update_address_endpoint(
    req: AddressUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    current_user.address_line1 = req.address_line1.strip()
    current_user.address_line2 = req.address_line2.strip() if req.address_line2 else ""
    current_user.city = req.city.strip()
    current_user.state = req.state.strip()
    current_user.pincode = req.pincode.strip()
    if current_user.onboarding_step < 3:
        current_user.onboarding_step = 3
    await session.commit()
    await session.refresh(current_user)
    return current_user


@router.post(
    "/skip-bank-link",
    response_model=UserResponse,
    summary="Skip bank linking step and complete onboarding",
)
async def skip_bank_link_endpoint(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    current_user.onboarding_step = 4
    await session.commit()
    await session.refresh(current_user)
    return current_user


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current logged-in user profile",
)
async def me_endpoint(
    current_user: User = Depends(get_current_user),
):
    return current_user
