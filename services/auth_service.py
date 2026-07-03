from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token, hash_password, verify_password
from app.schemas import TokenResponse, UserCreate, UserLogin
from database.repositories import create_user, get_user_by_username_or_email
from models import User


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
                "email": str(payload.email).lower(),
                "hashed_password": hash_password(payload.password),
            },
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User already exists"
        ) from exc

    return TokenResponse(access_token=create_access_token(str(user.id)), user=user)


async def authenticate_user(db: AsyncSession, payload: UserLogin) -> TokenResponse:
    user = await get_user_by_username_or_email(db, payload.username_or_email)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    return TokenResponse(access_token=create_access_token(str(user.id)), user=user)


async def get_user_profile(user: User) -> User:
    return user
