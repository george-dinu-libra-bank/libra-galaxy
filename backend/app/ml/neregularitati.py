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
from datetime import timedelta
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


@dataclass(frozen=True, slots=True)
class Neregularitate:
    id_tranzactie: str
    data: str
    suma: float
    valuta: str
    comerciant: str
    tip: str
    explicatie: str
    scor: float


@dataclass
class DetectorNeregularitati:
    model: Any | None = None
    _cache_grup: dict[str, list[Plata]] = field(default_factory=dict, init=False)

    @classmethod
    def cu_model_de_pe_disc(cls) -> "DetectorNeregularitati":
        if not CALE_MODEL.exists():
            logger.info("model.joblib lipseste; folosesc doar baza statistica")
            return cls(model=None)
        try:
            import joblib

            return cls(model=joblib.load(CALE_MODEL))
        except Exception:
            logger.exception("model.joblib nu a putut fi incarcat; raman pe baza statistica")
            return cls(model=None)

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
                or self._suma_atipica(plata, istoric)
                or self._comerciant_nou(plata, istoric, iesiri)
                or self._dupa_model(plata, grupuri[plata.comerciant])
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

    def _dupa_model(self, plata: Plata, grup: list[Plata]) -> Neregularitate | None:
        if self.model is None:
            return None
        try:
            predictie = self.model.predict([vector(plata, grup)])
        except Exception:
            logger.exception("modelul a esuat la inferenta; ignor constatarea")
            return None

        if predictie[0] != -1:
            return None

        return self._constatare(
            plata,
            "tipar_neobisnuit",
            f"Plata de {plata.suma:.2f} {plata.valuta} catre {plata.comerciant} nu seamana "
            "cu tiparul tau obisnuit de cheltuieli.",
            PRAG_SCOR,
        )

    @staticmethod
    def _constatare(plata: Plata, tip: str, explicatie: str, scor: float) -> Neregularitate:
        return Neregularitate(
            id_tranzactie=plata.id,
            data=plata.moment.date().isoformat(),
            suma=round(plata.suma, 2),
            valuta=plata.valuta,
            comerciant=plata.comerciant,
            tip=tip,
            explicatie=explicatie,
            scor=round(scor, 2),
        )
