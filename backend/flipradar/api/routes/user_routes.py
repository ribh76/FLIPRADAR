from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.dependencies.auth import AuthenticatedUser
from flipradar.api.dependencies.database import get_db_session
from flipradar.api.schemas import (
    AccountActionResponse,
    AccountSettingsUpdate,
    EmailChangeRequest,
    PasswordChangeRequest,
    UserResponse,
)
from flipradar.domain.models import User
from flipradar.services import auth_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get authenticated user",
    description="Return the profile for the authenticated access token.",
)
async def get_current_user_profile(current_user: AuthenticatedUser) -> User:
    return current_user


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update account settings",
    description="Update editable profile settings for the authenticated user.",
)
async def update_current_user_settings(
    payload: AccountSettingsUpdate,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> User:
    return await auth_service.update_account_settings(db, current_user, payload)


@router.post(
    "/me/password",
    response_model=AccountActionResponse,
    summary="Change password",
    description="Change the authenticated user's password after confirming the current password.",
)
async def change_current_user_password(
    payload: PasswordChangeRequest,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> AccountActionResponse:
    return await auth_service.change_password(db, current_user, payload)


@router.post(
    "/me/email-change/request",
    response_model=AccountActionResponse,
    summary="Request email change",
    description="Send a confirmation email to a pending new account email address.",
)
async def request_current_user_email_change(
    payload: EmailChangeRequest,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> AccountActionResponse:
    return await auth_service.request_email_change(db, current_user, payload)
