from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.dependencies.auth import (
    create_access_token,
    create_account_token,
    create_refresh_token,
    decode_account_token,
    decode_refresh_token,
    hash_account_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from flipradar.api.schemas import (
    EmailVerificationRequest,
    EmailVerificationResponse,
    LogoutRequest,
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
from flipradar.api.schemas.auth_schema import normalize_email_address
from flipradar.core.settings import get_settings
from flipradar.database.repositories import (
    DuplicateRecordError,
    blacklist_refresh_token,
    create_account_token_record,
    create_user,
    get_account_token_by_hash,
    get_latest_account_token_for_user,
    get_user_by_id,
    get_user_by_username_or_email,
    is_refresh_token_blacklisted,
    mark_account_token_sent,
    mark_account_token_used,
    mark_user_email_verified,
    revoke_account_tokens_for_user,
    update_user_password_hash,
)
from flipradar.domain.models import User
from flipradar.services.email_service import (
    send_password_reset_email,
    send_registration_email,
    send_security_email,
    send_verification_email,
)

EMAIL_VERIFICATION_PURPOSE = "email_verification"
PASSWORD_RESET_PURPOSE = "password_reset"


def _invalid_refresh_token() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
    )


def _token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        user=UserResponse.model_validate(user),
    )


def _invalid_email_verification_token() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired verification token",
    )


def _invalid_password_reset_token() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired reset token",
    )


def _account_token_expiry(payload: dict) -> datetime:
    expires_at = payload.get("exp")
    if not isinstance(expires_at, int):
        raise _invalid_email_verification_token()
    return datetime.fromtimestamp(expires_at, UTC)


def _account_token_subject(payload: dict) -> UUID:
    subject = payload.get("sub")
    if subject is None:
        raise _invalid_email_verification_token()
    try:
        return UUID(str(subject))
    except ValueError as exc:
        raise _invalid_email_verification_token() from exc


def _account_token_jti(payload: dict) -> str:
    token_jti = payload.get("jti")
    if not isinstance(token_jti, str) or not token_jti:
        raise _invalid_email_verification_token()
    return token_jti


def _verification_url(token: str) -> str:
    frontend_url = get_settings().application.frontend_url.rstrip("/")
    return f"{frontend_url}/verify-email?token={token}"


def _password_reset_url(token: str) -> str:
    frontend_url = get_settings().application.frontend_url.rstrip("/")
    return f"{frontend_url}/reset-password?token={token}"


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _resend_available_at(user_token) -> datetime | None:
    if user_token is None or user_token.last_sent_at is None:
        return None
    cooldown = get_settings().auth.account_token_resend_cooldown_seconds
    return _aware_utc(user_token.last_sent_at) + timedelta(seconds=cooldown)


async def _issue_account_token(
    db: AsyncSession,
    *,
    user: User,
    purpose: str,
    mark_sent: bool = False,
) -> str:
    now = datetime.now(UTC)
    token = create_account_token(str(user.id), purpose=purpose)
    try:
        payload = decode_account_token(token, expected_purpose=purpose)
    except HTTPException as exc:
        raise _invalid_email_verification_token() from exc

    await revoke_account_tokens_for_user(
        db,
        user_id=user.id,
        purpose=purpose,
        revoked_at=now,
        reason="reissued",
    )
    record = await create_account_token_record(
        db,
        user_id=user.id,
        purpose=purpose,
        token_hash=hash_account_token(token),
        token_jti=_account_token_jti(payload),
        expires_at=_account_token_expiry(payload),
        last_sent_at=now if mark_sent else None,
        sent_count=1 if mark_sent else 0,
    )
    if mark_sent and record.last_sent_at is None:
        await mark_account_token_sent(db, record, now)
    return token


async def _send_email_verification_token(db: AsyncSession, user: User) -> None:
    token = await _issue_account_token(
        db, user=user, purpose=EMAIL_VERIFICATION_PURPOSE, mark_sent=True
    )
    await send_verification_email(
        to_address=user.email,
        username=user.username,
        verification_url=_verification_url(token),
    )


async def _send_password_reset_token(db: AsyncSession, user: User) -> None:
    token = await _issue_account_token(
        db, user=user, purpose=PASSWORD_RESET_PURPOSE, mark_sent=True
    )
    await send_password_reset_email(
        to_address=user.email,
        username=user.username,
        reset_url=_password_reset_url(token),
    )


async def register_user(db: AsyncSession, payload: UserCreate) -> TokenResponse:
    existing = await get_user_by_username_or_email(db, payload.username)
    if existing is None:
        existing = await get_user_by_username_or_email(db, payload.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User already exists"
        )

    try:
        user = await create_user(
            db,
            {
                "username": payload.username,
                "email": normalize_email_address(payload.email),
                "hashed_password": hash_password(payload.password),
            },
        )
    except DuplicateRecordError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User already exists"
        ) from exc

    await _send_email_verification_token(db, user)
    await send_registration_email(to_address=user.email, username=user.username)
    return _token_response(user)


async def authenticate_user(db: AsyncSession, payload: UserLogin) -> TokenResponse:
    user = await get_user_by_username_or_email(db, payload.username_or_email)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    return _token_response(user)


async def get_user_profile(user: User) -> User:
    return user


async def verify_email(
    db: AsyncSession, payload: EmailVerificationRequest
) -> EmailVerificationResponse:
    try:
        token_payload = decode_account_token(
            payload.token, expected_purpose=EMAIL_VERIFICATION_PURPOSE
        )
    except HTTPException as exc:
        raise _invalid_email_verification_token() from exc

    user_id = _account_token_subject(token_payload)
    token_hash = hash_account_token(payload.token)
    token_record = await get_account_token_by_hash(
        db, token_hash, EMAIL_VERIFICATION_PURPOSE
    )
    now = datetime.now(UTC)
    if (
        token_record is None
        or token_record.user_id != user_id
        or token_record.used_at is not None
        or token_record.revoked_at is not None
        or _aware_utc(token_record.expires_at) <= now
    ):
        raise _invalid_email_verification_token()

    user = token_record.user
    if user is None:
        user = await get_user_by_id(db, user_id)
    if user is None:
        raise _invalid_email_verification_token()

    if not user.is_email_verified:
        await mark_user_email_verified(db, user, now)
    await mark_account_token_used(db, token_record, now)
    await revoke_account_tokens_for_user(
        db,
        user_id=user.id,
        purpose=EMAIL_VERIFICATION_PURPOSE,
        revoked_at=now,
        reason="verified",
    )
    return EmailVerificationResponse(
        verified=True, message="Email address verified successfully"
    )


def _assert_account_token_valid(
    *,
    token_record,
    user_id: UUID,
    now: datetime,
    invalid_error: HTTPException,
) -> None:
    if (
        token_record is None
        or token_record.user_id != user_id
        or token_record.used_at is not None
        or token_record.revoked_at is not None
        or _aware_utc(token_record.expires_at) <= now
    ):
        raise invalid_error


async def request_password_reset(
    db: AsyncSession, payload: PasswordResetRequest
) -> PasswordResetResponse:
    user = await get_user_by_username_or_email(db, payload.email)
    if user is None:
        return PasswordResetResponse(
            message="If an account exists for that email, a reset link has been sent"
        )

    latest_token = await get_latest_account_token_for_user(
        db, user.id, PASSWORD_RESET_PURPOSE
    )
    available_at = _resend_available_at(latest_token)
    now = datetime.now(UTC)
    if available_at is not None and available_at > now:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Please wait before requesting another password reset email",
        )

    await _send_password_reset_token(db, user)
    return PasswordResetResponse(
        message="If an account exists for that email, a reset link has been sent"
    )


async def confirm_password_reset(
    db: AsyncSession, payload: PasswordResetConfirmRequest
) -> PasswordResetResponse:
    try:
        token_payload = decode_account_token(
            payload.token, expected_purpose=PASSWORD_RESET_PURPOSE
        )
    except HTTPException as exc:
        raise _invalid_password_reset_token() from exc

    user_id = _account_token_subject(token_payload)
    token_record = await get_account_token_by_hash(
        db, hash_account_token(payload.token), PASSWORD_RESET_PURPOSE
    )
    now = datetime.now(UTC)
    _assert_account_token_valid(
        token_record=token_record,
        user_id=user_id,
        now=now,
        invalid_error=_invalid_password_reset_token(),
    )

    user = token_record.user
    if user is None:
        user = await get_user_by_id(db, user_id)
    if user is None:
        raise _invalid_password_reset_token()

    await update_user_password_hash(db, user, hash_password(payload.password))
    await mark_account_token_used(db, token_record, now)
    await revoke_account_tokens_for_user(
        db,
        user_id=user.id,
        purpose=PASSWORD_RESET_PURPOSE,
        revoked_at=now,
        reason="password_reset_complete",
    )
    await send_security_email(
        to_address=user.email,
        username=user.username,
        event_label="Your password was reset",
    )
    return PasswordResetResponse(message="Password reset successfully")


async def resend_verification_email(
    db: AsyncSession, current_user: User
) -> ResendVerificationResponse:
    if current_user.is_email_verified:
        return ResendVerificationResponse(
            sent=False,
            message="Email address is already verified",
        )

    latest_token = await get_latest_account_token_for_user(
        db, current_user.id, EMAIL_VERIFICATION_PURPOSE
    )
    available_at = _resend_available_at(latest_token)
    now = datetime.now(UTC)
    if available_at is not None and available_at > now:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Please wait before requesting another verification email",
        )

    await _send_email_verification_token(db, current_user)
    return ResendVerificationResponse(
        sent=True,
        message="Verification email sent",
    )


def _refresh_token_expiry(payload: dict) -> datetime:
    expires_at = payload.get("exp")
    if not isinstance(expires_at, int):
        raise _invalid_refresh_token()
    return datetime.fromtimestamp(expires_at, UTC)


def _refresh_token_subject(payload: dict) -> UUID:
    subject = payload.get("sub")
    if subject is None:
        raise _invalid_refresh_token()
    try:
        return UUID(str(subject))
    except ValueError as exc:
        raise _invalid_refresh_token() from exc


def _refresh_token_jti(payload: dict) -> str:
    token_jti = payload.get("jti")
    if not isinstance(token_jti, str) or not token_jti:
        raise _invalid_refresh_token()
    return token_jti


async def _revoke_refresh_token(
    db: AsyncSession,
    *,
    refresh_token: str,
    payload: dict,
    reason: str,
    ignore_existing: bool = False,
) -> User:
    token_hash = hash_refresh_token(refresh_token)
    if await is_refresh_token_blacklisted(db, token_hash):
        if ignore_existing:
            user = await get_user_by_id(db, _refresh_token_subject(payload))
            if user is None:
                raise _invalid_refresh_token()
            return user
        raise _invalid_refresh_token()

    user_id = _refresh_token_subject(payload)
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise _invalid_refresh_token()

    try:
        await blacklist_refresh_token(
            db,
            user_id=user.id,
            token_hash=token_hash,
            token_jti=_refresh_token_jti(payload),
            expires_at=_refresh_token_expiry(payload),
            reason=reason,
        )
    except DuplicateRecordError as exc:
        if ignore_existing:
            return user
        raise _invalid_refresh_token() from exc
    return user


async def refresh_auth_tokens(
    db: AsyncSession, payload: RefreshTokenRequest
) -> TokenResponse:
    refresh_payload = decode_refresh_token(payload.refresh_token)
    user = await _revoke_refresh_token(
        db,
        refresh_token=payload.refresh_token,
        payload=refresh_payload,
        reason="rotation",
    )
    return _token_response(user)


async def logout_user(
    db: AsyncSession, payload: LogoutRequest, current_user: User
) -> None:
    if payload.refresh_token is None:
        return

    refresh_payload = decode_refresh_token(payload.refresh_token)
    if _refresh_token_subject(refresh_payload) != current_user.id:
        raise _invalid_refresh_token()

    await _revoke_refresh_token(
        db,
        refresh_token=payload.refresh_token,
        payload=refresh_payload,
        reason="logout",
        ignore_existing=True,
    )
