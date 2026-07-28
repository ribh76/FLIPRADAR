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
    AccountActionResponse,
    AccountDeletionRequest,
    AccountDeletionResponse,
    AccountSettingsUpdate,
    EmailChangeConfirmRequest,
    EmailChangeRequest,
    EmailVerificationRequest,
    EmailVerificationResponse,
    LogoutRequest,
    PasswordChangeRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PasswordResetResponse,
    RefreshSessionResponse,
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
    apply_user_email_change,
    blacklist_refresh_token,
    create_account_token_record,
    create_refresh_token_session,
    create_user,
    get_account_token_by_hash,
    get_latest_account_token_for_user,
    get_refresh_token_session_by_hash,
    get_refresh_token_session_for_user,
    get_user_by_email,
    get_user_by_id,
    get_user_by_username_or_email,
    is_refresh_token_blacklisted,
    list_active_refresh_token_sessions_for_user,
    mark_account_token_sent,
    mark_account_token_used,
    mark_user_email_verified,
    revoke_account_tokens_for_user,
    revoke_active_refresh_token_sessions_for_user,
    revoke_refresh_token_session,
    schedule_user_deletion,
    stage_user_email_change,
    update_user_display_name,
    update_user_password_hash,
)
from flipradar.domain.models import User
from flipradar.domain.models.refresh_token import RefreshTokenSession
from flipradar.services.email_service import (
    send_account_deletion_confirmation_email,
    send_email_change_confirmation_email,
    send_password_reset_email,
    send_registration_email,
    send_security_email,
    send_verification_email,
)

EMAIL_VERIFICATION_PURPOSE = "email_verification"
PASSWORD_RESET_PURPOSE = "password_reset"
EMAIL_CHANGE_PURPOSE = "email_change"
ACCOUNT_DELETION_DELAY = timedelta(hours=24)


def _invalid_refresh_token() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
    )


async def _token_response(db: AsyncSession, user: User) -> TokenResponse:
    refresh_token = create_refresh_token(str(user.id))
    refresh_payload = decode_refresh_token(refresh_token)
    await create_refresh_token_session(
        db,
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_token),
        token_jti=_refresh_token_jti(refresh_payload),
        expires_at=_refresh_token_expiry(refresh_payload),
        last_seen_at=datetime.now(UTC),
    )
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=refresh_token,
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


def _invalid_email_change_token() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired email change token",
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


def _email_change_url(token: str) -> str:
    frontend_url = get_settings().application.frontend_url.rstrip("/")
    return f"{frontend_url}/verify-email?token={token}&flow=email-change"


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
    extra_claims: dict | None = None,
) -> str:
    now = datetime.now(UTC)
    token = create_account_token(
        str(user.id), purpose=purpose, extra_claims=extra_claims
    )
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


async def _send_email_change_token(
    db: AsyncSession, user: User, new_email: str
) -> None:
    token = await _issue_account_token(
        db,
        user=user,
        purpose=EMAIL_CHANGE_PURPOSE,
        mark_sent=True,
        extra_claims={"new_email": new_email},
    )
    await send_email_change_confirmation_email(
        to_address=new_email,
        username=user.username,
        new_email=new_email,
        confirmation_url=_email_change_url(token),
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
                "display_name": payload.username,
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
    return await _token_response(db, user)


async def authenticate_user(db: AsyncSession, payload: UserLogin) -> TokenResponse:
    user = await get_user_by_username_or_email(db, payload.username_or_email)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    return await _token_response(db, user)


async def get_user_profile(user: User) -> User:
    return user


async def update_account_settings(
    db: AsyncSession, current_user: User, payload: AccountSettingsUpdate
) -> User:
    return await update_user_display_name(db, current_user, payload.display_name)


async def change_password(
    db: AsyncSession, current_user: User, payload: PasswordChangeRequest
) -> AccountActionResponse:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    await update_user_password_hash(
        db, current_user, hash_password(payload.new_password)
    )
    await send_security_email(
        to_address=current_user.email,
        username=current_user.username,
        event_label="Your password was changed",
    )
    return AccountActionResponse(message="Password changed successfully")


async def request_account_deletion(
    db: AsyncSession, current_user: User, payload: AccountDeletionRequest
) -> AccountDeletionResponse:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    now = datetime.now(UTC)
    scheduled_at = now + ACCOUNT_DELETION_DELAY
    await schedule_user_deletion(
        db,
        current_user,
        requested_at=now,
        scheduled_at=scheduled_at,
    )
    await send_account_deletion_confirmation_email(
        to_address=current_user.email,
        username=current_user.username,
        deletion_scheduled_at=scheduled_at.isoformat(),
    )
    return AccountDeletionResponse(
        message="Account deletion confirmed. Your user data is scheduled for removal in 24 hours.",
        deletion_scheduled_at=scheduled_at,
    )


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


async def request_email_change(
    db: AsyncSession, current_user: User, payload: EmailChangeRequest
) -> AccountActionResponse:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    new_email = normalize_email_address(payload.new_email)
    if new_email == current_user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New email must be different from current email",
        )
    if await get_user_by_email(db, new_email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already exists"
        )

    latest_token = await get_latest_account_token_for_user(
        db, current_user.id, EMAIL_CHANGE_PURPOSE
    )
    available_at = _resend_available_at(latest_token)
    now = datetime.now(UTC)
    if available_at is not None and available_at > now:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Please wait before requesting another email change",
        )

    try:
        await stage_user_email_change(db, current_user, new_email)
    except DuplicateRecordError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already exists"
        ) from exc

    await _send_email_change_token(db, current_user, new_email)
    await send_security_email(
        to_address=current_user.email,
        username=current_user.username,
        event_label=f"Email change requested for {new_email}",
    )
    return AccountActionResponse(message="Confirmation email sent to the new address")


async def confirm_email_change(
    db: AsyncSession, payload: EmailChangeConfirmRequest
) -> EmailVerificationResponse:
    try:
        token_payload = decode_account_token(
            payload.token, expected_purpose=EMAIL_CHANGE_PURPOSE
        )
    except HTTPException as exc:
        raise _invalid_email_change_token() from exc

    user_id = _account_token_subject(token_payload)
    new_email = token_payload.get("new_email")
    if not isinstance(new_email, str) or not new_email:
        raise _invalid_email_change_token()
    new_email = normalize_email_address(new_email)
    token_record = await get_account_token_by_hash(
        db, hash_account_token(payload.token), EMAIL_CHANGE_PURPOSE
    )
    now = datetime.now(UTC)
    _assert_account_token_valid(
        token_record=token_record,
        user_id=user_id,
        now=now,
        invalid_error=_invalid_email_change_token(),
    )
    if token_record is None:
        raise _invalid_email_change_token()

    user = token_record.user
    if user is None:
        user = await get_user_by_id(db, user_id)
    if user is None or user.pending_email != new_email:
        raise _invalid_email_change_token()
    if await get_user_by_email(db, new_email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already exists"
        )

    try:
        await apply_user_email_change(db, user, new_email, now)
    except DuplicateRecordError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already exists"
        ) from exc
    await mark_account_token_used(db, token_record, now)
    await revoke_account_tokens_for_user(
        db,
        user_id=user.id,
        purpose=EMAIL_CHANGE_PURPOSE,
        revoked_at=now,
        reason="email_change_complete",
    )
    return EmailVerificationResponse(
        verified=True, message="Email address changed successfully"
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
    if token_record is None:
        raise _invalid_password_reset_token()

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


async def _blacklist_session_token(
    db: AsyncSession, *, session: RefreshTokenSession, reason: str
) -> None:
    try:
        await blacklist_refresh_token(
            db,
            user_id=session.user_id,
            token_hash=session.token_hash,
            token_jti=session.token_jti,
            expires_at=session.expires_at,
            reason=reason,
        )
    except DuplicateRecordError:
        return


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

    now = datetime.now(UTC)
    session = await get_refresh_token_session_by_hash(db, token_hash)
    if session is not None:
        if (
            session.user_id != user.id
            or session.revoked_at is not None
            or _aware_utc(session.expires_at) <= now
        ):
            raise _invalid_refresh_token()
        await revoke_refresh_token_session(db, session, revoked_at=now, reason=reason)

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
    return await _token_response(db, user)


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


async def list_active_sessions(
    db: AsyncSession, current_user: User
) -> list[RefreshSessionResponse]:
    sessions = await list_active_refresh_token_sessions_for_user(
        db, current_user.id, datetime.now(UTC)
    )
    return [RefreshSessionResponse.model_validate(session) for session in sessions]


async def revoke_session(
    db: AsyncSession, current_user: User, session_id: UUID
) -> AccountActionResponse:
    session = await get_refresh_token_session_for_user(db, current_user.id, session_id)
    now = datetime.now(UTC)
    if (
        session is None
        or session.revoked_at is not None
        or _aware_utc(session.expires_at) <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    await revoke_refresh_token_session(
        db, session, revoked_at=now, reason="user_revoked_session"
    )
    await _blacklist_session_token(db, session=session, reason="user_revoked_session")
    return AccountActionResponse(message="Session revoked")


async def revoke_all_sessions(
    db: AsyncSession, current_user: User
) -> AccountActionResponse:
    now = datetime.now(UTC)
    sessions = await revoke_active_refresh_token_sessions_for_user(
        db,
        user_id=current_user.id,
        revoked_at=now,
        reason="user_revoked_all_sessions",
    )
    for session in sessions:
        await _blacklist_session_token(
            db, session=session, reason="user_revoked_all_sessions"
        )
    return AccountActionResponse(message="All sessions revoked")
