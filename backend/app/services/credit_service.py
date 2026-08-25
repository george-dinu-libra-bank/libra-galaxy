"""Orchestrarea creditarii: simulare, cerere, verificari, decizie, acordare, rate.

Serviciul nu decide nimic singur — pune cap la cap piesele din `app/credit/`
(toate pure si testate) si scrie rezultatul. Ce e important sa ramana asa:

- **Decizia e reproductibila.** Aceleasi date dau acelasi scor, oricand. Modelul
  de limbaj primeste decizia deja luata si doar o pune in cuvinte; daca nu e
  configurat, textul determinist din motive tine loc (tiparul din alerte.py).
- **Graficul se calculeaza o singura data, aici.** RPC-ul din baza il primeste si
  il valideaza, dar nu il recalculeaza.
- **Ratele se proceseaza lenes.** Nu exista cron in proiect, deci orice citire a
  unui credit incaseaza intai ce e scadent. Idempotenta e garantata de constrangerea
  `credit_rate_unica` si de lock-ul din RPC, nu de disciplina apelantului.
"""

from __future__ import annotations

import asyncio
import calendar
import logging

from anyio import to_thread
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid4

from app.core.errors import ResourceNotFoundError, ValidationError
from app.credit import amortizare, reguli, scorecard
from app.credit.adeverinta import citeste_adeverinta
from app.credit.ai.contracte import DatePipelineCredit
from app.credit.venit import VenitConstatat, detecteaza_venit
from app.infrastructure.document_text import text_din_document
from app.ml.caracteristici import normalizeaza
from app.ml.neregularitati import DetectorNeregularitati
from app.repositories.credit_repository import CreditRepository

logger = logging.getLogger(__name__)

# Desparte textul mesajului de marcajul cu id-ul cererii din notificare.
# Interfata taie marcajul inainte de afisare (clopotel-notificari.tsx).
SEPARATOR_MARCAJ = chr(10) * 2

PRODUS_IMPLICIT = "galaxy-flex-personal"
ZILE_VALABILITATE_OFERTA = 7
# Cat de mult crede banca o adeverinta fata de incasari vazute in cont: un
# document poate fi si eronat, si falsificat, dar e verificabil — deci intre
# declaratie (0) si tranzactii (pana la 1).
INCREDERE_ADEVERINTA = 0.6
# Fereastra pe care se numara platile atipice pentru factorul de comportament.
ZILE_ISTORIC_COMPORTAMENT = 180

STATUSURI_CERERE = (
    "ciorna", "in_analiza", "oferta", "analiza_manuala", "asteapta_documente",
    "respinsa", "acceptata", "anulata", "expirata",
)
# Stari din care o cerere nu mai iese. Din momentul in care ajunge intr-una,
# incepe sa curga retentia documentelor.
STATUSURI_FINALE = ("respinsa", "acceptata", "anulata", "expirata")

# De unde isi poate retrage clientul cererea. 'oferta' lipseste intentionat:
# acolo are ceva de semnat, iar ignorarea duce singura la 'expirata'.
STATUSURI_ANULABILE = ("ciorna", "in_analiza", "analiza_manuala", "asteapta_documente")

# Dosarele deschise, pe care un analist le poate atinge. 'analiza_manuala' =
# asteapta banca; 'asteapta_documente' = asteapta clientul. Analistul poate
# decide din amandoua: daca actele cerute nu mai vin, dosarul trebuie sa se
# poata inchide.
STATUSURI_IN_LUCRU = ("analiza_manuala", "asteapta_documente")

# Unde firul mai poate primi mesaje. Include 'oferta': acolo clientul are cel
# mai des intrebari, iar un raspuns nu schimba nimic din angajament.
STATUSURI_CU_FIR = STATUSURI_IN_LUCRU + ("oferta", "in_analiza")

# Cat mai traieste fisierul dupa ce dosarul s-a inchis. Randul din
# credit_documente ramane pentru totdeauna, cu ce s-a citit si cine a confirmat;
# doar adeverinta propriu-zisa dispare. O luna acopera o contestatie facuta la
# cald, care e singurul motiv realist de a te intoarce la document.
ZILE_RETENTIE_DOCUMENTE = 30

# Ce se accepta la incarcare. Aceeasi lista e pusa si pe bucket in 0015: aici
# opreste devreme, acolo e ultima bariera pentru cine ar ocoli aplicatia.
TIPURI_DOCUMENT = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
MAX_OCTETI_DOCUMENT = 10 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class Simulare:
    suma: Decimal
    luni: int
    dobanda_anuala: Decimal
    rata_lunara: Decimal
    dae: Decimal
    total_platit: Decimal
    cost_total: Decimal
    grafic: list[dict]


@dataclass(frozen=True, slots=True)
class Decizie:
    decizie: str
    scor: int | None
    dti: Decimal | None
    motive: list[dict]
    factori: list[dict]
    explicatie: str
    rata_lunara: Decimal | None = None
    dae: Decimal | None = None
    oferta_expira_la: datetime | None = None
    # Adevarat cand o adeverinta chiar ar schimba ceva: banca n-a confirmat
    # niciun venit din sursele ei, **si** dosarul e inca deschis.
    #
    # A doua conditie nu e un detaliu. O cerere respinsa e dosar inchis si
    # refuza documente (STATUSURI_FINALE), deci a cere unul acolo ar trimite
    # omul sa incarce un fisier care e garantat respins. Iar pe respingerile pe
    # criterii hard — venit sub minim, identitate neverificata — o adeverinta
    # oricum n-ar ajuta: clientul si-a declarat singur venitul, iar identitatea
    # se rezolva din alta parte.
    cere_document: bool = False


class CreditNegasit(ResourceNotFoundError):
    """Cererea sau creditul nu exista, sau nu apartine utilizatorului.

    Acelasi raspuns pentru ambele cazuri, intentionat: cine intreaba de un id
    strain nu trebuie sa afle din raspuns daca exista.

    Mosteneste din ierarhia core/errors.py ca sa fie prinsa de handler-ul global
    din main.py si sa iasa in plicul standard — tiparul din identity_service.py.
    """

    code = "CREDIT_NOT_FOUND"


class OperatiuneRefuzata(ValidationError):
    """Starea curenta a cererii sau creditului nu permite operatiunea."""

    code = "CREDIT_STARE_INVALIDA"


class OperatiuneEsuata(ValidationError):
    """RPC-ul din baza a refuzat operatiunea (fonduri, grafic, stare).

    Codurile vin din 0010_credite_operatiuni.sql — FONDURI_INSUFICIENTE,
    GRAFIC_INVALID, OFERTA_EXPIRATA si celelalte. Se propaga ca atare, fiindca
    sunt exact ce trebuie sa afle apelantul.
    """

    code = "CREDIT_OPERATIUNE_REFUZATA"


class CreditService:
    def __init__(
        self,
        depozit: CreditRepository,
        detector: DetectorNeregularitati | None = None,
        explica=None,
    ) -> None:
        self._depozit = depozit
        self._detector = detector or DetectorNeregularitati()
        # Callable(decizie: Decizie, text_determinist: str) -> str | None.
        # Injectat ca sa poata fi inlocuit la test si ca serviciul sa nu depinda
        # de disponibilitatea unui model de limbaj — vezi app/credit/ai/etape/explicatie.py.
        self._explica = explica

    # -- simulare -----------------------------------------------------------

    async def simuleaza(
        self, suma: Decimal, luni: int, slug: str = PRODUS_IMPLICIT, de_la: date | None = None
    ) -> Simulare:
        produs = await self._produs(slug)
        return self._simulare(produs, suma, luni, de_la or date.today())

    def _simulare(self, produs: dict, suma: Decimal, luni: int, de_la: date) -> Simulare:
        principal_bani = amortizare.bani_din_lei(suma)
        dobanda = Decimal(str(produs["dobanda_anuala"]))

        rata_bani = amortizare.rata_lunara_bani(principal_bani, dobanda, luni)
        grafic = amortizare.genereaza_grafic(principal_bani, dobanda, luni)
        total_bani = sum(rata.total_bani for rata in grafic)

        return Simulare(
            suma=amortizare.lei_din_bani(principal_bani),
            luni=luni,
            dobanda_anuala=dobanda,
            rata_lunara=amortizare.lei_din_bani(rata_bani),
            dae=amortizare.dae(principal_bani, rata_bani, luni),
            total_platit=amortizare.lei_din_bani(total_bani),
            cost_total=amortizare.lei_din_bani(total_bani - principal_bani),
            grafic=_grafic_cu_scadente(grafic, de_la),
        )

    async def produs_public(self, slug: str = PRODUS_IMPLICIT) -> dict:
        """Limitele produsului pentru interfata — fara id si fara praguri de risc."""
        produs = await self._produs(slug)
        return {
            cheie: produs[cheie]
            for cheie in ("slug", "nume", "dobanda_anuala", "suma_min", "suma_max",
                          "luni_min", "luni_max", "venit_net_minim")
        }

    # -- cerere -------------------------------------------------------------

    async def cereri(self, user_id: UUID) -> list[dict]:
        return await self._depozit.cereri_utilizator(user_id)

    async def cerere(self, id_cerere: UUID, user_id: UUID) -> dict:
        return await self._cerere_proprie(id_cerere, user_id)

    async def depune_cerere(self, user_id: UUID, date_cerere: dict[str, Any]) -> dict:
        produs = await self._produs(date_cerere.get("produs", PRODUS_IMPLICIT))

        cerere = await self._depozit.creeaza_cerere({
            "id_user": str(user_id),
            "id_produs": produs["id"],
            "suma_ceruta": str(date_cerere["suma"]),
            "luni": date_cerere["luni"],
            "scop": date_cerere.get("scop"),
            "venit_declarat": str(date_cerere["venit_declarat"]),
            "angajator": date_cerere.get("angajator"),
            "vechime_angajator_luni": date_cerere.get("vechime_angajator_luni"),
            "obligatii_declarate": str(date_cerere.get("obligatii_declarate", 0)),
            "status": "ciorna",
        })

        await self._depozit.eveniment({
            "id_cerere": cerere["id"], "tip": "cerere_depusa", "actor": "client",
            "detalii": {"suma": str(date_cerere["suma"]), "luni": date_cerere["luni"]},
        })
        return cerere

    # -- evaluare -----------------------------------------------------------

    async def evalueaza(
        self, id_cerere: UUID, user_id: UUID, *, decizia_ramane_la_om: bool = False
    ) -> Decizie:
        """Ruleaza tot lantul: verificari de venit, criterii hard, scorecard.

        Se poate reevalua o cerere ramasa in 'ciorna' sau 'in_analiza'. O cerere
        care are deja oferta sau a fost acceptata nu se mai reevalueaza: oferta e
        un angajament, nu o parere.

        `decizia_ramane_la_om` opreste emiterea automata a ofertei: scorul se
        recalculeaza si se vede, dar cererea ramane in coada analistului. Se
        foloseste cand reevaluarea a fost declansata de un om care a completat o
        intrare (vezi `confirma_document`), nu de client.
        """
        cerere = await self._cerere_proprie(id_cerere, user_id)
        if cerere["status"] not in ("ciorna", "in_analiza"):
            raise OperatiuneRefuzata(f"O cerere in starea '{cerere['status']}' nu se mai evalueaza.")

        produs = await self._produs_dupa_id(cerere["id_produs"])
        profil = await self._depozit.profil(user_id)
        if not profil:
            raise CreditNegasit("Profilul nu exista.")

        suma = Decimal(str(cerere["suma_ceruta"]))
        luni = int(cerere["luni"])
        principal_bani = amortizare.bani_din_lei(suma)
        dobanda = Decimal(str(produs["dobanda_anuala"]))
        rata_bani = amortizare.rata_lunara_bani(principal_bani, dobanda, luni)
        rata_lunara = amortizare.lei_din_bani(rata_bani)

        venit, obligatii, incredere = await self._stabileste_situatia(id_cerere, user_id, cerere, profil)

        solicitant = reguli.Solicitant(
            cnp=profil["cnp"],
            verification_status=profil["verification_status"],
            venit_net=venit,
            obligatii_lunare=obligatii,
            vechime_angajator_luni=int(cerere.get("vechime_angajator_luni") or 0),
            # Cate luni de venituri am putut confirma; produsul cere 12.
            vechime_venituri_luni=await self._luni_de_venit(user_id, cerere),
        )

        motive = reguli.verifica(_produs_domeniu(produs), solicitant, suma, luni, rata_lunara)
        dti = reguli.grad_indatorare(venit, obligatii, rata_lunara) if venit > 0 else None

        if motive:
            # Respingerea pe criterii hard nu e discretionara, deci ramane
            # respingere si cand reevaluarea vine de la un analist.
            return await self._finalizeaza(
                cerere, Decizie(
                    decizie="respins", scor=None, dti=dti,
                    motive=[{"cod": m.cod, "text": m.text} for m in motive],
                    factori=[], explicatie="",
                ), venit, obligatii,
            )

        scor = scorecard.calculeaza(scorecard.DateScoring(
            dti=dti,
            venit_net=venit,
            venit_minim_produs=Decimal(str(produs["venit_net_minim"])),
            vechime_angajator_luni=solicitant.vechime_angajator_luni,
            incredere_venit=incredere,
            luni_de_la_deschiderea_contului=_luni_de_la(profil["creat_la"]),
            neregularitati_recente=await self._neregularitati(user_id),
        ))

        # Un venit pe care banca nu l-a putut confirma din nicio sursa proprie nu
        # duce niciodata la o aprobare automata, oricat de bun ar fi restul.
        #
        # Scorecard-ul singur nu acopera asta: `dovada_venit` valoreaza 15 din
        # 100, deci cineva cu DTI bun, vechime buna si relatie lunga cu banca
        # ajunge la 85 si trece pragul de 70 **cu zero dovezi** — declarand o
        # cifra pe care nimeni n-a verificat-o. Verificat pe cazul real: 85/100,
        # aprobat, 30.000 RON pe o suma scrisa de mana.
        #
        # Nu se rezolva umfland ponderea factorului, fiindca atunci dovada de
        # venit ar incepe sa compenseze un grad de indatorare prost. E o poarta,
        # nu o nuanta: fara dovada, cel mult analiza manuala — unde omul poate
        # cere o adeverinta si o poate confirma.
        venit_doar_declarat = incredere == 0.0
        verdict = scor.decizie
        if venit_doar_declarat and verdict == "aprobat":
            verdict = "analiza_manuala"
        aprobat = verdict == "aprobat"

        decizie = Decizie(
            decizie=verdict, scor=scor.total, dti=dti, motive=[],
            factori=[{"cod": f.cod, "puncte": f.puncte, "maxim": f.maxim, "explicatie": f.explicatie}
                     for f in scor.factori],
            explicatie="",
            rata_lunara=rata_lunara if aprobat else None,
            dae=amortizare.dae(principal_bani, rata_bani, luni) if aprobat else None,
            oferta_expira_la=(datetime.now(timezone.utc) + timedelta(days=ZILE_VALABILITATE_OFERTA))
            if aprobat else None,
            cere_document=venit_doar_declarat and verdict == "analiza_manuala",
        )
        return await self._finalizeaza(
            cerere, decizie, venit, obligatii, decizia_ramane_la_om=decizia_ramane_la_om
        )

    async def _finalizeaza(
        self, cerere: dict, decizie: Decizie, venit: Decimal, obligatii: Decimal,
        *, decizia_ramane_la_om: bool = False,
    ) -> Decizie:
        """Scrie rezultatul evaluarii pe cerere.

        Cand `decizia_ramane_la_om`, un verdict de "aprobat" se opreste in
        'analiza_manuala' si NU se scriu campurile de oferta. O oferta e un
        angajament fata de client — nu poate exista pe jumatate, cu rata
        completata dar fara ca cineva sa fi decis-o.
        """
        decizie = await _cu_explicatie(decizie, self._explica)
        status = {"aprobat": "oferta", "analiza_manuala": "analiza_manuala", "respins": "respinsa"}[
            decizie.decizie
        ]

        opreste_oferta = decizia_ramane_la_om and status == "oferta"
        if opreste_oferta:
            status = "analiza_manuala"

        await self._depozit.actualizeaza_cerere(UUID(cerere["id"]), {
            "status": status,
            "venit_folosit": str(venit),
            "obligatii_folosite": str(obligatii),
            "dti": str(decizie.dti) if decizie.dti is not None else None,
            "scor": decizie.scor,
            "motive": decizie.motive or decizie.factori,
            "explicatie": decizie.explicatie,
            "rata_lunara": None if opreste_oferta else (
                str(decizie.rata_lunara) if decizie.rata_lunara else None
            ),
            "dae": None if opreste_oferta else (str(decizie.dae) if decizie.dae else None),
            "oferta_expira_la": None if opreste_oferta else (
                decizie.oferta_expira_la.isoformat() if decizie.oferta_expira_la else None
            ),
        })

        await self._depozit.eveniment({
            "id_cerere": cerere["id"], "tip": f"decizie_{decizie.decizie}", "actor": "sistem",
            "detalii": {"scor": decizie.scor, "dti": str(decizie.dti) if decizie.dti else None},
        })

        if opreste_oferta:
            # Fara urma asta nu s-ar mai vedea peste sase luni ca motorul
            # spusese "aprobat" si ca oferta a asteptat un om.
            await self._depozit.eveniment({
                "id_cerere": cerere["id"], "tip": "decizie_lasata_la_analist", "actor": "sistem",
                "detalii": {"verdict_motor": decizie.decizie, "scor": decizie.scor},
            })
        return decizie

    # -- verificarile de venit ---------------------------------------------

    async def _stabileste_situatia(
        self, id_cerere: UUID, user_id: UUID, cerere: dict, profil: dict
    ) -> tuple[Decimal, Decimal, float]:
        """Cele patru surse, fiecare lasand urma in credit_verificari_venit.

        Precedenta la venit: tranzactii > adeverinta > declarat. La obligatii se
        ia maximul dintre ce declara omul si ce gaseste banca — daca declara mai
        mult decat stim noi, il credem; e in defavoarea lui, deci nu are motiv sa
        exagereze.
        """
        declarat = Decimal(str(cerere.get("venit_declarat") or 0))
        obligatii_declarate = Decimal(str(cerere.get("obligatii_declarate") or 0))

        await self._depozit.salveaza_verificare({
            "id_cerere": str(id_cerere), "sursa": "declarat",
            "venit_constatat": str(declarat), "obligatii_constatate": str(obligatii_declarate),
            "incredere": 0, "detalii": {"angajator": cerere.get("angajator")},
        })

        constatat = await self._venit_din_tranzactii(id_cerere, user_id)
        adeverinta = await self._venit_din_adeverinta(id_cerere)

        if constatat:
            venit, incredere = Decimal(str(constatat.venit_lunar)), constatat.incredere
        elif adeverinta is not None:
            venit, incredere = adeverinta, INCREDERE_ADEVERINTA
        else:
            venit, incredere = declarat, 0.0

        obligatii = max(obligatii_declarate, await self._obligatii(id_cerere, user_id, profil))
        return venit, obligatii, incredere

    async def _venit_din_tranzactii(self, id_cerere: UUID, user_id: UUID) -> VenitConstatat | None:
        randuri = await self._depozit.tranzactii_pentru_venit(user_id)
        constatat = detecteaza_venit(normalizeaza(randuri, user_id))

        await self._depozit.salveaza_verificare({
            "id_cerere": str(id_cerere), "sursa": "tranzactii",
            "venit_constatat": str(constatat.venit_lunar) if constatat else None,
            "incredere": constatat.incredere if constatat else 0,
            "detalii": {
                "platitor": constatat.platitor, "luni": constatat.luni_detectate,
                "deviatie": constatat.deviatie_relativa,
            } if constatat else {"gasit": False, "tranzactii_analizate": len(randuri)},
        })
        return constatat

    async def _venit_din_adeverinta(self, id_cerere: UUID) -> Decimal | None:
        """Venitul dintr-o adeverinta **confirmata de un analist**.

        Randul exista numai dupa ce un om s-a uitat la document si a validat
        cifra (vezi `confirma_document`) — ce a citit OCR-ul singur nu ajunge
        niciodata aici. De-asta poate primi INCREDERE_ADEVERINTA fara rezerve.

        Se ia ultima confirmare, nu prima: daca analistul revine si corecteaza,
        corectura trebuie sa fie cea care conteaza. `verificari()` intoarce
        randurile in ordinea scrierii, deci ultima potrivire e cea mai recenta.
        """
        venit = None
        for verificare in await self._depozit.verificari(id_cerere):
            if verificare["sursa"] == "adeverinta" and verificare["venit_constatat"]:
                venit = Decimal(str(verificare["venit_constatat"]))
        return venit

    async def _obligatii(self, id_cerere: UUID, user_id: UUID, profil: dict) -> Decimal:
        expuneri = await self._depozit.expuneri_birou(profil["cnp"])
        la_alte_banci = sum(Decimal(str(e["rata_lunara"])) for e in expuneri)
        la_galaxy = Decimal(str(await self._depozit.rate_lunare_credite_active(user_id)))

        await self._depozit.salveaza_verificare({
            "id_cerere": str(id_cerere), "sursa": "birou_credit",
            "obligatii_constatate": str(la_alte_banci + la_galaxy), "incredere": 1,
            "detalii": {
                "expuneri": [{"banca": e["banca"], "rata": str(e["rata_lunara"])} for e in expuneri],
                "rate_galaxy": str(la_galaxy),
            },
        })
        return la_alte_banci + la_galaxy

    async def _luni_de_venit(self, user_id: UUID, cerere: dict) -> int:
        """Cate luni de venituri poate confirma banca.

        Daca detectorul gaseste un tipar, numarul lui de incasari e dovada; altfel
        ramane declaratia clientului despre vechimea la angajator, care e tot ce
        avem.
        """
        randuri = await self._depozit.tranzactii_pentru_venit(user_id)
        constatat = detecteaza_venit(normalizeaza(randuri, user_id))
        if constatat:
            return constatat.luni_detectate
        return int(cerere.get("vechime_angajator_luni") or 0)

    async def _neregularitati(self, user_id: UUID) -> int:
        randuri = await self._depozit.tranzactii_pentru_venit(user_id, luni=6)
        return len(self._detector.evalueaza(normalizeaza(randuri, user_id)))

    # -- analiza manuala ----------------------------------------------------

    async def _cu_necitite_analist(self, cereri: list[dict]) -> list[dict]:
        """Adauga pe fiecare cerere cate mesaje ale clientului n-a citit banca.

        O singura interogare pentru toata lista, ca la contorul clientului —
        altfel coada analistului ar face cate una per dosar.
        """
        if not cereri:
            return cereri
        contor = await self._depozit.numara_necitite_analist(
            [UUID(str(c["id"])) for c in cereri]
        )
        return [{**c, "mesaje_necitite": contor.get(str(c["id"]), 0)} for c in cereri]

    async def cereri_in_analiza(self) -> list[dict]:
        # Coada e citita des si numai de administratori, deci e locul potrivit ca
        # sa se declanseze curatarea documentelor expirate: nu exista cron in
        # proiect, iar operatiunea trebuie sa porneasca din ceva ce se intampla
        # oricum. Nu poate darama citirea — vezi `_curata_documente_expirate`.
        await self._curata_documente_expirate()
        return await self._cu_necitite_analist(await self._depozit.cereri_in_analiza())

    async def cereri_toate(self, status: str | None = None) -> list[dict]:
        if status and status not in STATUSURI_CERERE:
            raise OperatiuneRefuzata(f"Statusul '{status}' nu exista.")
        return await self._cu_necitite_analist(
            await self._expira_ofertele_trecute(await self._depozit.cereri_toate(status))
        )

    async def credite_toate(self) -> list[dict]:
        return await self._depozit.credite_toate()

    async def dosar(self, id_cerere: UUID, *, marcheaza_citit: bool = False) -> dict:
        """Tot ce trebuie sa vada un analist despre o cerere, intr-un singur apel.

        Verificarile si documentele vin impreuna cu cererea fiindca fara ele
        scorul e un numar fara explicatie: „58 din 100" nu spune nimic, „58
        fiindca venitul e doar declarat" spune tot.
        """
        cerere = await self._depozit.cerere(id_cerere)
        if not cerere:
            raise CreditNegasit("Cererea nu exista.")

        # Deschiderea dosarului stinge contorul analistului: firul vine in acest
        # raspuns, deci in clipa asta chiar l-a vazut. Nu se face la orice
        # citire — listarile cheama `dosar()` fara steag, si acolo n-a citit
        # nimeni nimic.
        if marcheaza_citit:
            await self._depozit.marcheaza_mesaje_citite_analist(id_cerere)

        documente = await self._depozit.documente(id_cerere)
        return {
            "cerere": cerere,
            "verificari": await self._depozit.verificari(id_cerere),
            "documente": [
                {**document, "url": await self._url_document(document)} for document in documente
            ],
            # Firul vine in acelasi apel ca restul dosarului, ca verificarile si
            # documentele: analistul citeste tot dintr-o data.
            "mesaje": await self._depozit.mesaje(id_cerere),
        }

    async def date_pentru_pipeline(self, id_cerere: UUID) -> DatePipelineCredit:
        """Tot ce are nevoie pipeline-ul AI (app/credit/ai/pipeline.py), adunat o
        singura data — etapele nu mai fac interogari proprii, raman pure sau
        primesc doar providerul de model.

        Nu verifica proprietatea cererii: apelat exclusiv din context de
        administrator/fundal (CreditAiPipeline), niciodata direct din ruta
        clientului.
        """
        cerere = await self._depozit.cerere(id_cerere)
        if not cerere:
            raise CreditNegasit("Cererea nu exista.")
        user_id = UUID(str(cerere["id_user"]))

        verificari, documente, randuri = await asyncio.gather(
            self._depozit.verificari(id_cerere),
            self._depozit.documente(id_cerere),
            self._depozit.tranzactii_pentru_venit(user_id),
        )
        plati = normalizeaza(randuri, user_id)
        venit_constatat = detecteaza_venit(plati)

        documente_reutilizate: list[dict] = []
        for document in documente:
            hash_fisier = document.get("hash_fisier")
            if not hash_fisier:
                continue
            documente_reutilizate.extend(await self._depozit.documente_cu_hash(hash_fisier, id_cerere))

        return DatePipelineCredit(
            cerere=cerere, documente=documente, documente_reutilizate=documente_reutilizate,
            verificari=verificari, venit_constatat=venit_constatat, plati=plati,
        )

    async def _url_document(self, document: dict) -> str | None:
        """Link temporar, doar cat timp fisierul mai exista."""
        if document.get("sters_la"):
            return None
        return await self._depozit.url_document(document["storage_path"])

    async def decide_manual(
        self, id_cerere: UUID, id_admin: UUID, aproba: bool, nota: str | None = None
    ) -> dict:
        """Decizia unui om peste o cerere din zona gri.

        Scorul si factorii NU se recalculeaza si nu se sterg: raman exact cum
        i-a produs motorul. Un dosar aprobat manual trebuie sa arate ulterior si
        ca a fost la limita, si cine a decis altfel — altfel auditul nu poate
        distinge o aprobare automata de una omeneasca.

        Administratorul nu poate atinge o cerere inchisa sau deja ofertata: nu
        are ce cauta peste un refuz pe criterii hard (acolo decizia nu e
        discretionara) si nici peste o oferta emisa. Poate decide insa si peste
        un dosar care asteapta acte — daca actele nu mai vin, dosarul trebuie sa
        se poata inchide.
        """
        cerere = await self._depozit.cerere(id_cerere)
        if not cerere:
            raise CreditNegasit("Cererea nu exista.")
        if cerere["status"] not in STATUSURI_IN_LUCRU:
            raise OperatiuneRefuzata(
                f"Doar o cerere aflata in lucru poate fi decisa de un administrator; "
                f"asta e in starea '{cerere['status']}'."
            )

        motivare = (nota or "").strip()

        if aproba:
            produs = await self._produs_dupa_id(cerere["id_produs"])
            principal_bani = amortizare.bani_din_lei(cerere["suma_ceruta"])
            luni = int(cerere["luni"])
            rata_bani = amortizare.rata_lunara_bani(
                principal_bani, Decimal(str(produs["dobanda_anuala"])), luni
            )
            campuri = {
                "status": "oferta",
                "rata_lunara": str(amortizare.lei_din_bani(rata_bani)),
                "dae": str(amortizare.dae(principal_bani, rata_bani, luni)),
                "oferta_expira_la": (
                    datetime.now(timezone.utc) + timedelta(days=ZILE_VALABILITATE_OFERTA)
                ).isoformat(),
                "explicatie": _explicatie_manuala(True, motivare, cerere.get("scor")),
            }
        else:
            campuri = {
                "status": "respinsa",
                "explicatie": _explicatie_manuala(False, motivare, cerere.get("scor")),
            }

        actualizata = await self._depozit.actualizeaza_cerere(id_cerere, campuri)

        # Decizia intra si in fir, si in notificari. Pana acum motivul se scria
        # doar in `cerere.explicatie`, iar ecranul clientului nu randeaza deloc
        # cererile respinse — deci o respingere nu ajungea niciodata la om: se
        # uita in aplicatie si nu gasea nimic, ca si cum n-ar fi depus nimic.
        await self._depozit.adauga_mesaj({
            "id_cerere": str(id_cerere), "autor": "analist",
            "id_autor": str(id_admin),
            "text": campuri["explicatie"],
        })
        await self._depozit.notifica(
            UUID(str(cerere["id_user"])),
            "Ai o oferta de credit" if aproba else "Cererea de credit nu a fost aprobata",
            f"{campuri['explicatie']}" + SEPARATOR_MARCAJ + f"[cerere:{id_cerere}]",
            "info" if aproba else "atentionare",
        )

        await self._depozit.eveniment({
            "id_cerere": str(id_cerere),
            "tip": "decizie_manuala_aprobat" if aproba else "decizie_manuala_respins",
            "actor": "administrator",
            "id_actor": str(id_admin),
            "detalii": {"nota": motivare or None, "scor_automat": cerere.get("scor")},
        })
        return actualizata

    async def retrage_oferta(
        self, id_cerere: UUID, id_admin: UUID, motiv: str
    ) -> tuple[dict, dict]:
        """Aduce inapoi in analiza un dosar pentru care s-a emis deja o oferta.

        Singura cale prin care o oferta poate disparea din partea bancii. Pana
        acum nu exista niciuna, iar gaura se vedea in alta parte: `confirma_document`
        trecea pe langa starea 'oferta' si o stergea tacit. O oferta e un
        angajament fata de un om — cand chiar trebuie retrasa (date noi, suspiciune
        de frauda), retragerea trebuie sa fie o actiune cu nume, cu autor si cu
        motiv, nu un efect secundar.

        Clientul afla: mesajul intra in fir si pleaca o notificare. Altfel ar
        deschide aplicatia si ar gasi oferta disparuta, fara nicio explicatie.
        """
        cerere = await self._depozit.cerere(id_cerere)
        if not cerere:
            raise CreditNegasit("Cererea nu exista.")
        if cerere["status"] != "oferta":
            raise OperatiuneRefuzata(
                f"Doar o cerere cu oferta emisa poate fi retrasa; "
                f"asta e in starea '{cerere['status']}'."
            )

        text = (motiv or "").strip()
        if not text:
            raise OperatiuneRefuzata("Scrie motivul pentru care retragi oferta.")

        # Campurile ofertei se golesc, nu doar statusul: lasate acolo, interfata
        # ar continua sa arate o rata si o data de expirare pentru ceva ce nu mai
        # exista, iar RPC-ul de acceptare are propriile verificari pe ele.
        actualizata = await self._depozit.actualizeaza_cerere(id_cerere, {
            "status": "analiza_manuala",
            "rata_lunara": None,
            "dae": None,
            "oferta_expira_la": None,
        })

        scris = await self._depozit.adauga_mesaj({
            "id_cerere": str(id_cerere), "autor": "analist",
            "id_autor": str(id_admin), "text": text,
        })

        await self._depozit.notifica(
            UUID(str(cerere["id_user"])),
            "Oferta de credit a fost retrasa",
            f"{text}" + SEPARATOR_MARCAJ + f"[cerere:{id_cerere}]",
            "atentionare",
        )

        await self._depozit.eveniment({
            "id_cerere": str(id_cerere), "tip": "oferta_retrasa", "actor": "administrator",
            "id_actor": str(id_admin),
            "detalii": {"motiv": text, "rata_retrasa": str(cerere.get("rata_lunara"))},
        })
        return actualizata, scris

    async def cere_documente(
        self, id_cerere: UUID, id_admin: UUID, mesaj: str
    ) -> tuple[dict, dict]:
        """Trece mingea la client: are de incarcat ceva, si afla din mesaj ce.

        Nu e o decizie si nu inchide nimic — dosarul ramane deschis, deci mai
        primeste documente, iar retentia nu incepe sa curga (STATUSURI_FINALE).
        Cand clientul incarca, `incarca_document` il aduce inapoi in coada
        analistului, fara ca nimeni sa fie nevoit sa-si aminteasca de el.
        """
        return await self._scrie_mesaj(
            id_cerere, id_admin, mesaj,
            status_nou="asteapta_documente", tip_eveniment="documente_cerute",
        )

    async def notifica_client(
        self, id_cerere: UUID, id_admin: UUID, mesaj: str
    ) -> tuple[dict, dict]:
        """Spune ceva clientului fara sa schimbe starea dosarului.

        Pentru situatiile in care nu lipseste un act, dar ceva nu se leaga si
        omul trebuie sa afle. Dosarul ramane exact unde era: un mesaj nu e o
        decizie si nu muta responsabilitatea.
        """
        return await self._scrie_mesaj(
            id_cerere, id_admin, mesaj, status_nou=None, tip_eveniment="client_notificat",
        )

    async def _scrie_mesaj(
        self, id_cerere: UUID, id_admin: UUID, mesaj: str,
        *, status_nou: str | None, tip_eveniment: str,
    ) -> tuple[dict, dict]:
        """Partea comuna a celor doua: valideaza starea, scrie mesajul, lasa urma.

        Mesajul merge in firul dosarului (`credit_mesaje`), nu in `explicatie`:
        a doua e rescrisa de motor la fiecare reevaluare, iar fluxul "cer acte
        -> clientul incarca -> se reevalueaza" ar sterge exact mesajul care a
        pornit totul.

        Intoarce **si** cererea, **si** mesajul scris, fiindca apelantii au
        nevoie de lucruri diferite: `/decizie` raspunde cu starea dosarului,
        `/mesaje` raspunde cu bula noua din fir. Cat timp intorcea doar cererea,
        a doua ruta construia `MesajResponse` din campuri inexistente si pica cu
        500 dupa ce scrisese deja mesajul in baza — deci analistul retrimitea.
        """
        cerere = await self._depozit.cerere(id_cerere)
        if not cerere:
            raise CreditNegasit("Cererea nu exista.")

        # Un mesaj simplu are voie si peste o oferta emisa; unul care schimba
        # starea, nu. Clientul putea scrie in orice stare nefinala, inclusiv
        # 'oferta', dar analistul putea raspunde doar din cele doua stari de
        # lucru — deci cine intreba ceva despre oferta primita ramanea fara
        # raspuns posibil. Un raspuns nu e o decizie si nu atinge oferta.
        permise = STATUSURI_IN_LUCRU if status_nou is not None else STATUSURI_CU_FIR
        if cerere["status"] not in permise:
            raise OperatiuneRefuzata(
                f"Nu se mai poate scrie pe o cerere aflata in starea "
                f"'{cerere['status']}'."
            )

        text = (mesaj or "").strip()
        if not text:
            # Mesajul e singurul lucru pe care il vede clientul; unul gol l-ar
            # lasa sa se intrebe ce trebuie sa faca.
            raise OperatiuneRefuzata("Scrie un mesaj pentru client.")

        scris = await self._depozit.adauga_mesaj({
            "id_cerere": str(id_cerere), "autor": "analist",
            "id_autor": str(id_admin), "text": text,
        })

        # Firul se vede doar daca omul intra in aplicatie. Notificarea il aduce
        # inapoi — altfel un dosar care asteapta acte poate sta blocat saptamani
        # fiindca nimeni nu i-a spus clientului ca s-a cerut ceva.
        #
        # 'atentionare' cand are ceva de facut, 'info' cand doar afla.
        # Id-ul cererii merge in `mesaj`, dupa un marcaj: tabela `notificari` nu e
        # a noastra (n-are migratie in repo), deci n-o largim cu o coloana. Cu
        # marcajul, interfata poate duce clientul direct in firul potrivit.
        await self._depozit.notifica(
            UUID(str(cerere["id_user"])),
            "Ai nevoie de documente pentru cererea de credit"
            if status_nou == "asteapta_documente"
            else "Mesaj nou despre cererea ta de credit",
            f"{text}" + SEPARATOR_MARCAJ + f"[cerere:{id_cerere}]",
            "atentionare" if status_nou == "asteapta_documente" else "info",
        )

        # Cererea se actualizeaza doar cand starea chiar se schimba. `notifica`
        # nu muta nimic — un mesaj nu e o decizie.
        actualizata = (
            await self._depozit.actualizeaza_cerere(id_cerere, {"status": status_nou})
            if status_nou is not None
            else cerere
        )

        await self._depozit.eveniment({
            "id_cerere": str(id_cerere), "tip": tip_eveniment, "actor": "administrator",
            "id_actor": str(id_admin),
            "detalii": {"mesaj": text, "status_anterior": cerere["status"]},
        })
        return actualizata, scris

    # -- firul de discutie --------------------------------------------------

    async def mesaje(self, id_cerere: UUID, user_id: UUID | None = None) -> list[dict]:
        """Firul unei cereri.

        Cu `user_id`, verifica proprietatea — drumul clientului. Fara, e citire
        de administrator, iar accesul e oprit mai sus, in dependinta de ruta.
        """
        if user_id is not None:
            await self._cerere_proprie(id_cerere, user_id)
        elif not await self._depozit.cerere(id_cerere):
            raise CreditNegasit("Cererea nu exista.")

        return await self._depozit.mesaje(id_cerere)

    async def marcheaza_firul_citit(self, id_cerere: UUID, user_id: UUID) -> None:
        """Firul a fost deschis: mesajele bancii nu mai sunt necitite.

        „Ale bancii" inseamna `autor = 'analist'`, nu „tot ce nu e al clientului":
        mesajele `sistem` sunt generate de fapta lui (a incarcat un document),
        deci numarate ca necitite i-ar aprinde bulina pentru ce a facut singur.
        """
        await self._cerere_proprie(id_cerere, user_id)
        await self._depozit.marcheaza_mesaje_citite(id_cerere)

    async def cereri_cu_necitite(self, user_id: UUID) -> list[dict]:
        """Cererile utilizatorului, fiecare cu numarul de mesaje necitite.

        Numararea se face intr-o singura interogare pentru toata lista — altfel
        ecranul de credite ar face cate una per cerere.
        """
        cereri = await self._expira_ofertele_trecute(
            await self._depozit.cereri_utilizator(user_id)
        )
        contor = await self._depozit.numara_necitite([UUID(c["id"]) for c in cereri])
        return [{**cerere, "mesaje_necitite": contor.get(cerere["id"], 0)} for cerere in cereri]

    async def anuleaza(self, id_cerere: UUID, user_id: UUID) -> dict:
        """Clientul isi retrage cererea.

        `anulata` era al doilea status fantoma: exista in constante, dar nu-l
        scria nimeni, fiindca nu exista nicio ruta prin care sa fie cerut. Doua
        urmari: o ciorna ramanea ciorna pentru totdeauna, si — mai important —
        `finalizat_la` ramanea null, deci retentia documentelor nu pornea
        niciodata pentru dosarele abandonate. Adeverinta cuiva care s-a razgandit
        statea in bucket la nesfarsit.

        O oferta nu se anuleaza de aici: acolo omul are ceva de semnat, iar
        ignorarea ei duce singura la 'expirata'.
        """
        cerere = await self._cerere_proprie(id_cerere, user_id)
        if cerere["status"] not in STATUSURI_ANULABILE:
            raise OperatiuneRefuzata(
                f"O cerere in starea '{cerere['status']}' nu mai poate fi retrasa."
            )

        actualizata = await self._depozit.actualizeaza_cerere(id_cerere, {
            "status": "anulata",
            "finalizat_la": datetime.now(timezone.utc).isoformat(),
        })
        await self._depozit.eveniment({
            "id_cerere": str(id_cerere), "tip": "cerere_anulata", "actor": "client",
            "id_actor": str(user_id),
            "detalii": {"status_anterior": cerere["status"]},
        })
        return actualizata

    async def scrie_mesaj_client(self, id_cerere: UUID, user_id: UUID, mesaj: str) -> dict:
        """Raspunsul clientului in fir.

        Exista tocmai ca sa aiba unde intreba cand nu intelege ce act i se cere —
        pana acum singura lui actiune era sa incarce un fisier si sa spere ca e
        cel bun.
        """
        cerere = await self._cerere_proprie(id_cerere, user_id)
        if cerere["status"] in STATUSURI_FINALE:
            raise OperatiuneRefuzata(
                f"Cererea e in starea '{cerere['status']}'; discutia pe ea s-a incheiat."
            )

        text = (mesaj or "").strip()
        if not text:
            raise OperatiuneRefuzata("Scrie un mesaj.")

        return await self._depozit.adauga_mesaj({
            "id_cerere": str(id_cerere), "autor": "client",
            "id_autor": str(user_id), "text": text,
        })

    # -- documente ----------------------------------------------------------

    async def incarca_document(
        self, id_cerere: UUID, user_id: UUID, continut: bytes, content_type: str | None
    ) -> dict:
        """Urca adeverinta, o citeste, si atat.

        **Nu scrie nicio verificare de venit.** Aici documentul e citit, nu
        crezut: cifra propusa de OCR ramane in `extras`, unde n-are niciun efect
        asupra deciziei pana cand un analist o confirma. Diferenta asta e tot
        rostul fluxului — o suma citita gresit dintr-o poza inclinata ar da
        altfel un credit pe date inventate.
        """
        cerere = await self._cerere_proprie(id_cerere, user_id)
        if cerere["status"] in STATUSURI_FINALE:
            raise OperatiuneRefuzata(
                f"Cererea e in starea '{cerere['status']}'; nu mai primeste documente."
            )

        extensie = TIPURI_DOCUMENT.get((content_type or "").split(";")[0].strip().lower())
        if not extensie:
            raise OperatiuneRefuzata(
                "Se accepta doar PDF sau poza (JPEG, PNG, WebP)."
            )
        if not continut:
            raise OperatiuneRefuzata("Fisierul e gol.")
        if len(continut) > MAX_OCTETI_DOCUMENT:
            raise OperatiuneRefuzata(
                f"Fisierul depaseste {MAX_OCTETI_DOCUMENT // (1024 * 1024)} MB."
            )

        cale = f"{user_id}/{id_cerere}/{uuid4().hex}.{extensie}"
        await self._depozit.urca_document(cale, continut, content_type)

        # Pe un thread, nu pe event loop: `text_din_document` poate ajunge la
        # Tesseract (PDF scanat sau poza), adica secunde de CPU in care tot
        # backendul ar sta blocat pentru toata lumea, nu doar pentru cel care
        # incarca. Restul repository-ului foloseste deja `to_thread.run_sync`;
        # aici era singurul loc unde munca grea ramasese sincrona.
        date = await to_thread.run_sync(
            lambda: citeste_adeverinta(text_din_document(continut, content_type))
        )

        document = await self._depozit.salveaza_document({
            "id_cerere": str(id_cerere),
            "id_user": str(user_id),
            "tip": "adeverinta_venit",
            "storage_path": cale,
            "content_type": content_type,
            "marime_octeti": len(continut),
            "hash_fisier": sha256(continut).hexdigest(),
            "status": "procesat" if date.utilizabila else "ilizibil",
            "extras": {
                "venit_net": str(date.venit_net) if date.venit_net is not None else None,
                "angajator": date.angajator,
                "vechime_luni": date.vechime_luni,
                "incredere": date.incredere,
                # Textul brut ramane ca sa se poata verifica de ce a iesit cifra
                # aia, dupa ce fisierul e sters. Taiat, ca sa nu umple randul.
                "text": date.text_brut[:4000],
            },
        })

        await self._depozit.eveniment({
            "id_cerere": str(id_cerere), "tip": "document_incarcat", "actor": "client",
            "detalii": {
                "tip": "adeverinta_venit",
                "citit": date.utilizabila,
                "incredere": date.incredere,
            },
        })

        # Documentul intra si in fir, ca dosarul sa aiba o singura cronologie:
        # "s-a cerut X -> a venit Y". Textul se genereaza din ce s-a citit, ca
        # analistul sa vada rezultatul fara sa deschida documentul.
        # `sistem`, nu `client`: textul e generat din ce a citit OCR-ul, iar sub
        # semnatura clientului parea ca l-a scris el ("S-a citit un venit net de
        # X RON"). Valoarea era permisa de baza si nefolosita de nimeni.
        await self._depozit.adauga_mesaj({
            "id_cerere": str(id_cerere), "autor": "sistem", "id_autor": str(user_id),
            "id_document": str(document["id"]),
            "text": (
                f"Am incarcat adeverinta de venit. S-a citit un venit net de "
                f"{date.venit_net} RON."
                if date.venit_net is not None
                else "Am incarcat adeverinta de venit. Suma nu s-a putut citi automat."
            ),
        })

        # Dosarul care astepta acte se intoarce singur in coada analistului.
        # Fara asta ar ramane in 'asteapta_documente' pana si-ar aminti cineva
        # de el, desi mingea e din nou la banca.
        if cerere["status"] == "asteapta_documente":
            await self._depozit.actualizeaza_cerere(id_cerere, {"status": "analiza_manuala"})
            await self._depozit.eveniment({
                "id_cerere": str(id_cerere), "tip": "documente_primite", "actor": "sistem",
                "detalii": {"id_document": str(document["id"])},
            })

        return document

    async def documente(self, id_cerere: UUID, user_id: UUID) -> list[dict]:
        await self._cerere_proprie(id_cerere, user_id)
        return await self._depozit.documente(id_cerere)

    async def confirma_document(
        self, id_document: UUID, id_admin: UUID, venit_confirmat: Decimal
    ) -> dict:
        """Analistul valideaza cifra din adeverinta, si abia atunci ea conteaza.

        Se scriu doua lucruri, nu unul: randul din `credit_verificari_venit` care
        intra in decizie, si `venit_confirmat` pe document. `extras` ramane
        neatins, cu ce citise OCR-ul. Cand cele doua difera — si vor diferi — se
        vede peste sase luni ca a fost nevoie de o corectie omeneasca, si cat de
        mare. Daca am suprascrie `extras`, am pierde exact dovada asta.

        Dupa confirmare cererea se reevalueaza: venitul e o intrare a motorului
        de scoring, iar motorul trebuie sa ruleze din nou cu ea. Decizia ramane
        deterministica — analistul a completat un camp, nu a ales un rezultat.

        **Reevaluarea nu emite oferta.** Chiar daca noul scor trece pragul de
        aprobare, cererea ramane in 'analiza_manuala': confirmarea unui fapt nu
        e o decizie, iar o oferta e un angajament fata de client. Analistul o
        emite explicit, cu "Aproba". Vezi `decizia_ramane_la_om` din `evalueaza`.
        """
        document = await self._depozit.document(id_document)
        if not document:
            raise CreditNegasit("Documentul nu exista.")
        if venit_confirmat <= 0:
            raise OperatiuneRefuzata("Venitul confirmat trebuie sa fie pozitiv.")

        id_cerere = UUID(str(document["id_cerere"]))
        cerere = await self._depozit.cerere(id_cerere)
        if not cerere:
            raise CreditNegasit("Cererea nu exista.")
        if cerere["status"] in STATUSURI_FINALE:
            raise OperatiuneRefuzata(
                f"Cererea e in starea '{cerere['status']}'; decizia ei nu se mai schimba."
            )
        # `oferta` nu e in STATUSURI_FINALE, deci trecea pe langa garda de mai
        # sus — iar confirmarea readuce cererea in 'in_analiza' si reevalueaza,
        # adica **sterge tacit o oferta emisa**. Exact ce interzice `evalueaza`:
        # oferta e un angajament, nu o parere. Daca datele chiar s-au schimbat,
        # drumul e sa retragi intai oferta (`retrage_oferta`), explicit, ca
        # dosarul sa aiba un eveniment care spune cine si de ce.
        if cerere["status"] == "oferta":
            raise OperatiuneRefuzata(
                "Cererea are deja o oferta emisa. Retrage-o intai daca datele "
                "s-au schimbat; o confirmare de document nu poate sterge un "
                "angajament luat fata de client."
            )

        citit = (document.get("extras") or {}).get("venit_net")

        await self._depozit.salveaza_verificare({
            "id_cerere": str(id_cerere),
            "sursa": "adeverinta",
            "venit_constatat": str(venit_confirmat),
            "incredere": INCREDERE_ADEVERINTA,
            "detalii": {
                "id_document": str(id_document),
                "citit_de_ocr": citit,
                "confirmat_de": str(id_admin),
                "corectat": citit is not None and Decimal(str(citit)) != venit_confirmat,
            },
        })

        await self._depozit.actualizeaza_document(id_document, {
            "status": "confirmat",
            "venit_confirmat": str(venit_confirmat),
            "confirmat_de": str(id_admin),
            "confirmat_la": datetime.now(timezone.utc).isoformat(),
        })

        await self._depozit.eveniment({
            "id_cerere": str(id_cerere), "tip": "document_confirmat", "actor": "administrator",
            "id_actor": str(id_admin),
            "detalii": {"venit_confirmat": str(venit_confirmat), "citit_de_ocr": citit},
        })

        # `evalueaza` accepta doar 'ciorna' si 'in_analiza' — pe buna dreptate, ca
        # o oferta emisa sa nu se schimbe sub picioarele clientului. Aici insa
        # datele de intrare chiar s-au schimbat, deci cererea se intoarce
        # explicit in analiza inainte de a rula din nou motorul.
        #
        # `decizia_ramane_la_om`: analistul a completat o intrare a motorului, nu
        # a ales un rezultat. Scorul se recalculeaza si se vede imediat, dar
        # oferta n-o emite confirmarea — o emite omul, apasand "Aproba".
        await self._depozit.actualizeaza_cerere(id_cerere, {"status": "in_analiza"})
        await self.evalueaza(
            id_cerere, UUID(str(cerere["id_user"])), decizia_ramane_la_om=True
        )

        return await self.dosar(id_cerere)

    async def _expira_ofertele_trecute(self, cereri: list[dict]) -> list[dict]:
        """Trece pe 'expirata' ofertele carora le-a trecut termenul.

        `expirata` era un status fantoma: exista in constante si in constrangerea
        SQL, dar nu-l scria nimeni. `oferta_expira_la` se verifica doar in RPC-ul
        de acceptare, care refuza — insa cererea ramanea in 'oferta' la infinit,
        deci ecranul continua sa arate un buton „Semneaza" pentru ceva ce banca
        nu mai onora, iar refuzul venea abia dupa apasare.

        Lazy, ca `_curata_documente_expirate`: proiectul n-are cron, deci
        tranzitia porneste din citirea care se intampla oricum. Lucreaza peste
        randurile deja citite — niciun apel in plus pentru cazul obisnuit, in
        care nimic n-a expirat.

        Nu arunca: o listare de cereri n-are voie sa pice fiindca o actualizare
        secundara n-a mers.
        """
        acum = datetime.now(timezone.utc)
        rezultat: list[dict] = []

        for cerere in cereri:
            expira = cerere.get("oferta_expira_la")
            if cerere.get("status") != "oferta" or not expira:
                rezultat.append(cerere)
                continue

            try:
                termen = datetime.fromisoformat(str(expira).replace("Z", "+00:00"))
            except ValueError:
                logger.warning("expirare oferta: data ilizibila pe cererea %s", cerere.get("id"))
                rezultat.append(cerere)
                continue

            if termen.tzinfo is None:
                termen = termen.replace(tzinfo=timezone.utc)
            if termen > acum:
                rezultat.append(cerere)
                continue

            try:
                id_cerere = UUID(str(cerere["id"]))
                actualizata = await self._depozit.actualizeaza_cerere(
                    id_cerere, {"status": "expirata"}
                )
                await self._depozit.eveniment({
                    "id_cerere": str(id_cerere), "tip": "oferta_expirata", "actor": "sistem",
                    "detalii": {"expira_la": str(expira)},
                })
                rezultat.append({**cerere, **(actualizata or {"status": "expirata"})})
            except Exception:
                logger.exception("expirare oferta: cererea %s", cerere.get("id"))
                rezultat.append(cerere)

        return rezultat

    async def _curata_documente_expirate(self) -> int:
        """Sterge fisierele dosarelor inchise de peste ZILE_RETENTIE_DOCUMENTE.

        Randul din baza ramane intact — cu `extras`, cu hash-ul si cu cine a
        confirmat. Dispare doar fisierul, care e si singurul lucru care ocupa
        spatiu, si singurul care contine date personale in clar.

        Nu arunca niciodata: curatarea e un efect secundar al unei citiri, iar o
        eroare de storage n-are voie sa lase un analist fara coada de lucru.
        """
        limita = datetime.now(timezone.utc) - timedelta(days=ZILE_RETENTIE_DOCUMENTE)

        try:
            expirate = await self._depozit.documente_expirate(limita)
        except Exception:
            logger.exception("curatare documente: nu am putut citi lista")
            return 0

        sterse = 0
        for document in expirate:
            try:
                await self._depozit.sterge_document(document["storage_path"])
                await self._depozit.actualizeaza_document(UUID(str(document["id"])), {
                    "sters_la": datetime.now(timezone.utc).isoformat(),
                })
                sterse += 1
            except Exception:
                # Un fisier care nu se sterge azi se incearca din nou la
                # urmatoarea citire: `sters_la` ramane null, deci ramane in lista.
                logger.exception("curatare documente: %s", document["storage_path"])

        if sterse:
            logger.info("curatare documente: %d fisiere sterse dupa retentie", sterse)
        return sterse

    # -- acordare -----------------------------------------------------------

    async def accepta(
        self, id_cerere: UUID, user_id: UUID, id_cont: UUID, semnatura: dict
    ) -> dict:
        cerere = await self._cerere_proprie(id_cerere, user_id)
        if cerere["status"] != "oferta":
            raise OperatiuneRefuzata(
                f"Doar o cerere cu oferta poate fi acceptata; asta e in starea '{cerere['status']}'."
            )

        produs = await self._produs_dupa_id(cerere["id_produs"])
        suma = Decimal(str(cerere["suma_ceruta"]))
        luni = int(cerere["luni"])
        principal_bani = amortizare.bani_din_lei(suma)
        dobanda = Decimal(str(produs["dobanda_anuala"]))
        rata_bani = amortizare.rata_lunara_bani(principal_bani, dobanda, luni)

        grafic = _grafic_cu_scadente(
            amortizare.genereaza_grafic(principal_bani, dobanda, luni), date.today()
        )

        # RPC-ul face totul intr-o tranzactie: contract, grafic, virament, audit.
        return await _rpc(self._depozit.acorda(
            id_cerere=id_cerere,
            id_cont=id_cont,
            rata_lunara=float(amortizare.lei_din_bani(rata_bani)),
            dae=float(amortizare.dae(principal_bani, rata_bani, luni)),
            grafic=grafic,
            semnatura=semnatura,
        ))

    # -- credite si rate ----------------------------------------------------

    async def credite(self, user_id: UUID, pana_la: date | None = None) -> list[dict]:
        credite = await self._depozit.credite_utilizator(user_id)
        for credit in credite:
            if credit["status"] in ("activ", "restant"):
                await self._depozit.incaseaza_rate(UUID(credit["id"]), pana_la)
        return await self._depozit.credite_utilizator(user_id)

    async def detaliu(self, id_credit: UUID, user_id: UUID, pana_la: date | None = None) -> dict:
        credit = await self._credit_propriu(id_credit, user_id)
        if credit["status"] in ("activ", "restant"):
            await self._depozit.incaseaza_rate(id_credit, pana_la)
            credit = await self._depozit.credit(id_credit)

        rate = await self._depozit.rate(id_credit)
        urmatoarea = next((r for r in rate if r["status"] in ("programata", "restanta")), None)
        return {
            "credit": credit,
            "rate": rate,
            "urmatoarea_rata": urmatoarea,
            "rate_platite": sum(1 for r in rate if r["status"] == "platita"),
        }

    async def avanseaza_timp(self, id_credit: UUID, user_id: UUID, luni: int) -> dict:
        """Procesare pana la o data din viitor, pentru verificarea fluxului.

        Nu ocoleste nimic: cheama acelasi `credit_incaseaza_rate` ca procesarea
        obisnuita, doar cu alta limita de scadenta. Fara asta, ca sa vezi a doua
        rata incasata ar trebui sa astepti o luna.
        """
        await self._credit_propriu(id_credit, user_id)
        return await self.detaliu(id_credit, user_id, pana_la=aduna_luni(date.today(), luni))

    # -- rambursare anticipata ---------------------------------------------

    async def calcul_rambursare(self, id_credit: UUID, user_id: UUID) -> dict:
        credit = await self._credit_propriu(id_credit, user_id)
        if credit["status"] in ("inchis", "rambursat_anticipat"):
            raise OperatiuneRefuzata("Creditul e deja stins.")

        rate = await self._depozit.rate(id_credit)
        platite = sum(1 for r in rate if r["status"] == "platita")
        grafic = _grafic_din_randuri(rate)
        zile = _zile_de_la_ultima_scadenta(rate)

        cost = amortizare.cost_rambursare_anticipata(
            grafic, platite, zile, Decimal(str(credit["dobanda_anuala"]))
        )
        return {
            "sold": amortizare.lei_din_bani(cost.sold_bani),
            "dobanda_acumulata": amortizare.lei_din_bani(cost.dobanda_acumulata_bani),
            "total_de_plata": amortizare.lei_din_bani(cost.total_bani),
            "economie_dobanda": amortizare.lei_din_bani(cost.economie_dobanda_bani),
            "zile_de_la_ultima_scadenta": zile,
        }

    async def ramburseaza(
        self, id_credit: UUID, user_id: UUID, suma: Decimal | None = None
    ) -> dict:
        """`suma` None inseamna stingere integrala."""
        credit = await self._credit_propriu(id_credit, user_id)
        calcul = await self.calcul_rambursare(id_credit, user_id)

        sold = Decimal(str(credit["sold_ramas"]))
        principal = sold if suma is None else min(suma, sold)
        integral = principal >= sold

        grafic_nou = None
        if not integral:
            # Soldul scade, perioada ramane: se recalculeaza rata pe ce a mai
            # ramas de plata, cu aceeasi scadenta finala.
            rate = await self._depozit.rate(id_credit)
            ramase = [r for r in rate if r["status"] in ("programata", "restanta")]
            sold_nou_bani = amortizare.bani_din_lei(sold - principal)
            grafic_nou = _grafic_cu_scadente(
                amortizare.genereaza_grafic(
                    sold_nou_bani, Decimal(str(credit["dobanda_anuala"])), len(ramase)
                ),
                date.today(),
                numar_start=int(ramase[0]["numar_rata"]),
            )

        return await _rpc(self._depozit.ramburseaza_anticipat(
            id_credit=id_credit,
            principal_platit=float(principal),
            dobanda_acumulata=float(calcul["dobanda_acumulata"]),
            grafic_nou=grafic_nou,
        ))

    # -- ajutoare -----------------------------------------------------------

    async def _produs(self, slug: str) -> dict:
        produs = await self._depozit.produs(slug)
        if not produs:
            raise CreditNegasit(f"Produsul '{slug}' nu exista sau nu e activ.")
        return produs

    async def _produs_dupa_id(self, id_produs: str) -> dict:
        # Un singur produs activ deocamdata; cand apar mai multe, se cauta dupa id.
        produs = await self._depozit.produs(PRODUS_IMPLICIT)
        if not produs or produs["id"] != id_produs:
            raise CreditNegasit("Produsul cererii nu mai e disponibil.")
        return produs

    async def _cerere_proprie(self, id_cerere: UUID, user_id: UUID) -> dict:
        cerere = await self._depozit.cerere(id_cerere)
        if not cerere or cerere["id_user"] != str(user_id):
            raise CreditNegasit("Cererea nu exista.")
        return cerere

    async def _credit_propriu(self, id_credit: UUID, user_id: UUID) -> dict:
        credit = await self._depozit.credit(id_credit)
        if not credit or credit["id_user"] != str(user_id):
            raise CreditNegasit("Creditul nu exista.")
        return credit


# ---------------------------------------------------------------------------
# Functii de sprijin, pure
# ---------------------------------------------------------------------------


def aduna_luni(start: date, luni: int) -> date:
    """Aceeasi zi peste N luni, taiata la ultima zi a lunii cand nu exista.

    31 ianuarie + 1 luna da 28 (sau 29) februarie, nu 3 martie — asa functioneaza
    scadentele reale.
    """
    an, luna_bruta = divmod(start.month - 1 + luni, 12)
    an, luna = start.year + an, luna_bruta + 1
    return date(an, luna, min(start.day, calendar.monthrange(an, luna)[1]))


def _grafic_cu_scadente(
    grafic: list[amortizare.RataProgramata], de_la: date, numar_start: int = 1
) -> list[dict]:
    """Graficul, in forma pe care o asteapta RPC-ul: sume in lei, scadente reale.

    Prima scadenta e la o luna dupa acordare — creditul nu se ramburseaza in ziua
    in care se acorda.
    """
    return [
        {
            "numar": numar_start + indice,
            "scadenta": aduna_luni(de_la, indice + 1).isoformat(),
            "principal": str(amortizare.lei_din_bani(rata.principal_bani)),
            "dobanda": str(amortizare.lei_din_bani(rata.dobanda_bani)),
            "total": str(amortizare.lei_din_bani(rata.total_bani)),
            "sold_dupa": str(amortizare.lei_din_bani(rata.sold_dupa_bani)),
        }
        for indice, rata in enumerate(grafic)
    ]


def _grafic_din_randuri(rate: list[dict]) -> list[amortizare.RataProgramata]:
    """Randurile din credit_rate, inapoi in forma cu care lucreaza amortizare.py."""
    return [
        amortizare.RataProgramata(
            numar=int(rand["numar_rata"]),
            principal_bani=amortizare.bani_din_lei(rand["principal_rata"]),
            dobanda_bani=amortizare.bani_din_lei(rand["dobanda_rata"]),
            total_bani=amortizare.bani_din_lei(rand["rata_totala"]),
            sold_dupa_bani=amortizare.bani_din_lei(rand["sold_dupa"]),
        )
        for rand in rate
        if rand["status"] != "anulata"
    ]


def _zile_de_la_ultima_scadenta(rate: list[dict]) -> int:
    platite = [r for r in rate if r["status"] == "platita"]
    if not platite:
        return 0
    ultima = max(date.fromisoformat(r["scadenta"]) for r in platite)
    return max((date.today() - ultima).days, 0)


def _luni_de_la(moment_iso: str) -> int:
    inceput = datetime.fromisoformat(str(moment_iso).replace("Z", "+00:00"))
    return max(int((datetime.now(timezone.utc) - inceput).days / 30.44), 0)


def _produs_domeniu(produs: dict) -> reguli.Produs:
    return reguli.Produs(
        slug=produs["slug"],
        nume=produs["nume"],
        dobanda_anuala=Decimal(str(produs["dobanda_anuala"])),
        suma_min=Decimal(str(produs["suma_min"])),
        suma_max=Decimal(str(produs["suma_max"])),
        luni_min=int(produs["luni_min"]),
        luni_max=int(produs["luni_max"]),
        varsta_min=int(produs["varsta_min"]),
        varsta_max=int(produs["varsta_max"]),
        venit_net_minim=Decimal(str(produs["venit_net_minim"])),
        vechime_angajator_luni=int(produs["vechime_angajator_luni"]),
        vechime_venituri_luni=int(produs["vechime_venituri_luni"]),
    )


async def _cu_explicatie(decizie: Decizie, explica) -> Decizie:
    """Textul pentru client. Modelul de limbaj e optional, textul nu e.

    `explica(decizie, text_determinist)` e o corutina care primeste si textul
    deja calculat: nu genereaza o explicatie de la zero, o rescrie mai cald — un
    esec sau `None` lasa exact textul determinist, neschimbat.
    """
    from dataclasses import replace

    from app.services.credit_explicatie import explicatie_determinista

    text = explicatie_determinista(
        decizie.decizie, decizie.motive, decizie.factori, decizie.scor, decizie.cere_document
    )
    if explica is not None:
        try:
            text = await explica(decizie, text) or text
        except Exception:
            logger.exception("explicatia prin model a esuat; raman pe textul determinist")
    return replace(decizie, explicatie=text)


async def _rpc(apel):
    """Traduce refuzurile din plpgsql in erori de aplicatie.

    Functiile din 0010 ridica exceptii cu coduri vorbitoare (FONDURI_INSUFICIENTE,
    OFERTA_EXPIRATA, GRAFIC_INVALID). supabase-py le aduce ca APIError; fara
    traducerea asta ar iesi la client ca 500, desi sunt situatii previzibile.
    """
    try:
        return await apel
    except Exception as eroare:
        detaliu = getattr(eroare, "message", None) or str(eroare)
        logger.warning("rpc credit refuzat: %s", detaliu)
        raise OperatiuneEsuata(detaliu) from None


def _explicatie_manuala(aprobat: bool, nota: str, scor: int | None) -> str:
    """Textul care inlocuieste motivarea automata dupa decizia unui om.

    Scorul ramane in text: clientul aprobat la limita merita sa stie ca a fost
    la limita, nu sa creada ca dosarul lui era fara probleme.
    """
    parti = []
    if aprobat:
        parti.append("Cererea ta a fost aprobată după analiza unui coleg de la creditare.")
    else:
        parti.append("După analiza unui coleg de la creditare, nu putem aproba cererea.")

    if scor is not None:
        parti.append(f"Punctajul automat a fost {scor} din 100, în zona care cere decizie umană.")
    if nota:
        parti.append(nota)

    parti.append(
        "Oferta e valabilă 7 zile — o poți accepta din aplicație."
        if aprobat
        else "Poți relua cererea cu o sumă mai mică sau o perioadă mai lungă."
    )
    return "\n\n".join(parti)
