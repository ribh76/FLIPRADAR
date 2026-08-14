import logging

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.dependencies.auth import AuthenticatedUser
from flipradar.api.dependencies.database import get_db_session
from flipradar.api.schemas import (
    EmailChangeConfirmRequest,
    EmailVerificationRequest,
    EmailVerificationResponse,
    LogoutRequest,
    MfaChallengeResponse,
    MfaResetConfirmRequest,
    MfaResetRequest,
    MfaVerifyRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PasswordResetResponse,
    RefreshTokenRequest,
    ResendVerificationResponse,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from flipradar.domain.models import User
from flipradar.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = logging.getLogger(__name__)


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a V1 user",
    description="Create a username/email/password account and return an access/refresh token pair.",
)
async def register_user(
    payload: UserCreate, db: AsyncSession = Depends(get_db_session)
) -> TokenResponse:
    logger.info("request started route=register_user username=%s", payload.username)
    token = await auth_service.register_user(db, payload)
    logger.info("request finished route=register_user username=%s", payload.username)
    return token


@router.post(
    "/login",
    response_model=TokenResponse | MfaChallengeResponse,
    summary="Log in",
    description="Authenticate with username or email and return an access/refresh token pair.",
)
async def login_user(
    payload: UserLogin, db: AsyncSession = Depends(get_db_session)
) -> TokenResponse | MfaChallengeResponse:
    logger.info("request started route=login_user")
    token = await auth_service.authenticate_user(db, payload)
    logger.info("request finished route=login_user")
    return token


@router.post(
    "/mfa/verify",
    response_model=TokenResponse,
    summary="Verify MFA sign-in code",
    description="Exchange a valid one-time email code and MFA challenge for an auth session.",
)
async def verify_mfa_login(
    payload: MfaVerifyRequest, db: AsyncSession = Depends(get_db_session)
) -> TokenResponse:
    logger.info("request started route=verify_mfa_login")
    token = await auth_service.verify_mfa_challenge(db, payload)
    logger.info("request finished route=verify_mfa_login")
    return token


@router.post("/mfa/reset/request", response_model=PasswordResetResponse)
async def request_mfa_reset(
    payload: MfaResetRequest, db: AsyncSession = Depends(get_db_session)
) -> PasswordResetResponse:
    return await auth_service.request_mfa_reset(db, payload)


@router.post("/mfa/reset/confirm", response_model=PasswordResetResponse)
async def confirm_mfa_reset(
    payload: MfaResetConfirmRequest, db: AsyncSession = Depends(get_db_session)
) -> PasswordResetResponse:
    return await auth_service.confirm_mfa_reset(db, payload)


@router.post(
    "/verify-email",
    response_model=EmailVerificationResponse,
    summary="Verify email address",
    description="Verify one account email address with a short-lived verification token.",
)
async def verify_email(
    payload: EmailVerificationRequest, db: AsyncSession = Depends(get_db_session)
) -> EmailVerificationResponse:
    logger.info("request started route=verify_email")
    response = await auth_service.verify_email(db, payload)
    logger.info("request finished route=verify_email")
    return response


@router.post(
    "/email-change/confirm",
    response_model=EmailVerificationResponse,
    summary="Confirm email change",
    description="Verify the new account email address before applying it.",
)
async def confirm_email_change(
    payload: EmailChangeConfirmRequest, db: AsyncSession = Depends(get_db_session)
) -> EmailVerificationResponse:
    logger.info("request started route=confirm_email_change")
    response = await auth_service.confirm_email_change(db, payload)
    logger.info("request finished route=confirm_email_change")
    return response


@router.post(
    "/resend-verification",
    response_model=ResendVerificationResponse,
    summary="Resend verification email",
    description="Send another verification email for the authenticated user, with throttling.",
)
async def resend_verification(
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> ResendVerificationResponse:
    logger.info("request started route=resend_verification user_id=%s", current_user.id)
    response = await auth_service.resend_verification_email(db, current_user)
    logger.info(
        "request finished route=resend_verification user_id=%s", current_user.id
    )
    return response


@router.post(
    "/password-reset/request",
    response_model=PasswordResetResponse,
    summary="Request password reset",
    description="Send a throttled password reset email when an account exists.",
)
async def request_password_reset(
    payload: PasswordResetRequest, db: AsyncSession = Depends(get_db_session)
) -> PasswordResetResponse:
    logger.info("request started route=request_password_reset")
    response = await auth_service.request_password_reset(db, payload)
    logger.info("request finished route=request_password_reset")
    return response


@router.post(
    "/password-reset/confirm",
    response_model=PasswordResetResponse,
    summary="Confirm password reset",
    description="Reset a password with a short-lived password reset token.",
)
async def confirm_password_reset(
    payload: PasswordResetConfirmRequest, db: AsyncSession = Depends(get_db_session)
) -> PasswordResetResponse:
    logger.info("request started route=confirm_password_reset")
    response = await auth_service.confirm_password_reset(db, payload)
    logger.info("request finished route=confirm_password_reset")
    return response


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh an auth session",
    description="Rotate a valid refresh token and return a new access/refresh token pair.",
)
async def refresh_tokens(
    payload: RefreshTokenRequest, db: AsyncSession = Depends(get_db_session)
) -> TokenResponse:
    logger.info("request started route=refresh_tokens")
    token = await auth_service.refresh_auth_tokens(db, payload)
    logger.info("request finished route=refresh_tokens")
    return token


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log out",
    description="Revoke a refresh token so it can no longer be rotated.",
)
async def logout_user(
    payload: LogoutRequest,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    logger.info("request started route=logout_user")
    await auth_service.logout_user(db, payload, current_user)
    logger.info("request finished route=logout_user")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Return the profile for the authenticated JWT bearer token.",
)
async def get_me(current_user: AuthenticatedUser) -> User:
    return await auth_service.get_user_profile(current_user)
