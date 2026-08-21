from fastapi import APIRouter, Depends
from supabase import Client

from app.api.dependencies import UserContext, get_current_user, get_user_supabase
from app.repositories.profile_repository import ProfileRepository
from app.schemas.profiles import ProfileResponse
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/me", tags=["profile"])


@router.get("/profile", response_model=ProfileResponse)
async def get_my_profile(
    user: UserContext = Depends(get_current_user),
    client: Client = Depends(get_user_supabase),
) -> ProfileResponse:
    service = ProfileService(ProfileRepository(client))
    return await service.get_profile(user.user_id)
