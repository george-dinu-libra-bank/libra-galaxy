"""Detectia platilor neregulate.

Doua straturi, deliberat:

1. Baza statistica — functioneaza din prima zi, fara antrenare, si e explicabila
   utilizatorului ("de obicei platesti 40 RON aici, acum 380").
2. Model antrenat (`model.joblib`, IsolationForest) — prinde combinatii pe care o
   regula simpla nu le vede. Daca artefactul lipseste, stratul 1 ramane singur.

Detectorul nu trimite nimic nicaieri: intoarce constatari. Ce devine alerta si ce
se arata utilizatorului decide `AlerteService`.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.ml.caracteristici import (
    Plata,
    deviatie_absoluta_mediana,
    mediana,
    vector,
)

logger = logging.getLogger(__name__)

CALE_MODEL = Path(__file__).with_name("model.joblib")

# Sub atatea plati la un comerciant nu avem de unde sti ce inseamna "normal".
MIN_ISTORIC = 4
# Scor robust peste care suma iese din tipar. 3.5 e pragul uzual pentru MAD.
PRAG_SCOR = 3.5
# O suma sub asta nu merita o alerta, oricat de atipica ar fi.
PRAG_SUMA_MINIMA = 50.0
# Prima plata la un comerciant nou e normala. Devine interesanta doar cand e si
# mare in cifre absolute, si mult peste ce cheltuie de obicei utilizatorul.
PRAG_COMERCIANT_NOU_SUMA = 300.0
PRAG_COMERCIANT_NOU_MULTIPLU = 5.0
# Doua plati identice la acelasi comerciant in acest interval arata a dubla debitare.
FEREASTRA_DUBLARE = timedelta(minutes=15)
# Atatea plati la acelasi comerciant intr-o zi ies din ritmul obisnuit, chiar
# daca fiecare suma in parte e normala si nu sunt identice intre ele.
FEREASTRA_RAFALA = timedelta(hours=24)
PRAG_RAFALA = 4
# decision_function al IsolationForest sta aproximativ in [-0.5, 0.5]. Inmultit cu
# atat, o constatare de model ajunge intre PRAG_SCOR si ~8.5 — deci sub cele 10 ale
# unei dublari confirmate: o certitudine aritmetica trebuie sa bata o banuiala.
SCALA_MODEL = 10.0


@lru_cache(maxsize=1)
def incarca_model() -> Any | None:
    """Artefactul, citit o singura data per proces.

    Fara cache s-ar reciti la fiecare cerere: sunt cateva sute de milisecunde
    pentru un fisier de cativa MB, platite degeaba. Modelul e doar citit la
    inferenta, deci poate fi impartit intre cereri.

    Consecinta: dupa o reantrenare, procesul trebuie repornit ca sa vada noul
    artefact. Pentru un artefact regenerat manual, e schimbul corect.
    """
    if not CALE_MODEL.exists():
        logger.info("model.joblib lipseste; folosesc doar baza statistica")
        return None
    try:
        import joblib

        return joblib.load(CALE_MODEL)
    except Exception:
        logger.exception("model.joblib nu a putut fi incarcat; raman pe baza statistica")
        return None



# -----------------------------------------------------------------------------
# Severitatea, pe o scara de la 1 la 100
#
# Scorurile brute ale verificarilor nu sunt comparabile intre ele: o dublare
# confirmata primea 10, iar o suma atipica putea trece de 70, fiindca z-scorul
# modificat nu are limita superioara. Rezultatul: o certitudine aritmetica
# aparea SUB o banuiala statistica, exact invers fata de intentia scrisa mai sus
# ("o certitudine aritmetica trebuie sa bata o banuiala").
#
# Fiecare tip primeste o banda dupa cat de sigura e constatarea, iar scorul brut
# decide unde anume in banda. Asa ordinea intre tipuri e garantata de banda, si
# ordinea in interiorul unui tip ramane data de date.
#
# Severitatea NU e o probabilitate de frauda: sistemul nu a vazut niciodata o
# frauda confirmata din care sa invete. E o ordine de prioritate.
# -----------------------------------------------------------------------------

# tip -> (jos, sus, referinta)
# `referinta` e valoarea bruta la care constatarea ajunge cam la doua treimi din
# banda; peste ea creste tot mai incet, deci un z-score urias nu striveste
# restul listei.
BENZI_SEVERITATE: dict[str, tuple[int, int, float]] = {
    # Doua plati identice la acelasi comerciant in cateva minute. Nu e o
    # chestiune de grad: ori s-a intamplat, ori nu.
    "plata_dublata": (95, 95, 1.0),
    # Ritmul e masurabil si greu de confundat, dar nu e o certitudine.
    "rafala_de_plati": (72, 88, 8.0),
    # Prima plata la un comerciant, mult peste obisnuit.
    "comerciant_nou": (45, 90, 12.0),
    # Cat de departe e suma de mediana, in abateri absolute mediane.
    "suma_neobisnuita": (45, 90, 20.0),
    # Banuiala modelului: cea mai slaba dovada, deci cea mai joasa banda.
    "tipar_neobisnuit": (20, 60, 6.0),
}

SEVERITATE_IMPLICITA = (30, 70, 10.0)


def severitate(tip: str, brut: float) -> int:
    """Scorul brut al unei verificari, adus pe scara 1-100.

    Saturatie exponentiala in interiorul benzii: creste repede la inceput, unde
    diferentele chiar conteaza, si tot mai incet spre capat, ca o valoare
    extrema sa nu faca restul constatarilor sa para neinsemnate.
    """
    import math

    jos, sus, referinta = BENZI_SEVERITATE.get(tip, SEVERITATE_IMPLICITA)
    if jos == sus:
        return jos

    proportie = 1.0 - math.exp(-max(brut, 0.0) / referinta)
    return max(1, min(100, round(jos + (sus - jos) * proportie)))


@dataclass(frozen=True, slots=True)
class Neregularitate:
    id_tranzactie: str
    data: str
    suma: float
    valuta: str
    comerciant: str
    tip: str
    explicatie: str
    # Severitate 1-100, nu scorul brut al verificarii: vezi BENZI_SEVERITATE.
    scor: int


@dataclass
class DetectorNeregularitati:
    model: Any | None = None
    _cache_grup: dict[str, list[Plata]] = field(default_factory=dict, init=False)

    @classmethod
    def cu_model_de_pe_disc(cls) -> "DetectorNeregularitati":
        return cls(model=incarca_model())

    def evalueaza(self, plati: list[Plata]) -> list[Neregularitate]:
        iesiri = [p for p in plati if p.iesire]
        if not iesiri:
            return []

        grupuri: dict[str, list[Plata]] = {}
        for plata in iesiri:
            grupuri.setdefault(plata.comerciant, []).append(plata)

        constatari: list[Neregularitate] = []
        for plata in iesiri:
            istoric = [p for p in grupuri[plata.comerciant] if p.moment < plata.moment]

            constatare = (
                self._dubla_debitare(plata, istoric)
                or self._rafala(plata, istoric)
                or self._suma_atipica(plata, istoric)
                or self._comerciant_nou(plata, istoric, iesiri)
                or self._dupa_model(plata, istoric, iesiri)
            )
            if constatare:
                constatari.append(constatare)

        constatari.sort(key=lambda c: c.scor, reverse=True)
        return constatari

    def _dubla_debitare(self, plata: Plata, istoric: list[Plata]) -> Neregularitate | None:
        for anterioara in reversed(istoric):
            if plata.moment - anterioara.moment > FEREASTRA_DUBLARE:
                break
            if abs(anterioara.suma - plata.suma) < 0.01:
                return self._constatare(
                    plata,
                    "plata_dublata",
                    f"Aceeasi suma platita de doua ori la {plata.comerciant} "
                    f"in mai putin de {int(FEREASTRA_DUBLARE.total_seconds() // 60)} minute.",
                    10.0,
                )
        return None

    def _rafala(self, plata: Plata, istoric: list[Plata]) -> Neregularitate | None:
        """Mai multe plati la acelasi comerciant intr-o singura zi.

        Sumele pot fi toate obisnuite si diferite intre ele, deci nici
        _dubla_debitare, nici _suma_atipica nu au ce prinde: anormal e ritmul.
        Regula, nu model, pentru ca aici avem ce numara — iar un numar se poate
        spune omului ("patru plati intr-o zi"), spre deosebire de un scor.
        """
        in_fereastra = [
            p for p in istoric if plata.moment - p.moment <= FEREASTRA_RAFALA
        ]
        cate = len(in_fereastra) + 1
        if cate < PRAG_RAFALA:
            return None

        return self._constatare(
            plata,
            "rafala_de_plati",
            f"{cate} plati la {plata.comerciant} in mai putin de 24 de ore. "
            "Verifica daca le-ai facut pe toate.",
            8.0,
        )

    def _suma_atipica(self, plata: Plata, istoric: list[Plata]) -> Neregularitate | None:
        if len(istoric) < MIN_ISTORIC or plata.suma < PRAG_SUMA_MINIMA:
            return None

        sume = [p.suma for p in istoric]
        med = mediana(sume)
        imprastiere = deviatie_absoluta_mediana(sume)
        if imprastiere == 0:
            # Toate platile anterioare au fost identice; orice abatere conteaza.
            if abs(plata.suma - med) < 0.01:
                return None
            scor = PRAG_SCOR + 1
        else:
            scor = 0.6745 * abs(plata.suma - med) / imprastiere

        if scor < PRAG_SCOR or plata.suma <= med:
            return None

        return self._constatare(
            plata,
            "suma_neobisnuita",
            f"De obicei platesti in jur de {med:.2f} {plata.valuta} la {plata.comerciant}, "
            f"acum {plata.suma:.2f}.",
            scor,
        )

    def _comerciant_nou(
        self, plata: Plata, istoric: list[Plata], toate: list[Plata]
    ) -> Neregularitate | None:
        if istoric or plata.suma < PRAG_COMERCIANT_NOU_SUMA:
            return None

        sume = [p.suma for p in toate if p.moment < plata.moment]
        if len(sume) < MIN_ISTORIC:
            return None

        tipic = mediana(sume)
        if tipic <= 0 or plata.suma < tipic * PRAG_COMERCIANT_NOU_MULTIPLU:
            return None

        return self._constatare(
            plata,
            "comerciant_nou",
            f"Prima plata la {plata.comerciant}, si e de {plata.suma / tipic:.1f} ori "
            "mai mare decat o plata obisnuita a ta.",
            plata.suma / tipic,
        )

    def _dupa_model(
        self, plata: Plata, istoric: list[Plata], iesiri: list[Plata]
    ) -> Neregularitate | None:
        if self.model is None:
            return None

        # Prima plata la un comerciant nu are cu ce fi comparata: trasaturile
        # care o descriu sunt toate valori de asteptare ("nu exista anterioara"),
        # iar modelul le-ar citi ca pe niste numere neobisnuite si ar semnala
        # fiecare inceput de relatie. Cazul are deja regula lui, _comerciant_nou.
        if not istoric:
            return None

        trasaturi = [vector(plata, istoric, iesiri)]
        try:
            if self.model.predict(trasaturi)[0] != -1:
                return None
            brut = float(self.model.decision_function(trasaturi)[0])
        except Exception:
            logger.exception("modelul a esuat la inferenta; ignor constatarea")
            return None

        return self._constatare(
            plata,
            "tipar_neobisnuit",
            f"Plata de {plata.suma:.2f} {plata.valuta} catre {plata.comerciant} nu seamana "
            "cu tiparul tau obisnuit de cheltuieli.",
            PRAG_SCOR + abs(min(brut, 0.0)) * SCALA_MODEL,
        )

    @staticmethod
    def _constatare(plata: Plata, tip: str, explicatie: str, scor: float) -> Neregularitate:
        """`scor` intra brut si iese ca severitate 1-100 (vezi BENZI_SEVERITATE).

        Filtrarea pe PRAG_SCOR ramane pe valoarea bruta, in verificari: ce se
        raporteaza nu se schimba, doar cum se exprima gravitatea.
        """
        return Neregularitate(
            id_tranzactie=plata.id,
            data=plata.moment.date().isoformat(),
            suma=round(plata.suma, 2),
            valuta=plata.valuta,
            comerciant=plata.comerciant,
            tip=tip,
            explicatie=explicatie,
            scor=severitate(tip, scor),
        )


@dataclass(frozen=True, slots=True)
class StareModel:
    """Daca al doilea strat de detectie chiar ruleaza, si de cand.

    Exista fiindca lipsa artefactului e tacuta prin proiectare: detectia merge
    mai departe pe reguli statistice, iar cine se uita la ecran vede o lista
    plauzibila fara niciun semn ca jumatate din sistem lipseste. Un
    administrator care ia decizii pe baza listei are dreptul sa stie pe ce se
    uita.
    """

    activ: bool
    antrenat_la: str | None
    marime_kb: int | None

    @property
    def explicatie(self) -> str:
        if self.activ:
            return "Detectia ruleaza pe reguli statistice si pe model."
        return (
            "Modelul lipseste: detectia ruleaza doar pe reguli statistice. "
            "Tiparele invatate nu sunt verificate."
        )


def stare_model() -> StareModel:
    """Starea artefactului, citita de pe disc la fiecare apel.

    Deliberat fara cache, spre deosebire de incarca_model(): e o interogare
    rara, iar un raspuns care spune "modelul e activ" dupa ce fisierul a fost
    sters ar fi mai rau decat cei cativa milisecunzi economisiti.
    """
    if not CALE_MODEL.exists():
        return StareModel(activ=False, antrenat_la=None, marime_kb=None)

    info = CALE_MODEL.stat()
    return StareModel(
        activ=incarca_model() is not None,
        antrenat_la=datetime.fromtimestamp(info.st_mtime, tz=timezone.utc).isoformat(),
        marime_kb=round(info.st_size / 1024),
    )
