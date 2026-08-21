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

import calendar
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.core.errors import ResourceNotFoundError, ValidationError
from app.credit import amortizare, reguli, scorecard
from app.credit.venit import VenitConstatat, detecteaza_venit
from app.ml.caracteristici import normalizeaza
from app.ml.neregularitati import DetectorNeregularitati
from app.repositories.credit_repository import CreditRepository

logger = logging.getLogger(__name__)

PRODUS_IMPLICIT = "galaxy-flex-personal"
ZILE_VALABILITATE_OFERTA = 7
# Cat de mult crede banca o adeverinta fata de incasari vazute in cont: un
# document poate fi si eronat, si falsificat, dar e verificabil — deci intre
# declaratie (0) si tranzactii (pana la 1).
INCREDERE_ADEVERINTA = 0.6
# Fereastra pe care se numara platile atipice pentru factorul de comportament.
ZILE_ISTORIC_COMPORTAMENT = 180


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
        # Injectat ca sa poata fi inlocuit la test si ca serviciul sa nu depinda
        # de disponibilitatea unui model de limbaj.
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

    async def evalueaza(self, id_cerere: UUID, user_id: UUID) -> Decizie:
        """Ruleaza tot lantul: verificari de venit, criterii hard, scorecard.

        Se poate reevalua o cerere ramasa in 'ciorna' sau 'in_analiza'. O cerere
        care are deja oferta sau a fost acceptata nu se mai reevalueaza: oferta e
        un angajament, nu o parere.
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

        decizie = Decizie(
            decizie=scor.decizie, scor=scor.total, dti=dti, motive=[],
            factori=[{"cod": f.cod, "puncte": f.puncte, "maxim": f.maxim, "explicatie": f.explicatie}
                     for f in scor.factori],
            explicatie="",
            rata_lunara=rata_lunara if scor.aprobat else None,
            dae=amortizare.dae(principal_bani, rata_bani, luni) if scor.aprobat else None,
            oferta_expira_la=(datetime.now(timezone.utc) + timedelta(days=ZILE_VALABILITATE_OFERTA))
            if scor.aprobat else None,
        )
        return await self._finalizeaza(cerere, decizie, venit, obligatii)

    async def _finalizeaza(
        self, cerere: dict, decizie: Decizie, venit: Decimal, obligatii: Decimal
    ) -> Decizie:
        decizie = _cu_explicatie(decizie, self._explica)
        status = {"aprobat": "oferta", "analiza_manuala": "analiza_manuala", "respins": "respinsa"}[
            decizie.decizie
        ]

        await self._depozit.actualizeaza_cerere(UUID(cerere["id"]), {
            "status": status,
            "venit_folosit": str(venit),
            "obligatii_folosite": str(obligatii),
            "dti": str(decizie.dti) if decizie.dti is not None else None,
            "scor": decizie.scor,
            "motive": decizie.motive or decizie.factori,
            "explicatie": decizie.explicatie,
            "rata_lunara": str(decizie.rata_lunara) if decizie.rata_lunara else None,
            "dae": str(decizie.dae) if decizie.dae else None,
            "oferta_expira_la": decizie.oferta_expira_la.isoformat() if decizie.oferta_expira_la else None,
        })

        await self._depozit.eveniment({
            "id_cerere": cerere["id"], "tip": f"decizie_{decizie.decizie}", "actor": "sistem",
            "detalii": {"scor": decizie.scor, "dti": str(decizie.dti) if decizie.dti else None},
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
        """Venitul extras dintr-o adeverinta incarcata, daca exista una procesata."""
        for verificare in await self._depozit.verificari(id_cerere):
            if verificare["sursa"] == "adeverinta" and verificare["venit_constatat"]:
                return Decimal(str(verificare["venit_constatat"]))
        return None

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

    async def cereri_in_analiza(self) -> list[dict]:
        return await self._depozit.cereri_in_analiza()

    async def decide_manual(
        self, id_cerere: UUID, id_admin: UUID, aproba: bool, nota: str | None = None
    ) -> dict:
        """Decizia unui om peste o cerere din zona gri.

        Scorul si factorii NU se recalculeaza si nu se sterg: raman exact cum
        i-a produs motorul. Un dosar aprobat manual trebuie sa arate ulterior si
        ca a fost la limita, si cine a decis altfel — altfel auditul nu poate
        distinge o aprobare automata de una omeneasca.

        Administratorul nu poate atinge o cerere care nu e in analiza manuala:
        nu are ce cauta peste un refuz pe criterii hard (acolo decizia nu e
        discretionara) si nici peste o oferta deja emisa.
        """
        cerere = await self._depozit.cerere(id_cerere)
        if not cerere:
            raise CreditNegasit("Cererea nu exista.")
        if cerere["status"] != "analiza_manuala":
            raise OperatiuneRefuzata(
                f"Doar o cerere in analiza manuala poate fi decisa de un administrator; "
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

        await self._depozit.eveniment({
            "id_cerere": str(id_cerere),
            "tip": "decizie_manuala_aprobat" if aproba else "decizie_manuala_respins",
            "actor": "administrator",
            "id_actor": str(id_admin),
            "detalii": {"nota": motivare or None, "scor_automat": cerere.get("scor")},
        })
        return actualizata

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


def _cu_explicatie(decizie: Decizie, explica) -> Decizie:
    """Textul pentru client. Modelul de limbaj e optional, textul nu e."""
    from dataclasses import replace

    from app.services.credit_explicatie import explicatie_determinista

    text = explicatie_determinista(decizie.decizie, decizie.motive, decizie.factori, decizie.scor)
    if explica is not None:
        try:
            text = explica(decizie) or text
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
