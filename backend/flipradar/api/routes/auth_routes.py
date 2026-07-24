import logging

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from flipradar.api.dependencies.auth import get_current_user
from flipradar.api.dependencies.database import get_db_session
from flipradar.api.schemas import (
    RefreshTokenRequest,
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
    response_model=TokenResponse,
    summary="Log in",
    description="Authenticate with username or email and return an access/refresh token pair.",
)
async def login_user(
    payload: UserLogin, db: AsyncSession = Depends(get_db_session)
) -> TokenResponse:
    logger.info("request started route=login_user")
    token = await auth_service.authenticate_user(db, payload)
    logger.info("request finished route=login_user")
    return token


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
    payload: RefreshTokenRequest, db: AsyncSession = Depends(get_db_session)
) -> Response:
    logger.info("request started route=logout_user")
    await auth_service.logout_user(db, payload)
    logger.info("request finished route=logout_user")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Return the profile for the authenticated JWT bearer token.",
)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    return await auth_service.get_user_profile(current_user)
