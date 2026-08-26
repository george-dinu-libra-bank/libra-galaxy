"""Agentul de creditare — dosarul omului, nu brosura produsului.

De ce un agent propriu si nu tool-uri puse pe `financial_advisor`, cum am
incercat prima oara: acela **nu foloseste registrul de tool-uri**. `select_tools()`
intoarce mereu `[]` si delegheaza toata tura buclei din `agents/financiar.py`,
peste `AnalizaService` (vezi antetul din `financial_advisor.py`). Tool-urile
declarate in spec-ul lui erau inregistrate corect, dar nimeni nu le putea cere —
in practica asistentul raspundea „nu am acces la deciziile bancii" si cauta prin
tranzactii dupa cuvantul „rata".

Aici tool-urile chiar se cer, prin acelasi drum ca la `transaction_intelligence`:
executorul le ruleaza inainte de model, iar modelul primeste rezultatele in
context. Selectia e **determinista**, dupa ce contine intrebarea — nu-l lasam pe
model sa aleaga daca sa se uite in dosar, fiindca exact asta gresea.
"""

from __future__ import annotations

import re
import unicodedata

from app.agents.base import (
    AgentAnswer,
    AttachmentContext,
    build_system_prompt,
    build_user_message,
    confidence_from_tool_results,
)
from app.agents.specs import CREDIT_ADVISOR
from app.context.builder import AssembledContext
from app.core.security import Principal
from app.providers.base import ChatMessage, ChatProvider
from app.tools.base import SelectedTool, ToolResult
from app.tools.categorii_tranzactii import SUMA_PATTERN as _SUMA

# Aceeasi normalizare ca in orchestration/intent.py: casefold + fara diacritice,
# ca "rată" si "rata" sa fie acelasi lucru.
def _normalizeaza(text: str) -> str:
    descompus = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in descompus if not unicodedata.combining(c))


_DESPRE_DECIZIE = ("respins", "aprobat", "aprobata", "de ce", "motiv", "scor", "indatorare", "dti")
_DESPRE_RATA = ("rata", "rate", "scadent", "de plata", "cat platesc")
_SIMULARE = ("ce rata as", "as avea", "daca iau", "daca as lua", "pot lua", "vreau sa iau", "simul")
# Cand omul vrea sa treaca de la vorbit la facut. `prepare_credit_application`
# pregateste formularul; depunerea ramane a lui.
_VREA_CERERE = (
    "depune", "sa depun", "vreau sa aplic", "aplic pentru", "completeaza",
    "fa-mi cererea", "fa cererea", "vreau un credit de", "as vrea un credit de",
    "cere pentru mine", "trimite cererea",
)

# "30.000 pe 4 ani", "30000 lei pe 48 de luni"
#
# Durata creditului cere prefixul "pe": intr-o fraza ca "lucrez la ACME de 3 ani,
# vreau 30000 pe 48 de luni" exista doua perechi numar+unitate, iar fara prefix
# se alegea vechimea (3 ani -> 36 luni) in loc de durata ceruta. "de" optional
# intre numar si unitate, fiindca romana il pune ("48 de luni") si nu-l pune
# ("48 luni") la fel de des.
# _SUMA vine din categorii_tranzactii.py (SUMA_PATTERN) — acelasi tipar, reutilizat
# de find_transaction_for_receipt, nu duplicat.
_ANI = re.compile(r"pe\s+(\d{1,2})\s*(?:de\s+)?(?:ani|an)\b")
_LUNI = re.compile(r"pe\s+(\d{1,3})\s*(?:de\s+)?(?:luni|luna)\b")


def _cifre(text: str) -> tuple[float, int] | None:
    """Suma si durata in luni, daca intrebarea le contine amandoua.

    Fara ele, `simulate_credit` n-are ce calcula si ar intoarce o eroare pe care
    modelul ar trebui sa o explice — mai bine nu-l chemam deloc.
    """
    luni_gasite = _LUNI.search(text)
    ani_gasiti = _ANI.search(text)
    if luni_gasite:
        luni = int(luni_gasite.group(1))
    elif ani_gasiti:
        luni = int(ani_gasiti.group(1)) * 12
    else:
        return None

    for potrivire in _SUMA.finditer(text):
        brut = potrivire.group(1).replace(".", "").replace(" ", "").strip()
        if not brut.isdigit():
            continue
        valoare = float(brut)
        # Peste 1000: sub atat e aproape sigur durata ("4 ani", "48 luni") sau
        # un an calendaristic, nu suma imprumutata.
        if valoare >= 1000:
            return valoare, luni

    return None


# Datele formularului, culese din text. Orchestratorul cheama `select_tools`
# determinist, o singura data pe tura — nu exista o bucla in care modelul sa
# poata umple argumentele treptat. Deci le extragem noi, iar ce nu gasim se
# intoarce ca `missing` din tool: modelul intreaba exact bucata care lipseste,
# omul raspunde, si la tura urmatoare textul are deja si acea informatie
# (conversatia recenta intra in context).
_VENIT = re.compile(
    r"(?:castig|caștig|venit(?:ul)?(?:\s+net)?(?:\s+e)?|salariu(?:l)?(?:\s+e)?)\D{0,12}?(\d[\d.\s]{2,})"
)
_OBLIGATII = re.compile(
    r"(?:rate|obligatii|datorii|platesc lunar)\D{0,12}?(\d[\d.\s]{2,})"
)
# Numele angajatorului: cautare de prefix + taiere la primul cuvant de legatura.
# A fost regex si m-a costat trei incercari — se oprea dupa punctuatie, dar nu
# dupa " de ", deci inghitea " de 3 ani" in numele firmei. Varianta asta face
# acelasi lucru, se citeste dintr-o privire si se depaneaza cu un print.
_PREFIXE_ANGAJATOR = (
    "lucrez la ", "angajat la ", "angajata la ",
    "angajatorul e ", "angajatorul este ", "angajator ", "firma ", "societatea ",
)
_STOP_ANGAJATOR = (" de ", " din ", " si ", " iar ", " unde ", " cu ", ",", ".", ";", "!", "?")


def _angajator(text: str) -> str | None:
    for prefix in _PREFIXE_ANGAJATOR:
        pozitie = text.find(prefix)
        if pozitie == -1:
            continue

        rest = text[pozitie + len(prefix):]
        taieturi = [rest.find(s) for s in _STOP_ANGAJATOR if rest.find(s) != -1]
        nume = (rest[: min(taieturi)] if taieturi else rest).strip()
        if len(nume) >= 2:
            return nume

    return None
_VECHIME_ANI = re.compile(r"de\s+(\d{1,2})\s*(?:ani|an)\b")
_VECHIME_LUNI = re.compile(r"de\s+(\d{1,3})\s*(?:luni|luna)\b")


def _numar(brut: str) -> str | None:
    curat = brut.replace(".", "").replace(" ", "").strip()
    return curat if curat.isdigit() else None


def _date_cerere(text: str) -> dict:
    date: dict = {}

    cifre = _cifre(text)
    if cifre is not None:
        date["suma"], date["luni"] = str(cifre[0]), cifre[1]

    venit = _VENIT.search(text)
    if venit and (curat := _numar(venit.group(1))):
        date["venit_declarat"] = curat

    obligatii = _OBLIGATII.search(text)
    if obligatii and (curat := _numar(obligatii.group(1))):
        date["obligatii_declarate"] = curat

    angajator = _angajator(text)
    if angajator:
        date["angajator"] = angajator

    ani = _VECHIME_ANI.search(text)
    luni = _VECHIME_LUNI.search(text)
    if luni:
        date["vechime_angajator_luni"] = int(luni.group(1))
    elif ani:
        date["vechime_angajator_luni"] = int(ani.group(1)) * 12

    return date


class CreditAdvisorAgent:
    spec = CREDIT_ADVISOR

    def select_tools(self, user_text: str, intent: str) -> list[SelectedTool]:
        text = _normalizeaza(user_text)
        alese: list[SelectedTool] = []

        cifre = _cifre(text)
        if cifre is not None and any(c in text for c in _SIMULARE):
            suma, luni = cifre
            alese.append(SelectedTool(
                "simulate_credit", {"suma": str(suma), "luni": luni},
                "intrebare de simulare cu suma si durata explicite",
            ))

        if any(c in text for c in _VREA_CERERE):
            # Argumentele le pune modelul din conversatie; noi doar semnalam ca
            # tool-ul e potrivit. Fara date, tool-ul intoarce `missing` si
            # modelul stie exact ce sa mai intrebe.
            alese.append(SelectedTool(
                "prepare_credit_application", _date_cerere(text),
                "utilizatorul vrea sa depuna o cerere de credit",
            ))

        if any(c in text for c in _DESPRE_DECIZIE):
            alese.append(SelectedTool(
                "get_credit_decision", {}, "intrebare despre motivele unei decizii",
            ))

        if any(c in text for c in _DESPRE_RATA):
            alese.append(SelectedTool(
                "get_next_installment", {}, "intrebare despre rata de platit",
            ))

        # Starea dosarelor si creditele in derulare merg mereu: aproape orice
        # intrebare de creditare are nevoie de ele ca sa aiba despre ce vorbi,
        # iar amandoua sunt o singura citire fiecare.
        alese.append(SelectedTool(
            "get_credit_applications", {}, "starea cererilor de credit ale utilizatorului",
        ))
        alese.append(SelectedTool(
            "get_active_credits", {}, "creditele in derulare, pentru context",
        ))

        # Ordinea conteaza doar pentru citit; duplicatele nu, fiindca selectia
        # de mai sus nu poate cere acelasi tool de doua ori.
        return alese

    async def respond(
        self,
        principal: Principal,
        user_text: str,
        context: AssembledContext,
        tool_results: list[ToolResult],
        chat_provider: ChatProvider,
        attachments: list[AttachmentContext] = (),
    ) -> AgentAnswer:
        system_prompt = build_system_prompt(self.spec, context)
        completion = await chat_provider.complete([
            ChatMessage(role="system", content=system_prompt),
            build_user_message(user_text, attachments),
        ])
        return AgentAnswer(
            text=completion.text,
            citations=[],
            confidence=confidence_from_tool_results(tool_results),
            tokens_in=completion.tokens_in,
            tokens_out=completion.tokens_out,
            tokens_cached=completion.tokens_cached,
        )
