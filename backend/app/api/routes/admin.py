"""Zona administratorului: conturile semnalate si rapoartele lor.

Tot ce e aici cere rol de administrator in baza de date. Verificarea din
dependinta e prima bariera; a doua, cea care conteaza, sunt politicile RLS din
0004_rol_administrator.sql — fara ele, cererile n-ar intoarce nimic oricum.

Fiecare citire lasa o urma in public.acces_administrator: cine s-a uitat la
datele cui si cand.
"""

import logging
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from supabase import Client
from uuid import UUID

from app.api.dependencies import (
    UserContext,
    cere_administrator,
    get_admin_supabase,
    get_user_supabase,
)
from app.infrastructure.config import Settings, get_settings
from app.ml.neregularitati import DetectorNeregularitati
from app.rapoarte import csv_raport, pdf_raport
from app.repositories.admin_repository import AdminRepository, AnalizaRepository
from app.schemas.admin import (
    AnalizaRequest,
    AnalizaResponse,
    CerereInchidereContResponse,
    CerereStergereAdminResponse,
    DecizieInchidereRequest,
    DecizieStergereRequest,
    ContSemnalatResponse,
    IstoricAnalizaResponse,
    StareConturiResponse,
    StareContResponse,
    RaportResponse,
    StareModelResponse,
)
from app.services.analiza_cont_service import AnalizaContService
from app.services.raport_service import Raport, RaportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _serviciu(client: Client, settings: Settings) -> tuple[RaportService, AdminRepository]:
    depozit = AdminRepository(client)
    serviciu = RaportService(
        depozit,
        DetectorNeregularitati.cu_model_de_pe_disc(),
        settings.analiza_limita_randuri,
    )
    return serviciu, depozit


async def _urma(
    depozit: AdminRepository,
    administrator: UserContext,
    actiune: str,
    id_utilizator: UUID | None = None,
    detalii: str | None = None,
) -> None:
    """Scrie urma fara sa poata darama cererea.

    Un raport care esueaza fiindca n-a putut scrie o linie de audit ar fi mai
    rau decat unul livrat cu urma lipsa. Lipsa se vede in loguri.
    """
    try:
        await depozit.scrie_acces(administrator.user_id, actiune, id_utilizator, detalii)
    except Exception:
        logger.exception(
            "nu am putut scrie urma de acces administrator=%s actiune=%s",
            administrator.user_id,
            actiune,
        )


@router.get("/conturi-semnalate", response_model=list[ContSemnalatResponse])
async def conturi_semnalate(
    zile: int = Query(default=30, ge=1, le=365),
    administrator: UserContext = Depends(cere_administrator),
    client: Client = Depends(get_user_supabase),
    settings: Settings = Depends(get_settings),
) -> list[ContSemnalatResponse]:
    """Conturile cu plati atipice, cel mai greu caz primul."""
    serviciu, depozit = _serviciu(client, settings)
    rezumate = await serviciu.conturi_semnalate(zile)
    await _urma(depozit, administrator, "lista_alerte", detalii=f"zile={zile}")
    return [ContSemnalatResponse(**asdict(r)) for r in rezumate]


@router.get("/stare-detectie", response_model=StareModelResponse)
async def stare_detectie(
    administrator: UserContext = Depends(cere_administrator),
) -> StareModelResponse:
    """Daca stratul de model participa la detectie, sau lista vine doar din reguli.

    Nu lasa urma de audit: nu se citesc datele nimanui, e starea sistemului.
    """
    from app.ml.neregularitati import stare_model

    stare = stare_model()
    return StareModelResponse(
        activ=stare.activ,
        antrenat_la=stare.antrenat_la,
        marime_kb=stare.marime_kb,
        explicatie=stare.explicatie,
    )

async def _construieste_raport(
    serviciu: RaportService, user_id: UUID, zile: int, cu_sinteza: bool
) -> Raport:
    raport = await serviciu.raport(user_id, zile)
    if raport is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contul nu a fost gasit."
        )

    if cu_sinteza and raport.constatari:
        # Sinteza e in plus, nu in locul faptelor: daca modelul lipseste sau
        # cade, raportul pleaca la fel, doar fara paragraful de sus.
        try:
            from app.infrastructure.llm import get_client_model
            from app.services.sinteza import scrie_sinteza

            if get_settings().agenti_activi:
                raport.sinteza = await scrie_sinteza(raport, get_client_model())
        except Exception:
            logger.exception("sinteza a esuat; trimit raportul fara ea")

    return raport


@router.get("/raport/{id_utilizator}", response_model=RaportResponse)
async def raport_json(
    id_utilizator: UUID,
    zile: int = Query(default=180, ge=1, le=365),
    sinteza: bool = Query(default=False, description="adauga paragraful scris de model"),
    administrator: UserContext = Depends(cere_administrator),
    client: Client = Depends(get_user_supabase),
    settings: Settings = Depends(get_settings),
) -> RaportResponse:
    serviciu, depozit = _serviciu(client, settings)
    raport = await _construieste_raport(serviciu, id_utilizator, zile, sinteza)
    await _urma(depozit, administrator, "lista_alerte", id_utilizator, f"zile={zile}")

    return RaportResponse(
        id_utilizator=raport.id_utilizator,
        nume=raport.nume,
        email=raport.email,
        iban=raport.iban,
        zile=raport.zile,
        generat_la=raport.generat_la.isoformat(),
        total_tranzactii=raport.total_tranzactii,
        numar_semnalari=len(raport.constatari),
        suma_semnalata=raport.suma_semnalata,
        scor_maxim=raport.scor_maxim,
        pe_tip=raport.pe_tip,
        sinteza=raport.sinteza,
        constatari=[asdict(c) for c in raport.constatari],
    )


@router.get("/raport/{id_utilizator}/pdf")
async def raport_pdf(
    id_utilizator: UUID,
    zile: int = Query(default=180, ge=1, le=365),
    sinteza: bool = Query(default=True),
    administrator: UserContext = Depends(cere_administrator),
    client: Client = Depends(get_user_supabase),
    settings: Settings = Depends(get_settings),
) -> Response:
    serviciu, depozit = _serviciu(client, settings)
    raport = await _construieste_raport(serviciu, id_utilizator, zile, sinteza)
    await _urma(depozit, administrator, "raport_pdf", id_utilizator, f"zile={zile}")

    return Response(
        content=pdf_raport.randeaza(raport),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{pdf_raport.nume_fisier(raport)}"'
        },
    )


@router.get("/raport/{id_utilizator}/csv")
async def raport_csv(
    id_utilizator: UUID,
    zile: int = Query(default=180, ge=1, le=365),
    administrator: UserContext = Depends(cere_administrator),
    client: Client = Depends(get_user_supabase),
    settings: Settings = Depends(get_settings),
) -> Response:
    serviciu, depozit = _serviciu(client, settings)
    raport = await _construieste_raport(serviciu, id_utilizator, zile, cu_sinteza=False)
    await _urma(depozit, administrator, "raport_csv", id_utilizator, f"zile={zile}")

    return Response(
        content=csv_raport.randeaza(raport),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{csv_raport.nume_fisier(raport)}"'
        },
    )


# -----------------------------------------------------------------------------
# Analiza unui cont: decizia unui om, si ce se intampla in urma ei
# -----------------------------------------------------------------------------


def _analiza(client: Client) -> AnalizaContService:
    return AnalizaContService(AnalizaRepository(client), AdminRepository(client))


@router.get("/cont/{id_utilizator}/istoric", response_model=StareContResponse)
async def istoric_analize(
    id_utilizator: UUID,
    administrator: UserContext = Depends(cere_administrator),
    client: Client = Depends(get_admin_supabase),
) -> StareContResponse:
    """Ce s-a hotarat pana acum pe acest cont, si cum stau conturile azi."""
    depozit = AnalizaRepository(client)
    randuri = await _analiza(client).istoric(id_utilizator)
    conturi = await depozit.conturi(id_utilizator)

    analize = [
        IstoricAnalizaResponse(
            id=str(r["id"]),
            decizie=r["decizie"],
            observatie=r.get("observatie"),
            gravitate=r.get("gravitate"),
            numar_semnalari=r.get("numar_semnalari"),
            conturi_blocate=r.get("conturi_blocate") or 0,
            creat_la=str(r["creat_la"]),
        )
        for r in randuri
    ]

    return StareContResponse(
        conturi_total=len(conturi),
        conturi_blocate=sum(1 for c in conturi if c["blocat_administrativ"]),
        analize=analize,
    )


@router.post("/cont/{id_utilizator}/analiza", response_model=AnalizaResponse)
async def scrie_analiza(
    id_utilizator: UUID,
    cerere: AnalizaRequest,
    administrator: UserContext = Depends(cere_administrator),
    client: Client = Depends(get_admin_supabase),
) -> AnalizaResponse:
    """Consemneaza hotararea si, daca s-a cerut anume, blocheaza sau deblocheaza.

    Verdictul si masura sunt separate: `frauda` consemneaza doar suspiciunea
    confirmata. Cardurile se blocheaza numai cu `aplica_blocarea`, iar
    `deblocat` ridica blocarea. Clientul e anuntat cand i se schimba situatia
    pe cont, nu cand cineva scrie o observatie despre el.
    """
    rezultat = await _analiza(client).decide(
        id_utilizator,
        administrator.user_id,
        cerere.decizie,
        cerere.observatie,
        gravitate=cerere.gravitate,
        numar_semnalari=cerere.numar_semnalari,
        zile=cerere.zile,
        aplica_blocarea=cerere.aplica_blocarea,
    )

    depozit = AdminRepository(client)
    await _urma(
        depozit,
        administrator,
        "lista_alerte",
        id_utilizator=id_utilizator,
        detalii=f"analiza decizie={cerere.decizie} conturi={rezultat.conturi_atinse}",
    )

    return AnalizaResponse(
        decizie=rezultat.decizie,
        observatie=rezultat.observatie,
        conturi_atinse=rezultat.conturi_atinse,
        notificare_trimisa=rezultat.notificare_trimisa,
        creat_la=rezultat.creat_la,
    )


@router.get("/stare-conturi", response_model=list[StareConturiResponse])
async def stare_conturi(
    administrator: UserContext = Depends(cere_administrator),
    client: Client = Depends(get_admin_supabase),
) -> list[StareConturiResponse]:
    """Starea conturilor tuturor clientilor, pentru lista completa.

    Ruta proprie, nu un camp adaugat la lista de conturi din
    api/identity/admin/conturi: aceea raspunde la alta intrebare si apartine
    fluxului de verificare a identitatii.
    """
    pe_om = await AnalizaRepository(client).stare_conturi_toti()
    return [
        StareConturiResponse(id_utilizator=uid, total=s["total"], blocate=s["blocate"])
        for uid, s in pe_om.items()
    ]


# ---------------------------------------------------------------------------
# Cereri de inchidere a contului
# ---------------------------------------------------------------------------


@router.get("/cereri-stergere", response_model=list[CerereStergereAdminResponse])
async def cereri_stergere(
    doar_deschise: bool = Query(default=False),
    administrator: UserContext = Depends(cere_administrator),
    client: Client = Depends(get_admin_supabase),
) -> list[CerereStergereAdminResponse]:
    """Coada de cereri, cu tot ce ii trebuie analistului ca sa decida.

    Soldurile si creditele vin odata cu lista, nu la deschiderea fiecarui rand:
    fara ele, analistul ar apasa „Sterge" si abia RPC-ul i-ar spune de ce nu se
    poate.
    """
    depozit = AdminRepository(client)
    return [
        CerereStergereAdminResponse(**cerere)
        for cerere in await depozit.cereri_stergere(doar_deschise)
    ]


@router.post("/cereri-stergere/{id_cerere}/decizie", response_model=CerereStergereAdminResponse)
async def decide_stergere(
    id_cerere: UUID,
    cerere: DecizieStergereRequest,
    administrator: UserContext = Depends(cere_administrator),
    client: Client = Depends(get_admin_supabase),
) -> CerereStergereAdminResponse:
    """Aproba sau respinge. La aprobare, RPC-ul consolideaza intai conturile.

    Decizia scrie si notificarea catre client — nu ramane o schimbare de status
    pe care omul o descopera intrand din intamplare in Setari.
    """
    depozit = AdminRepository(client)
    rezultat = await depozit.decide_stergere(
        id_cerere, administrator.user_id, cerere.aproba, cerere.motiv
    )
    return CerereStergereAdminResponse(**rezultat)


@router.post("/cereri-stergere/{id_cerere}/sterge", status_code=204)
async def sterge_client(
    id_cerere: UUID,
    administrator: UserContext = Depends(cere_administrator),
    client: Client = Depends(get_admin_supabase),
) -> Response:
    """Stergerea efectiva, dupa o cerere aprobata.

    Poarta pe solduri sta in `public.sterge_client` (0038), nu aici: un buton
    dezactivat in interfata e o sugestie, o exceptie din RPC e o regula. Ruta
    doar transmite si sterge apoi utilizatorul din `auth`, unde SQL-ul nostru
    n-are acces.
    """
    depozit = AdminRepository(client)
    rezultat = await depozit.sterge_client(id_cerere, administrator.user_id)

    id_user = (rezultat or {}).get("id_utilizator")
    if id_user:
        await depozit.sterge_utilizator_auth(str(id_user))

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Cereri de inchidere a unui CONT BANCAR
#
# Alta operatiune decat cele de mai sus: acolo pleaca omul din banca, aici se
# inchide un singur cont bancar si omul ramane client. Cererea o depune clientul
# direct prin RLS (politicile din 0040); aici e doar partea bancii, care are
# nevoie de service-role ca sa mute bani.
# ---------------------------------------------------------------------------


@router.get("/cereri-inchidere-cont", response_model=list[CerereInchidereContResponse])
async def cereri_inchidere_cont(
    doar_deschise: bool = Query(default=False),
    administrator: UserContext = Depends(cere_administrator),
    client: Client = Depends(get_admin_supabase),
) -> list[CerereInchidereContResponse]:
    """Coada, cu toate conturile deschise ale clientului in fiecare rand.

    Analistul trebuie sa poata alege destinatia banilor dintr-o lista reala, nu
    sa o ghiceasca — deci vine odata cu cererea, dintr-o singura citire.
    """
    depozit = AdminRepository(client)
    return [
        CerereInchidereContResponse(**cerere)
        for cerere in await depozit.cereri_inchidere_cont(doar_deschise)
    ]


@router.post(
    "/cereri-inchidere-cont/{id_cerere}/decizie",
    response_model=CerereInchidereContResponse,
)
async def decide_inchidere_cont(
    id_cerere: UUID,
    cerere: DecizieInchidereRequest,
    administrator: UserContext = Depends(cere_administrator),
    client: Client = Depends(get_admin_supabase),
) -> CerereInchidereContResponse:
    """Aproba (muta banii, inchide cardurile, inchide contul) sau respinge.

    Garzile stau in `public.inchide_cont_bancar` (0040), nu aici: contul
    principal, contul blocat, soldul negativ si destinatia invalida sunt refuzate
    de RPC, intr-o singura tranzactie cu mutarea banilor. Ruta doar transmite.
    """
    depozit = AdminRepository(client)
    rezultat = await depozit.decide_inchidere_cont(
        id_cerere,
        administrator.user_id,
        cerere.aproba,
        id_destinatie=cerere.id_cont_destinatie,
        motiv=cerere.motiv,
    )
    return CerereInchidereContResponse(**rezultat)


@router.post("/conturi/{id_cont}/redeschide", status_code=204)
async def redeschide_cont(
    id_cont: UUID,
    administrator: UserContext = Depends(cere_administrator),
    client: Client = Depends(get_admin_supabase),
) -> Response:
    """Anuleaza o inchidere gresita.

    Banii NU se intorc singuri — au plecat intr-un cont real si pot fi deja
    cheltuiti. Se redeschide contul gol, iar restul se rezolva cu un transfer
    obisnuit; asta scrie si in notificarea catre client.
    """
    depozit = AdminRepository(client)
    await depozit.redeschide_cont(id_cont, administrator.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
