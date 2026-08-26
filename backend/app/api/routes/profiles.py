from fastapi import APIRouter, Depends
from supabase import Client

from app.api.dependencies import UserContext, get_current_user, get_user_supabase
from app.repositories.profile_repository import ProfileRepository
from app.infrastructure.rate_limit import limiteaza
from app.schemas.profiles import (
    CerereStergereRequest,
    CerereStergereResponse,
    ProfileResponse,
    StareStergereResponse,
)
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/me", tags=["profile"])


@router.get("/profile", response_model=ProfileResponse)
async def get_my_profile(
    user: UserContext = Depends(get_current_user),
    client: Client = Depends(get_user_supabase),
) -> ProfileResponse:
    service = ProfileService(ProfileRepository(client))
    return await service.get_profile(user.user_id)


@router.get("/stergere", response_model=StareStergereResponse)
async def stare_stergere(
    user: UserContext = Depends(get_current_user),
    client: Client = Depends(get_user_supabase),
) -> StareStergereResponse:
    """Daca poate cere inchiderea contului, si ce il opreste daca nu.

    Ecranul are nevoie de raspuns INAINTE sa apese omul: un buton care se lasa
    apasat si abia apoi spune „nu se poate" e mai prost decat unul care spune
    de la inceput ce mai are de facut.
    """
    service = ProfileService(ProfileRepository(client))
    return await service.stare_stergere(user.user_id)


@router.post("/stergere", response_model=CerereStergereResponse, status_code=201)
async def cere_stergere(
    cerere: CerereStergereRequest,
    user: UserContext = Depends(get_current_user),
    client: Client = Depends(get_user_supabase),
) -> CerereStergereResponse:
    """Depune cererea de inchidere. Nu sterge nimic — banca decide.

    Limita de rata e mica dinadins: cererea e un act, nu o actiune repetabila.
    Cine o depune de cinci ori in cinci minute nu vrea sa plece, ci incearca
    ceva.
    """
    limiteaza(f"cerere-stergere:user:{user.user_id}", max_incercari=5, fereastra_secunde=300)

    service = ProfileService(ProfileRepository(client))
    return await service.cere_stergere(user.user_id, cerere.motiv)


@router.delete("/stergere/{id_cerere}", response_model=CerereStergereResponse)
async def retrage_stergere(
    id_cerere: str,
    user: UserContext = Depends(get_current_user),
    client: Client = Depends(get_user_supabase),
) -> CerereStergereResponse:
    """Clientul se razgandeste. Se cheama „retrasa", nu „respinsa": prima e a
    lui, a doua e a bancii, si in jurnal sunt doua lucruri diferite."""
    service = ProfileService(ProfileRepository(client))
    return await service.retrage_stergere(user.user_id, id_cerere)
