from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.dependencies.auth import UnverifiedAuthenticatedUser
from flipradar.api.dependencies.database import get_db_session
from flipradar.api.schemas import (
    AccountActionResponse,
    AccountDeletionRequest,
    AccountDeletionResponse,
    AccountSettingsUpdate,
    EmailChangeRequest,
    MfaSettingsResponse,
    MfaSettingsUpdate,
    PasswordChangeRequest,
    RefreshSessionResponse,
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
async def get_current_user_profile(current_user: UnverifiedAuthenticatedUser) -> User:
    return current_user


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update account settings",
    description="Update editable profile settings for the authenticated user.",
)
async def update_current_user_settings(
    payload: AccountSettingsUpdate,
    current_user: UnverifiedAuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> User:
    return await auth_service.update_account_settings(db, current_user, payload)


@router.put(
    "/me/mfa",
    response_model=MfaSettingsResponse,
    summary="Update MFA settings",
    description="Enable or disable email MFA after confirming the current password.",
)
async def update_current_user_mfa_settings(
    payload: MfaSettingsUpdate,
    current_user: UnverifiedAuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> MfaSettingsResponse:
    return await auth_service.update_mfa_settings(db, current_user, payload)


@router.post(
    "/me/password",
    response_model=AccountActionResponse,
    summary="Change password",
    description="Change the authenticated user's password after confirming the current password.",
)
async def change_current_user_password(
    payload: PasswordChangeRequest,
    current_user: UnverifiedAuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> AccountActionResponse:
    return await auth_service.change_password(db, current_user, payload)


@router.post(
    "/me/deletion-request",
    response_model=AccountDeletionResponse,
    summary="Schedule account deletion",
    description="Re-authenticate and schedule account user data removal after 24 hours.",
)
async def request_current_user_account_deletion(
    payload: AccountDeletionRequest,
    current_user: UnverifiedAuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> AccountDeletionResponse:
    return await auth_service.request_account_deletion(db, current_user, payload)


@router.post(
    "/me/email-change/request",
    response_model=AccountActionResponse,
    summary="Request email change",
    description="Send a confirmation email to a pending new account email address.",
)
async def request_current_user_email_change(
    payload: EmailChangeRequest,
    current_user: UnverifiedAuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> AccountActionResponse:
    return await auth_service.request_email_change(db, current_user, payload)


@router.get(
    "/me/sessions",
    response_model=list[RefreshSessionResponse],
    summary="List active sessions",
    description="Return active refresh-token sessions for the authenticated user.",
)
async def list_current_user_sessions(
    current_user: UnverifiedAuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> list[RefreshSessionResponse]:
    return await auth_service.list_active_sessions(db, current_user)


@router.delete(
    "/me/sessions/{session_id}",
    response_model=AccountActionResponse,
    summary="Revoke session",
    description="Revoke one active refresh-token session.",
)
async def revoke_current_user_session(
    session_id: UUID,
    current_user: UnverifiedAuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> AccountActionResponse:
    return await auth_service.revoke_session(db, current_user, session_id)


@router.delete(
    "/me/sessions",
    response_model=AccountActionResponse,
    summary="Revoke all sessions",
    description="Revoke every active refresh-token session for the authenticated user.",
)
async def revoke_all_current_user_sessions(
    current_user: UnverifiedAuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> AccountActionResponse:
    return await auth_service.revoke_all_sessions(db, current_user)
