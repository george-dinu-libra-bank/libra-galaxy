from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status

from app.core.errors import ResourceNotFoundError, ValidationError
from app.repositories.profile_repository import ProfileRepository
from app.schemas.profiles import (
    CerereStergereResponse,
    ProfileResponse,
    StareStergereResponse,
)


def _suma(valoare) -> Decimal:
    try:
        return Decimal(str(valoare or 0))
    except Exception:
        return Decimal(0)


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

    # -- cererea de stergere a contului -------------------------------------

    async def _motive_blocare(self, user_id: UUID) -> list[str]:
        """De ce nu poate pleca clientul acum.

        Fraze, nu coduri, si la plural cand e cazul: ecranul le arata ca atare.
        Un "nu se poate" gol l-ar lasa pe om sa ghiceasca ce anume il tine —
        exact genul de raspuns pentru care oamenii suna la call center.
        """
        motive: list[str] = []

        credite = await self._repository.numara_credite_in_derulare(user_id)
        if credite == 1:
            motive.append("Ai un credit in derulare. Contul se poate inchide dupa ce il achiti.")
        elif credite > 1:
            motive.append(
                f"Ai {credite} credite in derulare. Contul se poate inchide dupa ce le achiti."
            )

        conturi = await self._repository.conturi_cu_sold(user_id)
        for cont in conturi:
            sold = _suma(cont.get("sold"))
            nume = cont.get("nume") or "Cont"
            valuta = cont.get("valuta") or "RON"
            # Si soldul negativ conteaza: inseamna ca datoreaza, nu ca poate
            # pleca. De-aia se verifica != 0 in interogare, nu > 0.
            if sold > 0:
                motive.append(
                    f"Contul {nume} are {sold} {valuta}. "
                    "Transfera banii in alta parte inainte de inchidere."
                )
            else:
                motive.append(
                    f"Contul {nume} are sold negativ ({sold} {valuta}). "
                    "Acopera-l inainte de inchidere."
                )
        return motive

    async def stare_stergere(self, user_id: UUID) -> StareStergereResponse:
        cerere = await self._repository.cerere_stergere_deschisa(user_id)
        motive = await self._motive_blocare(user_id)

        return StareStergereResponse(
            cerere=CerereStergereResponse.model_validate(cerere) if cerere else None,
            # Doar o cerere deschisa opreste alta. Soldurile sunt informative:
            # se arata ca „ce ai de facut", nu ca bariera.
            poate_cere=cerere is None,
            motive_blocare=motive,
        )

    async def cere_stergere(self, user_id: UUID, motiv: str | None) -> CerereStergereResponse:
        deschisa = await self._repository.cerere_stergere_deschisa(user_id)
        if deschisa is not None:
            raise ValidationError("Ai deja o cerere de inchidere in asteptare.")

        # Motivele NU mai opresc depunerea. Poarta adevarata sta la stergere
        # (public.sterge_client): acolo se verifica soldurile, si acolo conteaza.
        # Clientul are voie sa ceara oricand — daca mai are bani, i se spune ce
        # are de facut, nu i se refuza cererea. Cine vrea sa plece nu trebuie
        # sa treaca un examen ca sa poata cere.
        cerere = await self._repository.creeaza_cerere_stergere(user_id, motiv)
        return CerereStergereResponse.model_validate(cerere)

    async def retrage_stergere(self, user_id: UUID, id_cerere: str) -> CerereStergereResponse:
        cerere = await self._repository.retrage_cerere_stergere(user_id, id_cerere)
        if cerere is None:
            raise ResourceNotFoundError(
                "Nu exista o cerere de inchidere in asteptare cu acest id."
            )
        return CerereStergereResponse.model_validate(cerere)
