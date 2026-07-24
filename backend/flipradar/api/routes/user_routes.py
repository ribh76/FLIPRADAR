from fastapi import APIRouter

from flipradar.api.dependencies.auth import AuthenticatedUser
from flipradar.api.schemas import UserResponse
from flipradar.domain.models import User

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get authenticated user",
    description="Return the profile for the authenticated access token.",
)
async def get_current_user_profile(current_user: AuthenticatedUser) -> User:
    return current_user
