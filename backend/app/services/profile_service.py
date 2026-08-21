from uuid import UUID

from fastapi import HTTPException, status

from app.repositories.profile_repository import ProfileRepository
from app.schemas.profiles import ProfileResponse


class ProfileService:
    def __init__(self, repository: ProfileRepository) -> None:
        self._repository = repository

    async def get_profile(self, user_id: UUID) -> ProfileResponse:
        profile = await self._repository.get_owned_profile(user_id)
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profilul utilizatorului nu a fost gasit.",
            )
        return ProfileResponse.model_validate(profile)
