from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.dependencies.auth import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from flipradar.api.schemas import (
    LogoutRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from flipradar.api.schemas.auth_schema import normalize_email_address
from flipradar.database.repositories import (
    DuplicateRecordError,
    blacklist_refresh_token,
    create_user,
    get_user_by_id,
    get_user_by_username_or_email,
    is_refresh_token_blacklisted,
)
from flipradar.domain.models import User


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
