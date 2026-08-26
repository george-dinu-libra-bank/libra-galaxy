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

# Aceeasi normalizare ca in orchestration/intent.py: casefold + fara diacritice,
# ca "rată" si "rata" sa fie acelasi lucru.
#
# Varianta cu harta pastreaza, pentru fiecare caracter din textul normalizat,
# pozitia din care a venit in textul original. E nevoie de ea la numele
# angajatorului: cautam prefixul in text normalizat ("lucrez la "), dar taiem
# felia din textul ORIGINAL, ca sa iasa "ACME Software", nu "acme software".
# Indicii nu se pot deduce prin scadere — "ă" ocupa un caracter in original si
# unul in normalizat, dar "ß" devine "ss", iar lungimile se desincronizeaza.
def _normalizeaza_cu_harta(text: str) -> tuple[str, list[int]]:
    bucati: list[str] = []
    harta: list[int] = []
    for pozitie, caracter in enumerate(text):
        for c in unicodedata.normalize("NFKD", caracter.casefold()):
            if unicodedata.combining(c):
                continue
            bucati.append(c)
            harta.append(pozitie)
    return "".join(bucati), harta


def _normalizeaza(text: str) -> str:
    return _normalizeaza_cu_harta(text)[0]


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
_SUMA = re.compile(r"(\d[\d.\s]{2,})\s*(?:lei|ron)?")
# Suma legata de cuvantul care o explica. Fara ancora, `_cifre` lua primul numar
# >= 1000 din fraza, oricare ar fi fost el: in "castig 5200 net, vreau un credit
# de 30000 pe 48 de luni" ajungea in formular 5200 ca suma imprumutata. Ancora se
# incearca prima; daca lipseste, se cade pe primul numar neatribuit deja altui
# camp (vezi `ignora` mai jos).
_SUMA_ANCORATA = re.compile(r"(?:credit|imprumut|suma)\w*\s+(?:de\s+)?(\d[\d.\s]{2,})")
_ANI = re.compile(r"pe\s+(\d{1,2})\s*(?:de\s+)?(?:ani|an)\b")
_LUNI = re.compile(r"pe\s+(\d{1,3})\s*(?:de\s+)?(?:luni|luna)\b")


def _cifre(text: str, ignora: frozenset[float] = frozenset()) -> tuple[float, int] | None:
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

    ancorat = _SUMA_ANCORATA.search(text)
    if ancorat and (curat := _numar(ancorat.group(1))) and float(curat) >= 1000:
        return float(curat), luni

    for potrivire in _SUMA.finditer(text):
        curat = _numar(potrivire.group(1))
        if curat is None:
            continue
        valoare = float(curat)
        # Peste 1000: sub atat e aproape sigur durata ("4 ani", "48 luni") sau
        # un an calendaristic, nu suma imprumutata. `ignora` scoate numerele deja
        # atribuite venitului sau obligatiilor — altfel primul numar din fraza
        # castiga, indiferent ce inseamna.
        if valoare >= 1000 and valoare not in ignora:
            return valoare, luni

    return None


def _suma_text(valoare: float) -> str:
    """Suma ca text, fara ".0" parazit.

    `str(30000.0)` da "30000.0", iar tool-ul face apoi `str(int(...))` in URL —
    deci orice zecimala se pierdea tacit. Se formateaza o data, aici, corect.
    """
    return str(int(valoare)) if valoare == int(valoare) else f"{valoare:.2f}"


# Datele formularului, culese din text. Orchestratorul cheama `select_tools`
# determinist, o singura data pe tura — nu exista o bucla in care modelul sa
# poata umple argumentele treptat. Deci le extragem noi, iar ce nu gasim se
# intoarce ca `missing` din tool, si modelul intreaba exact bucata care lipseste.
#
# ATENTIE, aici a fost scris odata ca „la tura urmatoare textul are deja si acea
# informatie": nu e adevarat. `select_tools` primeste DOAR mesajul curent
# (orchestrator.py::handle_message), nu fereastra `recent`, iar `ChatProvider`
# n-are function calling. Un raspuns de tip „5200 lei" nu contine niciun
# declansator din `_VREA_CERERE`, deci tool-ul nici nu se mai selecteaza.
# Acumularea peste mai multe ture cere o schimbare de contract intre orchestrator
# si agenti — nu e facuta, si nu trebuie presupusa.
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


def _angajator(text: str, harta: list[int], original: str) -> str | None:
    """Numele firmei, cautat in textul normalizat dar TAIAT din cel original.

    Cautarea trebuie sa fie pe text normalizat (prefixele sunt scrise fara
    diacritice si cu litere mici), dar rezultatul ajunge direct in formularul
    cererii de credit, sub ochii unui analist. "acme software" acolo arata a
    data scoasa dintr-o masina; "ACME Software" arata a nume de firma.
    """
    for prefix in _PREFIXE_ANGAJATOR:
        pozitie = text.find(prefix)
        if pozitie == -1:
            continue

        inceput = pozitie + len(prefix)
        rest = text[inceput:]
        taieturi = [rest.find(stop) for stop in _STOP_ANGAJATOR if rest.find(stop) != -1]
        lungime = min(taieturi) if taieturi else len(rest)

        bruta = rest[:lungime]
        felie = bruta.strip()
        if len(felie) < 2:
            continue

        # Inapoi la textul original, prin harta de pozitii. Marginile se
        # recalculeaza fata de felia netrunchiata, ca spatiile taiate de
        # `strip()` sa nu deplaseze indicii.
        decalaj = bruta.index(felie)
        prima = harta[inceput + decalaj]
        ultima = harta[inceput + decalaj + len(felie) - 1]
        return original[prima:ultima + 1].strip()

    return None
# "de" optional intre numar si unitate, exact ca la `_LUNI` de mai sus si din
# acelasi motiv: romana scrie si "36 luni", si "36 de luni". Fara el, "am vechime
# de 36 de luni" nu se citea deloc, iar tool-ul intorcea vechimea ca `missing` —
# adica agentul reintreba fix ce tocmai spusese omul.
_VECHIME_ANI = re.compile(r"de\s+(\d{1,2})\s*(?:de\s+)?(?:ani|an)\b")
_VECHIME_LUNI = re.compile(r"de\s+(\d{1,3})\s*(?:de\s+)?(?:luni|luna)\b")


def _numar(brut: str) -> str | None:
    curat = brut.replace(".", "").replace(" ", "").strip()
    return curat if curat.isdigit() else None


def _date_cerere(text: str, harta: list[int], original: str) -> dict:
    date: dict = {}

    # Venitul si obligatiile se citesc INAINTEA sumei: amandoua sunt ancorate de
    # un cuvant ("castig", "rate"), deci sunt sigure, iar numerele lor se scot
    # din calea sumei, care e cea mai vulnerabila la confuzie.
    venit = _VENIT.search(text)
    if venit and (curat := _numar(venit.group(1))):
        date["venit_declarat"] = curat

    obligatii = _OBLIGATII.search(text)
    if obligatii and (curat := _numar(obligatii.group(1))):
        date["obligatii_declarate"] = curat

    atribuite = frozenset(
        float(date[cheie])
        for cheie in ("venit_declarat", "obligatii_declarate")
        if cheie in date
    )

    cifre = _cifre(text, atribuite)
    if cifre is not None:
        date["suma"], date["luni"] = _suma_text(cifre[0]), cifre[1]

    angajator = _angajator(text, harta, original)
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

    @staticmethod
    def _citari(tool_results: list[ToolResult]) -> list[dict]:
        """Sursele raspunsului, cand el vine din cunostintele bancii.

        Aceeasi forma ca in document_intelligence.py: un raspuns despre dobanda
        sau despre conditiile de eligibilitate trebuie sa poata fi urmarit inapoi
        la documentul din care a iesit. Raspunsurile care vin doar din dosarul
        omului n-au ce cita — acolo lista ramane goala.
        """
        for rezultat in tool_results:
            if rezultat.tool_name == "search_bank_knowledge" and rezultat.success and rezultat.data:
                return [
                    {"document_id": hit["document_id"], "section": hit.get("section"), "score": hit["score"]}
                    for hit in rezultat.data.get("hits", [])[:3]
                ]
        return []

    def select_tools(self, user_text: str, intent: str) -> list[SelectedTool]:
        text, harta = _normalizeaza_cu_harta(user_text)
        alese: list[SelectedTool] = []

        cifre = _cifre(text)
        if cifre is not None and any(c in text for c in _SIMULARE):
            suma, luni = cifre
            alese.append(SelectedTool(
                "simulate_credit", {"suma": _suma_text(suma), "luni": luni},
                "intrebare de simulare cu suma si durata explicite",
            ))

        vrea_cerere = any(c in text for c in _VREA_CERERE)

        if vrea_cerere:
            # Argumentele le extragem noi, determinist, din mesajul curent — nu
            # exista function calling prin care modelul sa le puna. Ce nu gasim
            # se intoarce ca `missing` si modelul stie exact ce sa mai intrebe.
            alese.append(SelectedTool(
                "prepare_credit_application", _date_cerere(text, harta, user_text),
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

        # Brosura, dar NU cand omul completeaza cererea.
        #
        # De cand `credit_intent` se ruteaza aici (specs.py), agentul primeste si
        # intrebarile pur informative — „ce dobanda are creditul de nevoi
        # personale?" — la care tool-urile de dosar n-au ce raspunde.
        #
        # Cautarea se opreste insa cand `prepare_credit_application` e in joc:
        # documentul cu procedura de creditare listeaza actele cerute la ghiseu
        # (CNP, act de identitate, acord Birou de Credit), iar modelul, primind si
        # formularul gata pregatit si acea lista, recita lista si cere omului date
        # pe care banca le are deja. Verificat pe viu: raspunsul devenea un
        # chestionar de ghiseu in loc de „poftim formularul". Cand omul vrea sa
        # faca, nu sa afle, formularul castiga.
        #
        # `categorie_hint` se pune determinist, din intentie, nu de catre model
        # (aceeasi regula ca in document_intelligence.py).
        if not vrea_cerere:
            alese.append(SelectedTool(
                "search_bank_knowledge",
                {"query": user_text, "categorie_hint": "credite"},
                "conditiile produsului, din cunostintele bancii",
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
            citations=self._citari(tool_results),
            confidence=confidence_from_tool_results(tool_results),
            tokens_in=completion.tokens_in,
            tokens_out=completion.tokens_out,
            tokens_cached=completion.tokens_cached,
        )
