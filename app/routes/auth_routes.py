import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.schemas import TokenResponse, UserCreate, UserLogin, UserResponse
from database import get_db_session
from models import User
from services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = logging.getLogger(__name__)


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a V1 user",
    description="Create a username/email/password account and return a JWT access token.",
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
    description="Authenticate with username or email and return a JWT access token.",
)
async def login_user(
    payload: UserLogin, db: AsyncSession = Depends(get_db_session)
) -> TokenResponse:
    logger.info("request started route=login_user")
    token = await auth_service.authenticate_user(db, payload)
    logger.info("request finished route=login_user")
    return token


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Return the profile for the authenticated JWT bearer token.",
)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    return await auth_service.get_user_profile(current_user)
