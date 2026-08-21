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

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile

from app.api.dependencies import (
    UserContext,
    cere_administrator,
    get_credit_service,
    get_current_user,
)
from app.core.errors import ValidationError
from app.schemas.credit import (
    AcceptaRequest,
    AcordareResponse,
    CerereAdminResponse,
    CerereRequest,
    CerereResponse,
    ConfirmaDocumentRequest,
    CreditAdminResponse,
    CreditResponse,
    DecizieManualaRequest,
    DecizieResponse,
    DetaliuCreditResponse,
    DocumentResponse,
    DosarResponse,
    ProdusResponse,
    RambursareCalculResponse,
    RambursareRequest,
    RambursareResponse,
    SimulareRequest,
    SimulareResponse,
    VerificareResponse,
)
from app.services.credit_service import CreditService

router = APIRouter(prefix="/credite", tags=["credite"])

# Router separat, cu alta dependinta de acces. Nu e o subruta a celui de sus
# tocmai ca sa nu poata cineva adauga din greseala un endpoint de admin fara
# `cere_administrator` — aici garda e pe router, nu pe fiecare functie.
router_admin = APIRouter(
    prefix="/admin/credite", tags=["credite-admin"], dependencies=[Depends(cere_administrator)]
)


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


@router.post("/cereri/{id_cerere}/documente", response_model=DocumentResponse)
async def incarca_document(
    id_cerere: UUID,
    fisier: UploadFile = File(...),
    user: UserContext = Depends(get_current_user),
    serviciu: CreditService = Depends(get_credit_service),
) -> DocumentResponse:
    """Incarca o adeverinta de venit si o citeste.

    Documentul e citit, nu crezut: ce extrage OCR-ul ramane in `extras` si nu
    atinge decizia pana cand un analist confirma cifra. Raspunsul arata ce s-a
    citit, ca omul sa stie daca a iesit ceva din poza lui.
    """
    document = await serviciu.incarca_document(
        id_cerere, user.user_id, await fisier.read(), fisier.content_type
    )
    return DocumentResponse(**_document_public(document))


@router.get("/cereri/{id_cerere}/documente", response_model=list[DocumentResponse])
async def documentele_cererii(
    id_cerere: UUID,
    user: UserContext = Depends(get_current_user),
    serviciu: CreditService = Depends(get_credit_service),
) -> list[DocumentResponse]:
    return [
        DocumentResponse(**_document_public(document))
        for document in await serviciu.documente(id_cerere, user.user_id)
    ]


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


# ---------------------------------------------------------------------------
# Analiza manuala — zona gri a scorecard-ului (45-69 puncte)
# ---------------------------------------------------------------------------


@router_admin.get("/analiza-manuala", response_model=list[CerereAdminResponse])
async def coada_analiza(
    serviciu: CreditService = Depends(get_credit_service),
) -> list[CerereAdminResponse]:
    """Cererile care asteapta decizia unui om, cea mai veche prima."""
    return [_cerere_admin(cerere) for cerere in await serviciu.cereri_in_analiza()]


@router_admin.post("/cereri/{id_cerere}/decizie", response_model=CerereResponse)
async def decizie_manuala(
    id_cerere: UUID,
    cerere: DecizieManualaRequest,
    administrator: UserContext = Depends(cere_administrator),
    serviciu: CreditService = Depends(get_credit_service),
) -> CerereResponse:
    """Aproba sau respinge o cerere din analiza manuala.

    Aprobarea nu acorda creditul — genereaza oferta. Clientul o accepta tot el,
    din aplicatie: semnatura ramane a lui, nu a administratorului.
    """
    rezultat = await serviciu.decide_manual(
        id_cerere, administrator.user_id, cerere.aproba, cerere.nota
    )
    return CerereResponse(**_cerere_publica(rezultat))


@router_admin.get("/cereri", response_model=list[CerereAdminResponse])
async def toate_cererile(
    status: str | None = Query(default=None),
    serviciu: CreditService = Depends(get_credit_service),
) -> list[CerereAdminResponse]:
    """Toate cererile, optional filtrate — ca sa poata fi auditate si cele automate."""
    return [_cerere_admin(cerere) for cerere in await serviciu.cereri_toate(status)]


@router_admin.get("/cereri/{id_cerere}", response_model=DosarResponse)
async def dosar(
    id_cerere: UUID,
    serviciu: CreditService = Depends(get_credit_service),
) -> DosarResponse:
    """Cererea, cele patru verificari de venit si documentele, cu link-uri semnate."""
    date = await serviciu.dosar(id_cerere)
    return DosarResponse(
        cerere=_cerere_admin(date["cerere"]),
        verificari=[VerificareResponse(**_verificare_publica(v)) for v in date["verificari"]],
        documente=[DocumentResponse(**_document_public(d)) for d in date["documente"]],
    )


@router_admin.post("/documente/{id_document}/confirma", response_model=DosarResponse)
async def confirma_document(
    id_document: UUID,
    cerere: ConfirmaDocumentRequest,
    administrator: UserContext = Depends(cere_administrator),
    serviciu: CreditService = Depends(get_credit_service),
) -> DosarResponse:
    """Valideaza cifra din adeverinta si reevalueaza cererea cu ea.

    Analistul completeaza o intrare a motorului de scoring, nu alege un
    rezultat: dupa confirmare ruleaza acelasi calcul determinist, cu venitul in
    plus. De-aia raspunsul e dosarul intreg — scorul se poate fi schimbat.
    """
    date = await serviciu.confirma_document(
        id_document, administrator.user_id, cerere.venit_confirmat
    )
    return DosarResponse(
        cerere=_cerere_admin(date["cerere"]),
        verificari=[VerificareResponse(**_verificare_publica(v)) for v in date["verificari"]],
        documente=[DocumentResponse(**_document_public(d)) for d in date["documente"]],
    )


@router_admin.get("/acordate", response_model=list[CreditAdminResponse])
async def credite_acordate(
    serviciu: CreditService = Depends(get_credit_service),
) -> list[CreditAdminResponse]:
    return [
        CreditAdminResponse(
            **_credit_public(credit),
            nume=(credit.get("profiles") or {}).get("nume", "necunoscut"),
        )
        for credit in await serviciu.credite_toate()
    ]


def _cerere_admin(cerere: dict) -> CerereAdminResponse:
    return CerereAdminResponse(
        **_cerere_publica(cerere),
        nume=(cerere.get("profiles") or {}).get("nume", "necunoscut"),
        venit_folosit=cerere.get("venit_folosit"),
        obligatii_folosite=cerere.get("obligatii_folosite"),
        motive=cerere.get("motive") or [],
    )


def _document_public(document: dict) -> dict:
    campuri = (
        "id tip status content_type marime_octeti extras venit_confirmat "
        "confirmat_la sters_la creat_la url"
    ).split()
    date = {cheie: document.get(cheie) for cheie in campuri}
    date["extras"] = date["extras"] or {}
    return date


def _verificare_publica(verificare: dict) -> dict:
    campuri = "sursa venit_constatat obligatii_constatate incredere detalii creat_la".split()
    date = {cheie: verificare.get(cheie) for cheie in campuri}
    date["detalii"] = date["detalii"] or {}
    return date


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
