"""Azure AI Document Intelligence (REST) — OCR pe documente incarcate.

A treia resursa Azure a proiectului, separata de Foundry (chat/embeddings) si de
Speech. REST direct cu cheia de subscriptie, nu SDK-ul `azure-ai-documentintelligence`
— acelasi motiv ca la `providers/voice.py`: nu adaugam un SDK cu dependintele lui
pentru un serviciu optional, cand schimbul e un POST si un GET.

**Se citeste `pages[].lines[]`, nu `analyzeResult.content`.**

Cele doua nu sunt acelasi text. `content` e varianta aplatizata: Azure lipeste
randuri consecutive cand le considera acelasi paragraf. Pe o adeverinta, asta
aduce brutul si netul pe aceeasi linie:

    Salariul brut lunar: 14.500,00 lei Salariul net lunar: 8.700,00 lei

iar `credit/adeverinta.py` arunca linia intreaga cand vede "brut" — regula lui e
scrisa pentru randuri de pe hartie, unde o linie inseamna o eticheta. Din `content`,
venitul iesea `None` pe un document pe care Azure il citise perfect: OCR mai bun,
rezultat mai prost, si niciun mesaj de eroare pe undeva.

`lines[]` pastreaza randurile asa cum stau pe hartie, deci parserul primeste exact
forma pentru care a fost scris si nu trebuie atins. Verificat pe adeverinta de test:
prin `lines[]` da acelasi 8700.00 / incredere 0.893 ca drumul prin pypdf.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx

from app.core.config import Settings
from app.core.errors import AiProviderError, AiProviderUnavailableError

logger = logging.getLogger(__name__)

# Versiunea GA a lui Document Intelligence v4.0. Verificata live pe resursa
# proiectului inainte de a scrie clientul.
API_VERSION = "2024-11-30"

# Cat asteptam un raspuns. O adeverinta de o pagina se termina in 1-3 secunde
# (masurat: 1s); limita e pentru cazul in care operatia se blocheaza, ca sa nu
# tinem o cerere HTTP agatata la nesfarsit.
SECUNDE_INTRE_INTEROGARI = 1.0
INTEROGARI_MAXIME = 30

# Pentru documentele fara structura de citit — un buletin, de exemplu, din care
# ne trebuie doar cifrele CNP-ului si increderea pe ele. "prebuilt-read" costa
# 1,50 $/1000 pagini fata de 10 $ la "layout", iar un buletin n-are coloane pe
# care sa le pierdem. Adeverintele raman pe modelul din config.
MODEL_DOAR_TEXT = "prebuilt-read"


@dataclass(frozen=True, slots=True)
class Cuvant:
    """Un cuvant citit, cu increderea raportata de Azure (0..1)."""

    text: str
    incredere: float


@dataclass(frozen=True, slots=True)
class TextCitit:
    text: str
    cuvinte: tuple[Cuvant, ...]
    # Tabelele, ca grile dense de siruri (primul rand e antetul, cand exista).
    # Sirurile, nu obiectele Azure: interpretarea lor se face in `credit/`, care
    # nu are voie sa stie ca exista un furnizor de OCR.
    tabele: tuple[tuple[tuple[str, ...], ...], ...] = ()


class AzureDocumentIntelligence:
    def __init__(self, settings: Settings) -> None:
        if not settings.document_intelligence_configured:
            raise AiProviderUnavailableError("Azure Document Intelligence nu este configurat.")

        # `rstrip` fiindca endpoint-ul copiat din portal vine adesea cu "/" la
        # coada, iar noi lipim mereu o cale care incepe cu "/".
        self._endpoint = settings.di_endpoint.rstrip("/")
        self._key = settings.di_key
        self._model = settings.di_model

    @property
    def _antet(self) -> dict[str, str]:
        return {"Ocp-Apim-Subscription-Key": self._key}

    async def citeste(
        self, continut: bytes, content_type: str, model: str | None = None
    ) -> TextCitit:
        """Textul dintr-un fisier (PDF sau poza).

        `model` suprascrie modelul din config pentru un singur apel — vezi
        MODEL_DOAR_TEXT, pentru documentele din care nu avem ce structura sa
        citim si n-are rost sa platim de sapte ori mai mult.

        Se trimit octetii bruti cu `Content-Type`-ul real, nu `base64Source`:
        base64 ar umfla cu 33% un fisier de cativa MB, degeaba.
        """
        url = (
            f"{self._endpoint}/documentintelligence/documentModels"
            f"/{model or self._model}:analyze?api-version={API_VERSION}"
        )

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                pornire = await client.post(
                    url,
                    headers={**self._antet, "Content-Type": content_type},
                    content=continut,
                )
            except httpx.HTTPError as exc:
                raise AiProviderUnavailableError("Azure Document Intelligence este inaccesibil.") from exc

            if pornire.status_code != 202:
                raise AiProviderError(
                    f"Azure Document Intelligence a raspuns cu status {pornire.status_code} la analyze."
                )

            locatie = pornire.headers.get("operation-location")
            if not locatie:
                raise AiProviderError("Azure Document Intelligence n-a intors Operation-Location.")

            rezultat = await self._asteapta(client, locatie)

        return _din_raspuns(rezultat)

    async def _asteapta(self, client: httpx.AsyncClient, locatie: str) -> dict:
        """Interogheaza operatia pana se termina. Analiza e asincrona la Azure."""
        for _ in range(INTEROGARI_MAXIME):
            await asyncio.sleep(SECUNDE_INTRE_INTEROGARI)

            try:
                raspuns = await client.get(locatie, headers=self._antet)
            except httpx.HTTPError as exc:
                raise AiProviderUnavailableError("Azure Document Intelligence este inaccesibil.") from exc

            if raspuns.status_code != 200:
                raise AiProviderError(
                    f"Azure Document Intelligence a raspuns cu status {raspuns.status_code} la interogare."
                )

            date = raspuns.json()
            stare = date.get("status")

            if stare == "succeeded":
                return date
            if stare == "failed":
                # Motivul lui Azure ajunge in log, nu la utilizator: poate contine
                # bucati din document.
                logger.warning("document_intelligence: analiza esuata (%s)", date.get("error"))
                raise AiProviderError("Azure Document Intelligence n-a putut analiza documentul.")

        raise AiProviderUnavailableError(
            f"Azure Document Intelligence n-a terminat in {INTEROGARI_MAXIME} secunde."
        )


def _din_raspuns(date: dict) -> TextCitit:
    """Randurile si cuvintele din raspunsul brut.

    Functie libera, ca sa se poata testa pe un JSON salvat, fara retea si fara
    chei — vezi tests/fixturi.
    """
    analiza = date.get("analyzeResult") or {}
    pagini = analiza.get("pages") or []

    randuri: list[str] = []
    cuvinte: list[Cuvant] = []

    for pagina in pagini:
        for linie in pagina.get("lines") or []:
            continut = (linie.get("content") or "").strip()
            if continut:
                randuri.append(continut)

        for cuvant in pagina.get("words") or []:
            text = cuvant.get("content") or ""
            if text:
                cuvinte.append(Cuvant(text, float(cuvant.get("confidence") or 0.0)))

    # Rezerva pentru un model care ar intoarce text fara `lines` (nu e cazul lui
    # prebuilt-layout, dar `content` e singurul camp garantat de schema).
    text = "\n".join(randuri) or (analiza.get("content") or "")

    return TextCitit(text=text, cuvinte=tuple(cuvinte), tabele=_tabele(analiza))


def _tabele(analiza: dict) -> tuple[tuple[tuple[str, ...], ...], ...]:
    """Tabelele, ca grile dense.

    Azure da celulele ca lista plata, fiecare cu `rowIndex`/`columnIndex`. Le
    asezam noi in grila: o celula lipsa devine sir gol, ca randurile sa aiba
    toate aceeasi lungime si indicele de coloana sa insemne acelasi lucru pe
    fiecare rand. Fara asta, alinierea antet-valoare n-ar mai fi de incredere.

    Celulele imbinate (`columnSpan`) se repeta pe coloanele acoperite, din
    acelasi motiv: pastreaza indicii aliniati.
    """
    grile: list[tuple[tuple[str, ...], ...]] = []

    for tabel in analiza.get("tables") or []:
        randuri_n = int(tabel.get("rowCount") or 0)
        coloane_n = int(tabel.get("columnCount") or 0)
        if randuri_n <= 0 or coloane_n <= 0:
            continue

        grila = [["" for _ in range(coloane_n)] for _ in range(randuri_n)]

        for celula in tabel.get("cells") or []:
            rand = int(celula.get("rowIndex") or 0)
            coloana = int(celula.get("columnIndex") or 0)
            if not (0 <= rand < randuri_n and 0 <= coloana < coloane_n):
                continue

            # Azure rupe cuvintele lungi cu "-\n" la capat de celula
            # ("Virament ban-\ncar"); lipim la loc inainte de a normaliza.
            continut = (celula.get("content") or "").replace("-\n", "").replace("\n", " ").strip()

            for pas in range(max(int(celula.get("columnSpan") or 1), 1)):
                if coloana + pas < coloane_n:
                    grila[rand][coloana + pas] = continut

        grile.append(tuple(tuple(rand) for rand in grila))

    return tuple(grile)
