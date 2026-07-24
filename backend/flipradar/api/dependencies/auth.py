import hashlib
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.core.settings import get_settings
from flipradar.database import get_db_session
from flipradar.database.repositories import get_user_by_id
from flipradar.domain.models import User

pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated=["bcrypt"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _not_authenticated() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def hash_jwt_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_refresh_token(token: str) -> str:
    return hash_jwt_token(token)


def hash_account_token(token: str) -> str:
    return hash_jwt_token(token)


def _create_token(
    subject: str,
    *,
    token_type: str,
    expires_at: datetime,
    extra_claims: dict | None = None,
) -> str:
    settings = get_settings().auth
    payload = {
        "sub": subject,
        "typ": token_type,
        "jti": str(uuid4()),
        "iat": datetime.now(UTC),
        "exp": expires_at,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def create_access_token(subject: str) -> str:
    settings = get_settings().auth
    expires_at = datetime.now(UTC) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return _create_token(subject, token_type="access", expires_at=expires_at)


def create_refresh_token(subject: str) -> str:
    settings = get_settings().auth
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    return _create_token(subject, token_type="refresh", expires_at=expires_at)


def create_account_token(subject: str, *, purpose: str) -> str:
    settings = get_settings().auth
    expire_minutes = settings.email_verification_token_expire_minutes
    if purpose == "password_reset":
        expire_minutes = settings.password_reset_token_expire_minutes
    expires_at = datetime.now(UTC) + timedelta(minutes=expire_minutes)
    return _create_token(
        subject,
        token_type="account",
        expires_at=expires_at,
        extra_claims={"purpose": purpose},
    )


def decode_token(token: str, *, expected_type: str) -> dict:
    settings = get_settings().auth
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        if payload.get("typ") != expected_type:
            raise InvalidTokenError("Unexpected token type")
        return payload
    except InvalidTokenError as exc:
        raise _not_authenticated() from exc


def decode_access_token(token: str) -> dict:
    return decode_token(token, expected_type="access")


def decode_refresh_token(token: str) -> dict:
    return decode_token(token, expected_type="refresh")


def decode_account_token(token: str, *, expected_purpose: str) -> dict:
    payload = decode_token(token, expected_type="account")
    if payload.get("purpose") != expected_purpose:
        raise _not_authenticated()
    return payload


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    payload = decode_access_token(token)
    subject = payload.get("sub")
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = UUID(str(subject))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


AuthenticatedUser = Annotated[User, Depends(get_current_user)]
