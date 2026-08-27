"""Investigatia de frauda: ecranul administratorului si ecranul clientului.

Doua audiente pe acelasi dosar, ca la sesizari, dar cu o asimetrie deliberata:
administratorul deschide cazul si il inchide, clientul doar raspunde. Nu exista
nicio ruta prin care un client sa deschida un caz despre el insusi sau sa-l
inchida — cine e investigat nu conduce investigatia.

Separarea se face prin dependinte (`cere_administrator` vs `get_current_user`),
nu prin verificari scrise de mana in fiecare functie.
"""

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.dependencies import (
    UserContext,
    cere_administrator,
    get_caz_service,
    get_current_user,
)
from app.services.caz_service import CazService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cazuri", tags=["cazuri"])


# -- ce intra ------------------------------------------------------------------


class TranzactieCazIn(BaseModel):
    id_tranzactie: str
    motiv: str | None = None


class DeschideRequest(BaseModel):
    id_utilizator: str
    motiv: str = Field(min_length=3, max_length=2000)
    gravitate: int | None = Field(default=None, ge=0, le=100)
    numar_semnalari: int | None = Field(default=None, ge=0)
    tranzactii: list[TranzactieCazIn] = Field(default_factory=list)


class PregatesteRequest(BaseModel):
    # Maximul e acelasi cu MAX_INTREBARI din serviciu. Peste opt intrebari,
    # mesajul devine un formular pe care nimeni nu-l completeaza.
    intrebari: list[str] = Field(min_length=1, max_length=8)
    nota: str = Field(default="", max_length=2000)


class TrimiteRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    intrebari: list[str] = Field(min_length=1, max_length=8)
    # Cele doua steaguri vin din interfata, nu sunt ghicite pe server: ecranul
    # stie daca textul a fost propus de redactor si daca administratorul l-a
    # atins inainte sa apese trimite.
    propus_de_agent: bool = False
    editat_de_om: bool = False


class InchideRequest(BaseModel):
    rezultat: str
    nota: str = Field(default="", max_length=4000)


class RaspundeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


# -- ce iese -------------------------------------------------------------------


class RandCaz(BaseModel):
    id: str
    id_utilizator: str
    id_administrator: str
    stare: str
    motiv_deschidere: str
    gravitate: int | None = None
    numar_semnalari: int | None = None
    rezultat: str | None = None
    deschis_la: str
    inchis_la: str | None = None


class RandMesaj(BaseModel):
    id: str
    autor: str
    text: str
    structura: dict = Field(default_factory=dict)
    propus_de_agent: bool = False
    editat_de_om: bool = False
    creat_la: str


class RandTranzactie(BaseModel):
    id: str
    suma: float
    valuta: str
    descriere: str | None = None
    creat_la: str
    motiv: str | None = None


class DosarResponse(BaseModel):
    caz: RandCaz
    tranzactii: list[RandTranzactie] = Field(default_factory=list)
    mesaje: list[RandMesaj] = Field(default_factory=list)


class FirResponse(BaseModel):
    caz: RandCaz
    mesaje: list[RandMesaj] = Field(default_factory=list)


class MesajPropusResponse(BaseModel):
    text: str
    intrebari: list[str]
    # Fals cand agentul nu e configurat sau n-a putut scrie. Nu e o eroare:
    # interfata arata caseta goala si administratorul scrie el.
    scris_de_agent: bool


def _caz(r: dict) -> RandCaz:
    return RandCaz(
        id=str(r["id"]),
        id_utilizator=str(r["id_utilizator"]),
        id_administrator=str(r["id_administrator"]),
        stare=r["stare"],
        motiv_deschidere=r["motiv_deschidere"],
        gravitate=r.get("gravitate"),
        numar_semnalari=r.get("numar_semnalari"),
        rezultat=r.get("rezultat"),
        deschis_la=str(r["deschis_la"]),
        inchis_la=str(r["inchis_la"]) if r.get("inchis_la") else None,
    )


def _mesaj(r: dict) -> RandMesaj:
    return RandMesaj(
        id=str(r["id"]),
        autor=r["autor"],
        text=r["text"],
        structura=r.get("structura") or {},
        propus_de_agent=bool(r.get("propus_de_agent")),
        editat_de_om=bool(r.get("editat_de_om")),
        creat_la=str(r["creat_la"]),
    )


def _tranzactie(r: dict) -> RandTranzactie:
    t = r["tranzactii"]
    return RandTranzactie(
        id=str(t["id"]),
        suma=float(t.get("suma") or 0),
        valuta=str(t.get("valuta") or "RON"),
        descriere=t.get("descriere"),
        creat_la=str(t["creat_la"]),
        motiv=r.get("motiv"),
    )


# -- administratorul -----------------------------------------------------------


@router.post("", response_model=RandCaz)
async def deschide(
    cerere: DeschideRequest,
    administrator: UserContext = Depends(cere_administrator),
    serviciu: CazService = Depends(get_caz_service),
) -> RandCaz:
    """Deschide cazul. Daca omul are deja unul nerezolvat, il primeste pe acela."""
    caz = await serviciu.deschide(
        id_administrator=str(administrator.user_id),
        id_utilizator=cerere.id_utilizator,
        motiv=cerere.motiv,
        gravitate=cerere.gravitate,
        numar_semnalari=cerere.numar_semnalari,
        tranzactii=[t.model_dump() for t in cerere.tranzactii],
    )
    return _caz(caz)


@router.get("/coada", response_model=list[RandCaz])
async def coada(
    doar_deschise: bool = Query(default=True),
    administrator: UserContext = Depends(cere_administrator),
    serviciu: CazService = Depends(get_caz_service),
) -> list[RandCaz]:
    """Cazurile de rezolvat, cel mai vechi primul."""
    return [_caz(r) for r in await serviciu.coada(doar_deschise)]


@router.get("/ale-mele", response_model=list[RandCaz])
async def ale_mele(
    user: UserContext = Depends(get_current_user),
    serviciu: CazService = Depends(get_caz_service),
) -> list[RandCaz]:
    """Cazurile proprii ale clientului."""
    return [_caz(r) for r in await serviciu.ale_utilizatorului(str(user.user_id))]


@router.post("/{id_caz}/pregateste", response_model=MesajPropusResponse)
async def pregateste(
    id_caz: str,
    cerere: PregatesteRequest,
    administrator: UserContext = Depends(cere_administrator),
    serviciu: CazService = Depends(get_caz_service),
) -> MesajPropusResponse:
    """Cere redactorului un text. Nu scrie nimic in dosar si nu trimite nimic."""
    propus = await serviciu.pregateste_mesaj(id_caz, cerere.intrebari, cerere.nota)
    return MesajPropusResponse(
        text=propus.text,
        intrebari=list(propus.intrebari),
        scris_de_agent=propus.scris_de_agent,
    )


@router.post("/{id_caz}/mesaje", response_model=RandMesaj)
async def trimite(
    id_caz: str,
    cerere: TrimiteRequest,
    administrator: UserContext = Depends(cere_administrator),
    serviciu: CazService = Depends(get_caz_service),
) -> RandMesaj:
    """Trimite clientului mesajul pe care administratorul tocmai l-a citit."""
    return _mesaj(
        await serviciu.trimite_mesaj(
            id_caz=id_caz,
            id_administrator=str(administrator.user_id),
            text=cerere.text,
            intrebari=cerere.intrebari,
            propus_de_agent=cerere.propus_de_agent,
            editat_de_om=cerere.editat_de_om,
        )
    )


@router.post("/{id_caz}/inchide", response_model=RandCaz)
async def inchide(
    id_caz: str,
    cerere: InchideRequest,
    administrator: UserContext = Depends(cere_administrator),
    serviciu: CazService = Depends(get_caz_service),
) -> RandCaz:
    """Consemneaza urmarea aleasa de administrator.

    Nu blocheaza si nu deblocheaza nimic. Chiar si `rezultat='deblocat'` doar
    scrie ce a decis omul; deblocarea propriu-zisa e alt buton, in ecranul
    contului, si ramane o apasare separata.
    """
    return _caz(
        await serviciu.inchide(id_caz, str(administrator.user_id), cerere.rezultat, cerere.nota)
    )


@router.get("/{id_caz}", response_model=DosarResponse)
async def dosar(
    id_caz: str,
    administrator: UserContext = Depends(cere_administrator),
    serviciu: CazService = Depends(get_caz_service),
) -> DosarResponse:
    """Dosarul intreg: cazul, platile semnalate si tot firul, analize incluse."""
    d = await serviciu.dosar(id_caz)
    return DosarResponse(
        caz=_caz(d["caz"]),
        tranzactii=[_tranzactie(r) for r in d["tranzactii"] if r.get("tranzactii")],
        mesaje=[_mesaj(m) for m in d["mesaje"]],
    )


# -- clientul ------------------------------------------------------------------


@router.get("/{id_caz}/fir", response_model=FirResponse)
async def fir(
    id_caz: str,
    user: UserContext = Depends(get_current_user),
    serviciu: CazService = Depends(get_caz_service),
) -> FirResponse:
    """Firul asa cum il vede clientul: fara mesajele interne de la 'sistem'."""
    d = await serviciu.dosarul_clientului(id_caz, str(user.user_id))
    return FirResponse(caz=_caz(d["caz"]), mesaje=[_mesaj(m) for m in d["mesaje"]])


@router.post("/{id_caz}/raspunde", response_model=RandMesaj)
async def raspunde(
    id_caz: str,
    cerere: RaspundeRequest,
    user: UserContext = Depends(get_current_user),
    serviciu: CazService = Depends(get_caz_service),
) -> RandMesaj:
    """Raspunsul clientului. Serviciul verifica el ca dosarul chiar e al lui."""
    return _mesaj(await serviciu.primeste_raspuns(id_caz, str(user.user_id), cerere.text))
