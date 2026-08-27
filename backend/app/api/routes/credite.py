"""Rutele de creditare, sub /api/v1.

Tiparul e cel din alerte.py: `get_current_user` pentru identitate, `response_model`
pentru contract, iar erorile ies prin handler-ul global din main.py, fiindca
serviciul ridica subclase de AppError.

Nicio ruta nu primeste `user_id` din corp sau din query: vine mereu din sesiune.
Un `id_cont` sau `id_cerere` din corp e verificat ca fiind al utilizatorului —
o data in serviciu, si inca o data in RPC-ul din baza.
"""

import asyncio
import logging
from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, Request, UploadFile

from app.api.dependencies import (
    UserContext,
    cere_administrator,
    get_credit_ai_pipeline,
    get_credit_ai_repository,
    get_credit_service,
    get_current_user,
)
from app.core.config import get_settings
from app.core.errors import PermissionDeniedError, ValidationError
from app.infrastructure.rate_limit import limiteaza
from app.credit.ai.contracte import ALL_ETAPE_SPECS
from app.credit.ai.pipeline import CreditAiPipeline
from app.repositories.credit_ai_repository import CreditAiRepository
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
    EvenimentResponse,
    MesajRequest,
    MesajResponse,
    ProdusResponse,
    RambursareCalculResponse,
    RambursareRequest,
    RambursareResponse,
    SimulareRequest,
    SimulareResponse,
    VerificareResponse,
)
from app.schemas.credit_ai import (
    DosarAiResponse,
    EtapaAiResponse,
    EtapaSpecResponse,
    ObservabilitateAiResponse,
    RataAcordResponse,
    RezumatZilnicEtapaResponse,
    RulareAiResponse,
    SemnalResponse,
    SemnaleRezumatResponse,
)
from app.services.credit_service import CreditService

logger = logging.getLogger(__name__)

# Mediile in care uneltele de demo au voie sa existe. Lista alba, nu
# `!= "production"`: cu negatie, un mediu nou nebotezat porneste deschis.
MEDII_CU_DEMO = ("local", "test", "demo")


def _limiteaza_scump(user_id: str, actiune: str, *, maxim: int) -> None:
    """Limita pe utilizator pentru rutele care costa bani sau timp.

    `credite.py` era singurul router fara nicio limita, desi are cele mai scumpe
    rute din aplicatie: `documente` cheama Azure Document Intelligence (bani
    reali, per pagina) si `evalueaza` cheama un LLM. Cheia e utilizatorul, nu
    IP-ul: rutele sunt autentificate, deci avem ceva mai bun decat un IP.

    Pragurile sunt generoase pentru un om real — cine incarca a unsprezecea
    adeverinta in cinci minute nu depune o cerere de credit.
    """
    limiteaza(f"credite-{actiune}:user:{user_id}", max_incercari=maxim, fereastra_secunde=300)


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
    # `cereri_cu_necitite`, nu `cereri`: bulina din ecran are nevoie de contor,
    # iar numararea se face intr-o singura interogare pentru toata lista.
    return [
        CerereResponse(**_cerere_publica(c)) for c in await serviciu.cereri_cu_necitite(user.user_id)
    ]


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
    background: BackgroundTasks,
    user: UserContext = Depends(get_current_user),
    serviciu: CreditService = Depends(get_credit_service),
    pipeline: CreditAiPipeline = Depends(get_credit_ai_pipeline),
) -> DecizieResponse:
    """Ruleaza verificarile de venit, criteriile hard si scorecard-ul.

    Poate dura: interogheaza tranzactiile, registrul de expuneri si, daca e
    configurat, modelul care formuleaza motivarea (etapa 'explicatie', sincrona).

    Etapele consultative 1-3 (documente/coerenta/brief) pornesc separat, ca
    task de fundal: nu au ce cauta pe drumul critic al unei decizii care
    trebuie sa ramana reproductibila indiferent cat de repede raspunde Foundry.
    """
    _limiteaza_scump(user.user_id, "evalueaza", maxim=10)

    rezultat = await serviciu.evalueaza(id_cerere, user.user_id)
    background.add_task(pipeline.ruleaza, id_cerere, "evalueaza")
    return DecizieResponse(**asdict(rezultat))


@router.post("/cereri/{id_cerere}/documente", response_model=DocumentResponse)
async def incarca_document(
    id_cerere: UUID,
    background: BackgroundTasks,
    fisier: UploadFile = File(...),
    user: UserContext = Depends(get_current_user),
    serviciu: CreditService = Depends(get_credit_service),
    pipeline: CreditAiPipeline = Depends(get_credit_ai_pipeline),
) -> DocumentResponse:
    """Incarca o adeverinta de venit si o citeste.

    Documentul e citit, nu crezut: ce extrage OCR-ul ramane in `extras` si nu
    atinge decizia pana cand un analist confirma cifra. Raspunsul arata ce s-a
    citit, ca omul sa stie daca a iesit ceva din poza lui.

    Task de fundal: modelul citeste acelasi document (etapa 'documente') si
    coreleaza cu tranzactiile (etapa 'coerenta') — pentru analistul care va
    deschide dosarul, nu pentru raspunsul asta.
    """
    # Inaintea lui `read()`: cine a depasit limita nu mai are de ce sa-si urce
    # fisierul in memoria serverului ca sa afle asta.
    _limiteaza_scump(user.user_id, "documente", maxim=10)

    document = await serviciu.incarca_document(
        id_cerere, user.user_id, await fisier.read(), fisier.content_type
    )
    background.add_task(pipeline.ruleaza, id_cerere, "document_incarcat")
    return DocumentResponse(**_document_public(document))


@router.get("/cereri/{id_cerere}/mesaje", response_model=list[MesajResponse])
async def mesajele_cererii(
    id_cerere: UUID,
    user: UserContext = Depends(get_current_user),
    serviciu: CreditService = Depends(get_credit_service),
) -> list[MesajResponse]:
    """Firul de discutie al cererii, in ordine cronologica."""
    return [
        MesajResponse(**_mesaj_public(mesaj))
        for mesaj in await serviciu.mesaje(id_cerere, user.user_id)
    ]


@router.post("/cereri/{id_cerere}/mesaje/citite", status_code=204)
async def marcheaza_firul_citit(
    id_cerere: UUID,
    user: UserContext = Depends(get_current_user),
    serviciu: CreditService = Depends(get_credit_service),
) -> None:
    """Firul a fost deschis — mesajele bancii nu mai sunt necitite."""
    await serviciu.marcheaza_firul_citit(id_cerere, user.user_id)


@router.post("/cereri/{id_cerere}/mesaje", response_model=MesajResponse, status_code=201)
async def scrie_mesaj(
    id_cerere: UUID,
    cerere: MesajRequest,
    user: UserContext = Depends(get_current_user),
    serviciu: CreditService = Depends(get_credit_service),
) -> MesajResponse:
    """Raspunsul clientului — exista ca sa aiba unde intreba cand nu intelege
    ce act i se cere."""
    _limiteaza_scump(user.user_id, "mesaje", maxim=30)

    mesaj = await serviciu.scrie_mesaj_client(id_cerere, user.user_id, cerere.text)
    return MesajResponse(**_mesaj_public(mesaj))


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

    Tocmai fiindca nu falsifica nimic, are nevoie de o poarta: statea pe
    `router`, nu pe `router_admin`, si cerea doar o sesiune valida — orice
    utilizator autentificat isi putea muta "azi"-ul cu 120 de luni si declansa
    incasari adevarate. E o unealta de demo, si trebuie sa fie DOAR atat.
    """
    if get_settings().environment not in MEDII_CU_DEMO:
        # PermissionDeniedError (403), nu OperatiuneRefuzata: aceea e 422 cu cod
        # de stare a creditului, iar aici creditul n-are nicio vina — ruta pur si
        # simplu nu exista in mediul asta.
        raise PermissionDeniedError(
            "Avansarea timpului e disponibila doar in mediile de demonstratie."
        )
    _limiteaza_scump(user.user_id, "avanseaza-timp", maxim=20)

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
    ai_repo: CreditAiRepository = Depends(get_credit_ai_repository),
) -> list[CerereAdminResponse]:
    """Cererile care asteapta decizia unui om, cea mai veche prima."""
    cereri = await serviciu.cereri_in_analiza()
    semnale = await _semnale_grupate_sigur(ai_repo, [UUID(c["id"]) for c in cereri])
    return [_cerere_admin(cerere, semnale.get(cerere["id"])) for cerere in cereri]


@router.post("/cereri/{id_cerere}/anuleaza", response_model=CerereResponse)
async def anuleaza_cerere(
    id_cerere: UUID,
    utilizator: UserContext = Depends(get_current_user),
    serviciu: CreditService = Depends(get_credit_service),
) -> CerereResponse:
    """Clientul isi retrage cererea.

    Nu e doar o curatenie de ecran: inchiderea completeaza `finalizat_la`, deci
    porneste retentia documentelor. Fara ruta asta, un dosar abandonat isi tinea
    adeverinta in bucket la nesfarsit.
    """
    return CerereResponse(**_cerere_publica(await serviciu.anuleaza(id_cerere, utilizator.user_id)))


@router_admin.post("/cereri/{id_cerere}/decizie", response_model=CerereResponse)
async def decizie_manuala(
    id_cerere: UUID,
    cerere: DecizieManualaRequest,
    administrator: UserContext = Depends(cere_administrator),
    serviciu: CreditService = Depends(get_credit_service),
) -> CerereResponse:
    """Ce face analistul cu un dosar aflat in lucru.

    Patru actiuni printr-un singur endpoint, ca sa existe o singura garda de
    acces si o singura forma de raspuns:

    - `aproba` — nu acorda creditul, genereaza oferta. Clientul o accepta tot
      el, din aplicatie: semnatura ramane a lui, nu a administratorului.
    - `respinge` — inchide dosarul.
    - `cere_documente` — muta mingea la client, cu un mesaj despre ce lipseste.
    - `notifica` — il anunta ca ceva nu se leaga, fara sa schimbe starea.
    - `retrage_oferta` — singura care lucreaza peste un dosar ofertat: il aduce
      inapoi in analiza si goleste campurile ofertei, cu motiv scris in fir.
    """
    if cerere.actiune == "retrage_oferta":
        rezultat, _ = await serviciu.retrage_oferta(
            id_cerere, administrator.user_id, cerere.nota or ""
        )
    elif cerere.actiune == "cere_documente":
        # Cele doua actiuni cu mesaj intorc `(cerere, mesaj)`. Aici raspunsul e
        # starea dosarului; bula din fir intereseaza doar ruta `/mesaje`.
        rezultat, _ = await serviciu.cere_documente(
            id_cerere, administrator.user_id, cerere.nota or ""
        )
    elif cerere.actiune == "notifica":
        rezultat, _ = await serviciu.notifica_client(
            id_cerere, administrator.user_id, cerere.nota or ""
        )
    else:
        rezultat = await serviciu.decide_manual(
            id_cerere, administrator.user_id, cerere.actiune == "aproba", cerere.nota
        )
    return CerereResponse(**_cerere_publica(rezultat))


@router_admin.post("/cereri/{id_cerere}/mesaje", response_model=MesajResponse, status_code=201)
async def raspunde_in_fir(
    id_cerere: UUID,
    cerere: MesajRequest,
    administrator: UserContext = Depends(cere_administrator),
    serviciu: CreditService = Depends(get_credit_service),
) -> MesajResponse:
    """Raspunsul analistului, fara sa fie o decizie.

    Cele patru actiuni din `/decizie` isi scriu si ele textul in acelasi fir;
    asta e pentru cand nu e nimic de decis, doar de raspuns.
    """
    _, mesaj = await serviciu.notifica_client(id_cerere, administrator.user_id, cerere.text)
    return MesajResponse(**_mesaj_public(mesaj))


@router_admin.get("/cereri", response_model=list[CerereAdminResponse])
async def toate_cererile(
    status: str | None = Query(default=None),
    serviciu: CreditService = Depends(get_credit_service),
    ai_repo: CreditAiRepository = Depends(get_credit_ai_repository),
) -> list[CerereAdminResponse]:
    """Toate cererile, optional filtrate — ca sa poata fi auditate si cele automate."""
    cereri = await serviciu.cereri_toate(status)
    semnale = await _semnale_grupate_sigur(ai_repo, [UUID(c["id"]) for c in cereri])
    return [_cerere_admin(cerere, semnale.get(cerere["id"])) for cerere in cereri]


@router_admin.get("/cereri/{id_cerere}", response_model=DosarResponse)
async def dosar(
    id_cerere: UUID,
    background: BackgroundTasks,
    serviciu: CreditService = Depends(get_credit_service),
    ai_repo: CreditAiRepository = Depends(get_credit_ai_repository),
    pipeline: CreditAiPipeline = Depends(get_credit_ai_pipeline),
) -> DosarResponse:
    """Cererea, cele patru verificari de venit, documentele si — cand exista —
    ultima rulare a pipeline-ului AI consultativ.

    Catch-up lazy: daca datele s-au schimbat de la ultima rulare (sau n-a
    rulat niciodata), porneste una noua ca task de fundal. Raspunsul de acum
    arata ce exista deja — niciodata nu asteapta dupa model.
    """
    # `marcheaza_citit`: firul vine in acest raspuns, deci analistul chiar il
    # vede acum. Ruta de "ruleaza AI" cheama tot `dosar()`, dar fara steag — un
    # buton apasat nu inseamna ca cineva a citit mesajele.
    date = await serviciu.dosar(id_cerere, marcheaza_citit=True)
    ai_dosar = await _dosar_ai_sigur(ai_repo, id_cerere)
    background.add_task(pipeline.ruleaza, id_cerere, "lazy")
    return _dosar_response(date, ai_dosar)


@router_admin.post("/cereri/{id_cerere}/ai", response_model=DosarResponse)
async def ruleaza_ai(
    id_cerere: UUID,
    serviciu: CreditService = Depends(get_credit_service),
    ai_repo: CreditAiRepository = Depends(get_credit_ai_repository),
    pipeline: CreditAiPipeline = Depends(get_credit_ai_pipeline),
) -> DosarResponse:
    """"Ruleaza din nou" — spre deosebire de catch-up-ul lazy, sare peste
    refolosirea prin hash: recheama efectiv modelul, sincron, ca analistul sa
    vada imediat rezultatul."""
    await pipeline.ruleaza(id_cerere, "manual", forta=True)
    date = await serviciu.dosar(id_cerere)
    ai_dosar = await _dosar_ai_sigur(ai_repo, id_cerere)
    return _dosar_response(date, ai_dosar)


@router_admin.get("/ai/rezumat", response_model=ObservabilitateAiResponse)
async def observabilitate_ai(
    ai_repo: CreditAiRepository = Depends(get_credit_ai_repository),
) -> ObservabilitateAiResponse:
    """Rulari si esecuri pe etapa, cost estimat si rata de acord AI vs. decizia
    finala a omului — vezi view-urile SQL din 0018_credit_ai_pipeline.sql."""
    rezumat_zilnic, rata_acord, cost = await asyncio.gather(
        ai_repo.rezumat_zilnic(), ai_repo.rata_acord(), ai_repo.cost_recent()
    )
    return ObservabilitateAiResponse(
        rezumat_zilnic=[RezumatZilnicEtapaResponse(**r) for r in rezumat_zilnic],
        rata_acord=RataAcordResponse(**rata_acord),
        cost_estimat_usd_30_zile=cost,
        etape=[
            EtapaSpecResponse(
                id=spec.id, scop=spec.scop, responsabilitati=list(spec.responsabilitati),
                interzis=list(spec.interzis), are_nevoie_de_model=spec.are_nevoie_de_model,
                versiune_prompt=spec.versiune_prompt, prompt_sistem=spec.prompt_sistem,
            )
            for spec in ALL_ETAPE_SPECS
        ],
    )


@router_admin.post("/documente/{id_document}/confirma", response_model=DosarResponse)
async def confirma_document(
    id_document: UUID,
    cerere: ConfirmaDocumentRequest,
    background: BackgroundTasks,
    administrator: UserContext = Depends(cere_administrator),
    serviciu: CreditService = Depends(get_credit_service),
    ai_repo: CreditAiRepository = Depends(get_credit_ai_repository),
    pipeline: CreditAiPipeline = Depends(get_credit_ai_pipeline),
) -> DosarResponse:
    """Valideaza cifra din adeverinta si reevalueaza cererea cu ea.

    Analistul completeaza o intrare a motorului de scoring, nu alege un
    rezultat: dupa confirmare ruleaza acelasi calcul determinist, cu venitul in
    plus. De-aia raspunsul e dosarul intreg — scorul se poate fi schimbat.
    """
    date = await serviciu.confirma_document(
        id_document, administrator.user_id, cerere.venit_confirmat
    )
    id_cerere = UUID(date["cerere"]["id"])
    background.add_task(pipeline.ruleaza, id_cerere, "document_confirmat")
    ai_dosar = await _dosar_ai_sigur(ai_repo, id_cerere)
    return _dosar_response(date, ai_dosar)


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


def _cerere_admin(cerere: dict, semnale: dict | None = None) -> CerereAdminResponse:
    return CerereAdminResponse(
        **_cerere_publica(cerere),
        nume=(cerere.get("profiles") or {}).get("nume", "necunoscut"),
        venit_folosit=cerere.get("venit_folosit"),
        obligatii_folosite=cerere.get("obligatii_folosite"),
        motive=cerere.get("motive") or [],
        semnale=SemnaleRezumatResponse(**semnale) if semnale else None,
    )


async def _dosar_ai_sigur(ai_repo: CreditAiRepository, id_cerere: UUID) -> dict | None:
    """Pipeline-ul AI e strict consultativ: o eroare aici (Supabase, retea) nu
    are voie sa darame pagina dosarului, care ramane utila fara el."""
    try:
        return await ai_repo.dosar_ai(id_cerere)
    except Exception:
        logger.exception("nu am putut citi rularea AI pentru cererea %s", id_cerere)
        return None


async def _semnale_grupate_sigur(ai_repo: CreditAiRepository, id_cereri: list[UUID]) -> dict[str, dict]:
    try:
        return await ai_repo.semnale_grupate(id_cereri)
    except Exception:
        logger.exception("nu am putut citi semnalele AI pentru lista de cereri")
        return {}


def _dosar_response(date: dict, ai_dosar: dict | None) -> DosarResponse:
    """Compune DosarResponse din datele deterministe (serviciu.dosar) si, cand
    exista, ultima rulare a pipeline-ului AI — folosita de cele trei rute care
    intorc dosarul complet (dosar, ruleaza_ai, confirma_document)."""
    semnale_rezumat = _conteaza_semnale(ai_dosar["semnale"]) if ai_dosar else None
    return DosarResponse(
        cerere=_cerere_admin(date["cerere"], semnale_rezumat),
        verificari=[VerificareResponse(**_verificare_publica(v)) for v in date["verificari"]],
        documente=[DocumentResponse(**_document_public(d)) for d in date["documente"]],
        mesaje=[MesajResponse(**_mesaj_public(m)) for m in date.get("mesaje", [])],
        evenimente=[EvenimentResponse(**e) for e in date.get("evenimente", [])],
        ai=DosarAiResponse(
            rulare=RulareAiResponse(**_rulare_publica(ai_dosar["rulare"])),
            etape=[EtapaAiResponse(**_etapa_publica(e)) for e in ai_dosar["etape"]],
            semnale=[SemnalResponse(**_semnal_publica(s)) for s in ai_dosar["semnale"]],
        ) if ai_dosar else None,
    )


def _rulare_publica(rulare: dict) -> dict:
    campuri = (
        "id status declansator versiune_pipeline recomandare incredere "
        "latenta_ms cost_estimat_usd creat_la finalizat_la"
    ).split()
    return {cheie: rulare.get(cheie) for cheie in campuri}


def _etapa_publica(etapa: dict) -> dict:
    campuri = "etapa status versiune_prompt deployment rezultat incredere latenta_ms cod_eroare creat_la".split()
    date = {cheie: etapa.get(cheie) for cheie in campuri}
    date["rezultat"] = date["rezultat"] or {}
    return date


def _mesaj_public(mesaj: dict) -> dict:
    campuri = "id autor text id_document creat_la citit_de_client_la".split()
    return {cheie: mesaj.get(cheie) for cheie in campuri}


def _semnal_publica(semnal: dict) -> dict:
    campuri = "cod severitate titlu detaliu sursa".split()
    date = {cheie: semnal.get(cheie) for cheie in campuri}
    date["detaliu"] = date["detaliu"] or {}
    return date


def _conteaza_semnale(semnale: list[dict]) -> dict[str, int]:
    conteaza = {"grave": 0, "atentie": 0, "informativ": 0}
    cheie_dupa_severitate = {"grav": "grave", "atentie": "atentie", "informativ": "informativ"}
    for semnal in semnale:
        cheie = cheie_dupa_severitate.get(semnal.get("severitate"))
        if cheie:
            conteaza[cheie] += 1
    return conteaza


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
        "id status suma_ceruta luni creat_la scor dti rata_lunara dae explicatie "
        "oferta_expira_la mesaje_necitite"
    ).split()
    date = {cheie: cerere.get(cheie) for cheie in campuri}
    date["mesaje_necitite"] = cerere.get("mesaje_necitite") or 0
    return date


def _credit_public(credit: dict) -> dict:
    campuri = (
        "id principal dobanda_anuala luni rata_lunara dae sold_ramas data_acordarii status inchis_la"
    ).split()
    return {cheie: credit.get(cheie) for cheie in campuri}


def _acum() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
