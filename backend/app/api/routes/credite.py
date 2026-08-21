"""Rutele de creditare, sub /api/v1.

Tiparul e cel din alerte.py: `get_current_user` pentru identitate, `response_model`
pentru contract, iar erorile ies prin handler-ul global din main.py, fiindca
serviciul ridica subclase de AppError.

Nicio ruta nu primeste `user_id` din corp sau din query: vine mereu din sesiune.
Un `id_cont` sau `id_cerere` din corp e verificat ca fiind al utilizatorului —
o data in serviciu, si inca o data in RPC-ul din baza.
"""

from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from app.api.dependencies import UserContext, get_credit_service, get_current_user
from app.core.errors import ValidationError
from app.schemas.credit import (
    AcceptaRequest,
    AcordareResponse,
    CerereRequest,
    CerereResponse,
    CreditResponse,
    DecizieResponse,
    DetaliuCreditResponse,
    ProdusResponse,
    RambursareCalculResponse,
    RambursareRequest,
    RambursareResponse,
    SimulareRequest,
    SimulareResponse,
)
from app.services.credit_service import CreditService

router = APIRouter(prefix="/credite", tags=["credite"])


@router.get("/produs", response_model=ProdusResponse)
async def produs(
    _user: UserContext = Depends(get_current_user),
    serviciu: CreditService = Depends(get_credit_service),
) -> ProdusResponse:
    """Limitele produsului, ca interfata sa nu le tina hardcodate."""
    return ProdusResponse(**await serviciu.produs_public())


@router.post("/simulare", response_model=SimulareResponse)
async def simulare(
    cerere: SimulareRequest,
    _user: UserContext = Depends(get_current_user),
    serviciu: CreditService = Depends(get_credit_service),
) -> SimulareResponse:
    """Rata, DAE si graficul, fara sa se creeze nimic.

    Nu cere date despre venit si nu lasa urma: e un calculator, nu o cerere.
    """
    # asdict, nu vars: Simulare e un dataclass cu slots=True, deci nu are
    # __dict__ si vars() ar arunca TypeError — exact bug-ul care facea ruta sa
    # raspunda cu 500 „A aparut o eroare neasteptata pe server".
    rezultat = await serviciu.simuleaza(cerere.suma, cerere.luni)
    return SimulareResponse(**asdict(rezultat))


@router.post("/cereri", response_model=CerereResponse, status_code=201)
async def depune_cerere(
    cerere: CerereRequest,
    user: UserContext = Depends(get_current_user),
    serviciu: CreditService = Depends(get_credit_service),
) -> CerereResponse:
    if not cerere.consimtamant:
        raise ValidationError(
            "Ai nevoie de acordul pentru verificarea veniturilor ca sa depui cererea."
        )

    rezultat = await serviciu.depune_cerere(user.user_id, cerere.model_dump())
    return CerereResponse(**_cerere_publica(rezultat))


@router.get("/cereri", response_model=list[CerereResponse])
async def cereri(
    user: UserContext = Depends(get_current_user),
    serviciu: CreditService = Depends(get_credit_service),
) -> list[CerereResponse]:
    return [CerereResponse(**_cerere_publica(c)) for c in await serviciu.cereri(user.user_id)]


@router.get("/cereri/{id_cerere}", response_model=CerereResponse)
async def cerere(
    id_cerere: UUID,
    user: UserContext = Depends(get_current_user),
    serviciu: CreditService = Depends(get_credit_service),
) -> CerereResponse:
    return CerereResponse(**_cerere_publica(await serviciu.cerere(id_cerere, user.user_id)))


@router.post("/cereri/{id_cerere}/evalueaza", response_model=DecizieResponse)
async def evalueaza(
    id_cerere: UUID,
    user: UserContext = Depends(get_current_user),
    serviciu: CreditService = Depends(get_credit_service),
) -> DecizieResponse:
    """Ruleaza verificarile de venit, criteriile hard si scorecard-ul.

    Poate dura: interogheaza tranzactiile, registrul de expuneri si, daca e
    configurat, modelul care formuleaza motivarea.
    """
    return DecizieResponse(**asdict(await serviciu.evalueaza(id_cerere, user.user_id)))


@router.post("/cereri/{id_cerere}/accepta", response_model=AcordareResponse)
async def accepta(
    id_cerere: UUID,
    cerere: AcceptaRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
    serviciu: CreditService = Depends(get_credit_service),
) -> AcordareResponse:
    """Semnarea si acordarea: contract, grafic si banii in cont, atomic.

    Semnatura nu e una calificata, dar lasa o urma verificabila a
    consimtamantului — ip, user agent si momentul, pastrate pe contract.
    """
    semnatura = {
        "ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "moment": _acum(),
    }
    rezultat = await serviciu.accepta(id_cerere, user.user_id, UUID(cerere.id_cont), semnatura)
    return AcordareResponse(**rezultat)


@router.get("", response_model=list[CreditResponse])
async def credite(
    user: UserContext = Depends(get_current_user),
    serviciu: CreditService = Depends(get_credit_service),
) -> list[CreditResponse]:
    """Creditele utilizatorului.

    Citirea incaseaza intai ratele scadente — nu exista cron in proiect, deci
    soldul se aduce la zi cand se uita cineva la el (vezi credit_service).
    """
    return [CreditResponse(**_credit_public(c)) for c in await serviciu.credite(user.user_id)]


@router.get("/{id_credit}", response_model=DetaliuCreditResponse)
async def detaliu(
    id_credit: UUID,
    user: UserContext = Depends(get_current_user),
    serviciu: CreditService = Depends(get_credit_service),
) -> DetaliuCreditResponse:
    rezultat = await serviciu.detaliu(id_credit, user.user_id)
    return DetaliuCreditResponse(
        credit=CreditResponse(**_credit_public(rezultat["credit"])),
        rate=rezultat["rate"],
        urmatoarea_rata=rezultat["urmatoarea_rata"],
        rate_platite=rezultat["rate_platite"],
    )


@router.get("/{id_credit}/rambursare", response_model=RambursareCalculResponse)
async def calcul_rambursare(
    id_credit: UUID,
    user: UserContext = Depends(get_current_user),
    serviciu: CreditService = Depends(get_credit_service),
) -> RambursareCalculResponse:
    """Cat costa stingerea azi si cata dobanda se economiseste.

    Pas separat de executie, ca in rambursare-anticipata.md: clientul cere
    calculul, banca il comunica, si abia apoi el confirma.
    """
    return RambursareCalculResponse(**await serviciu.calcul_rambursare(id_credit, user.user_id))


@router.post("/{id_credit}/rambursare", response_model=RambursareResponse)
async def ramburseaza(
    id_credit: UUID,
    cerere: RambursareRequest,
    user: UserContext = Depends(get_current_user),
    serviciu: CreditService = Depends(get_credit_service),
) -> RambursareResponse:
    rezultat = await serviciu.ramburseaza(id_credit, user.user_id, cerere.suma)
    return RambursareResponse(**rezultat)


@router.post("/{id_credit}/avanseaza-timp", response_model=DetaliuCreditResponse)
async def avanseaza_timp(
    id_credit: UUID,
    luni: int = Query(default=1, ge=1, le=120),
    user: UserContext = Depends(get_current_user),
    serviciu: CreditService = Depends(get_credit_service),
) -> DetaliuCreditResponse:
    """Muta un "azi" simulat inainte si incaseaza scadentele pana acolo.

    Exista ca sa poata fi verificat fluxul de rambursare fara sa astepti luni
    intregi. Nu falsifica nimic: foloseste exact acelasi RPC ca procesarea
    obisnuita, doar cu alta data limita.
    """
    rezultat = await serviciu.avanseaza_timp(id_credit, user.user_id, luni)
    return DetaliuCreditResponse(
        credit=CreditResponse(**_credit_public(rezultat["credit"])),
        rate=rezultat["rate"],
        urmatoarea_rata=rezultat["urmatoarea_rata"],
        rate_platite=rezultat["rate_platite"],
    )


def _cerere_publica(cerere: dict) -> dict:
    """Doar campurile din contract — restul raman in baza (audit, nu API)."""
    campuri = (
        "id status suma_ceruta luni creat_la scor dti rata_lunara dae explicatie oferta_expira_la"
    ).split()
    return {cheie: cerere.get(cheie) for cheie in campuri}


def _credit_public(credit: dict) -> dict:
    campuri = (
        "id principal dobanda_anuala luni rata_lunara dae sold_ramas data_acordarii status inchis_la"
    ).split()
    return {cheie: credit.get(cheie) for cheie in campuri}


def _acum() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
