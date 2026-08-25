"""Tool-uri de creditare pentru asistent — citire si calcul determinist, niciodata scriere.

Pana acum asistentul nu stia nimic despre credite: niciun tool, niciun intent,
niciunul din cei cinci agenti. „De ce mi-a fost respinsa cererea?" cadea pe
`unknown`, ajungea la `document_intelligence` si primea un raspuns din baza de
cunostinte despre produsul Galaxy Flex Personal — corect in general, dar despre
altcineva. Omul intreba de dosarul lui.

Doua reguli care nu se incalca aici:

1. **`user_id` nu e parametru de tool** (docs/AGENTS.md #1). Tool-urile sunt
   inchideri peste `Principal`, deci modelul nu poate cere dosarul altcuiva nici
   daca i se sugereaza asta in mesaj.
2. **Modelul formuleaza, motorul calculeaza.** `simulate_credit` merge prin
   `amortizare`/`reguli`, aceleasi module ca fluxul real de creditare, deci rata
   pe care o spune asistentul e chiar rata pe care ar primi-o. Un numar produs
   de model ar fi o promisiune pe care banca n-o poate onora.

Toate sunt READ_ONLY/COMPUTE si LOW: nu misca bani, nu schimba stari, nu decid
nimic. Deciziile raman in `CreditService`, dupa motorul determinist.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from app.core.security import PERMISSION_ACCOUNTS_READ, Principal
from app.credit import amortizare
from app.repositories.credit_repository import CreditRepository
from app.services.credit_service import PRODUS_IMPLICIT
from app.tools.base import RiskLevel, SideEffect, ToolDefinition

# Creditele sunt situatia financiara a omului, deci stau la acelasi agent care
# vorbeste despre solduri si cashflow. Un al saselea agent ar taia in doua exact
# contextul de care are nevoie ca sa raspunda („poti sa-mi permiti rata asta?"
# cere si creditul, si cheltuielile).
# `credit_advisor`, nu `financial_advisor`: acela nu foloseste registrul de
# tool-uri (`select_tools()` intoarce mereu [], vezi agents/financial_advisor.py),
# deci tool-urile atasate lui erau inregistrate dar imposibil de cerut.
_AGENTI = frozenset({"credit_advisor"})

# Ce inseamna fiecare stare pentru cel care intreaba. Modelul primeste explicatia
# gata scrisa, ca sa nu inventeze el ce urmeaza — „in_analiza" nu spune nimanui
# daca trebuie sa faca ceva.
_CE_URMEAZA = {
    "ciorna": "Cererea nu a fost trimisa inca; poate fi completata din aplicatie.",
    "in_analiza": "Se verifica automat. Nu e nimic de facut, raspunsul vine singur.",
    "analiza_manuala": "Un analist se uita peste dosar. Nu e nimic de facut.",
    "asteapta_documente": "Banca asteapta documente. Sunt de incarcat din ecranul de credite.",
    "oferta": "Exista o oferta de semnat, valabila pana la data de expirare.",
    "acceptata": "Oferta a fost semnata si creditul e acordat.",
    "respinsa": "Cererea nu a fost aprobata. Se poate depune alta oricand.",
    "anulata": "Cererea a fost retrasa de client.",
    "expirata": "Oferta nu a fost semnata la timp. Se poate depune o cerere noua.",
}


def _lei(valoare) -> float | None:
    return None if valoare is None else float(Decimal(str(valoare)))


def build_credit_tools(repository: CreditRepository) -> list[ToolDefinition]:
    async def get_credit_applications(principal: Principal, _args: dict) -> dict:
        cereri = await repository.cereri_utilizator(principal.user_id)
        return {
            "applications": [
                {
                    "id": str(cerere["id"]),
                    "status": cerere["status"],
                    "ce_urmeaza": _CE_URMEAZA.get(str(cerere["status"]), ""),
                    "suma_ceruta": _lei(cerere.get("suma_ceruta")),
                    "luni": cerere.get("luni"),
                    "rata_lunara": _lei(cerere.get("rata_lunara")),
                    "creat_la": cerere.get("creat_la"),
                    "oferta_expira_la": cerere.get("oferta_expira_la"),
                }
                for cerere in cereri
            ]
        }

    async def get_credit_decision(principal: Principal, args: dict) -> dict:
        """Motivele deciziei, asa cum le-a scris motorul determinist.

        `motive` tine si factorii scorecard-ului, si criteriile hard de
        respingere (vezi `CreditService._finalizeaza`). Se intorc ca atare:
        explicatia de ce a iesit un scor e treaba motorului, nu a modelului.
        """
        cereri = await repository.cereri_utilizator(principal.user_id)
        cerut = str(args.get("application_id") or "").strip()

        # Fara id, ultima cerere — cazul obisnuit („de ce am fost respins?"
        # inseamna aproape mereu cea mai recenta). Filtrarea se face pe lista
        # proprie, deci un id strain nu poate fi citit nici din greseala.
        cerere = next((c for c in cereri if str(c["id"]) == cerut), cereri[0] if cereri else None)
        if cerere is None:
            return {"found": False}

        return {
            "found": True,
            "id": str(cerere["id"]),
            "status": cerere["status"],
            "ce_urmeaza": _CE_URMEAZA.get(str(cerere["status"]), ""),
            "scor": cerere.get("scor"),
            "dti": _lei(cerere.get("dti")),
            "explicatie": cerere.get("explicatie"),
            "motive": cerere.get("motive") or [],
            "venit_folosit": _lei(cerere.get("venit_folosit")),
            "obligatii_folosite": _lei(cerere.get("obligatii_folosite")),
        }

    async def get_active_credits(principal: Principal, _args: dict) -> dict:
        credite = await repository.credite_utilizator(principal.user_id)
        return {
            "credits": [
                {
                    "id": str(credit["id"]),
                    "status": credit["status"],
                    "principal": _lei(credit.get("principal")),
                    "sold_ramas": _lei(credit.get("sold_ramas")),
                    "rata_lunara": _lei(credit.get("rata_lunara")),
                    "luni": credit.get("luni"),
                    "dobanda_anuala": _lei(credit.get("dobanda_anuala")),
                    "data_acordarii": credit.get("data_acordarii"),
                }
                for credit in credite
            ]
        }

    async def get_next_installment(principal: Principal, _args: dict) -> dict:
        """Prima rata neplatita de pe fiecare credit activ.

        Intrebarea „ce am de platit luna asta" nu are un raspuns unic daca omul
        are doua credite, deci se intorc toate — modelul le insumeaza in text,
        dar cifrele vin de aici.
        """
        credite = await repository.credite_utilizator(principal.user_id)
        rezultat = []

        for credit in credite:
            if credit.get("status") not in ("activ", "restant"):
                continue
            rate = await repository.rate(credit["id"])
            urmatoarea = next((r for r in rate if r.get("status") != "platita"), None)
            if urmatoarea is None:
                continue
            rezultat.append({
                "id_credit": str(credit["id"]),
                "numar_rata": urmatoarea.get("numar"),
                "scadenta": urmatoarea.get("scadenta"),
                "total": _lei(urmatoarea.get("total")),
                "status": urmatoarea.get("status"),
            })

        return {"installments": rezultat}

    async def simulate_credit(_principal: Principal, args: dict) -> dict:
        """Rata si costul pentru o suma si o durata, prin motorul real.

        Nu spune daca cererea ar fi aprobata — asta cere venitul confirmat,
        obligatiile si scorecard-ul, adica o evaluare, nu o simulare. Instructiunile
        agentului ii interzic explicit sa deduca aprobarea de aici.
        """
        try:
            suma = Decimal(str(args.get("suma", "0")))
            luni = int(args.get("luni", 0))
        except (InvalidOperation, TypeError, ValueError):
            return {"error": "Suma sau durata nu sunt numere valide."}

        if suma <= 0 or luni <= 0:
            return {"error": "Suma si durata trebuie sa fie pozitive."}

        produs = await repository.produs(PRODUS_IMPLICIT)
        if produs is None:
            return {"error": "Catalogul de produse nu e disponibil momentan."}
        dobanda = Decimal(str(produs["dobanda_anuala"]))
        principal_bani = amortizare.bani_din_lei(suma)
        rata_bani = amortizare.rata_lunara_bani(principal_bani, dobanda, luni)
        rata = amortizare.lei_din_bani(rata_bani)

        return {
            "suma": float(suma),
            "luni": luni,
            "dobanda_anuala": float(dobanda),
            "rata_lunara": float(rata),
            "dae": float(amortizare.dae(principal_bani, rata_bani, luni)),
            "total_platit": float(rata * luni),
            "cost_total": float(rata * luni - suma),
        }

    async def prepare_credit_application(_principal: Principal, args: dict) -> dict:
        """Pregateste cererea, dar NU o depune.

        Depunerea cere `consimtamant=true` — un acord informat, dat de om, despre
        interogarea Biroului de Credit si prelucrarea datelor lui. Un model care
        deduce acordul dintr-o conversatie nu e acelasi lucru cu omul care bifeaza
        casuta, iar aici diferenta e juridica, nu de stil. De aceea tool-ul e
        `PREPARES_MUTATION`: strange datele, le valideaza fata de limitele
        produsului, calculeaza rata cu motorul real si intoarce o adresa care
        deschide formularul **completat**. Ultimul pas ramane o apasare a lui.

        Acelasi tipar ca la Agentul Actiuni din docs/AGENTS.md: agentul propune,
        executia ramane in serviciu, dupa confirmare explicita in interfata.
        """
        produs = await repository.produs(PRODUS_IMPLICIT)
        if produs is None:
            return {"error": "Catalogul de produse nu e disponibil momentan."}

        lipsesc: list[str] = []
        try:
            suma = Decimal(str(args.get("suma", "0")))
            luni = int(args.get("luni", 0))
            venit = Decimal(str(args.get("venit_declarat", "0")))
            obligatii = Decimal(str(args.get("obligatii_declarate", "0")))
            vechime = int(args.get("vechime_angajator_luni", 0))
        except (InvalidOperation, TypeError, ValueError):
            return {"error": "Una dintre valori nu e un numar valid."}

        angajator = str(args.get("angajator") or "").strip()

        # Se spune ce lipseste, pe nume: modelul trebuie sa poata cere exact
        # bucata care ii lipseste, nu sa reia tot chestionarul de la capat.
        if suma <= 0:
            lipsesc.append("suma dorita")
        if luni <= 0:
            lipsesc.append("durata in luni")
        if venit <= 0:
            lipsesc.append("venitul lunar net")
        if not angajator:
            lipsesc.append("numele angajatorului")
        if vechime <= 0:
            lipsesc.append("vechimea la angajatorul actual, in luni")

        if lipsesc:
            return {"ready": False, "missing": lipsesc}

        minim = Decimal(str(produs["suma_min"]))
        maxim = Decimal(str(produs["suma_max"]))
        if not (minim <= suma <= maxim):
            return {
                "ready": False,
                "error": (
                    f"Suma trebuie sa fie intre {minim} si {maxim} RON pentru "
                    f"{produs['nume']}."
                ),
            }
        if not (int(produs["luni_min"]) <= luni <= int(produs["luni_max"])):
            return {
                "ready": False,
                "error": (
                    f"Durata trebuie sa fie intre {produs['luni_min']} si "
                    f"{produs['luni_max']} luni."
                ),
            }

        dobanda = Decimal(str(produs["dobanda_anuala"]))
        principal_bani = amortizare.bani_din_lei(suma)
        rata = amortizare.lei_din_bani(
            amortizare.rata_lunara_bani(principal_bani, dobanda, luni)
        )

        parametri = urlencode({
            "suma": str(int(suma)), "luni": luni,
            "venit": str(venit), "angajator": angajator,
            "vechime": vechime, "obligatii": str(obligatii),
        })

        return {
            "ready": True,
            "suma": float(suma),
            "luni": luni,
            "rata_lunara": float(rata),
            "venit_declarat": float(venit),
            "angajator": angajator,
            "vechime_angajator_luni": vechime,
            "obligatii_declarate": float(obligatii),
            "link": f"/credite/cerere?{parametri}",
            "ce_urmeaza": (
                "Formularul se deschide completat. Cererea se depune abia dupa ce "
                "omul verifica datele si bifeaza acordul — asistentul nu poate da "
                "acel acord in locul lui."
            ),
        }

    return [
        ToolDefinition(
            name="prepare_credit_application",
            description=(
                "Pregateste o cerere de credit din datele stranse in conversatie si "
                "intoarce o adresa care deschide formularul completat. Argumente: "
                "'suma', 'luni', 'venit_declarat', 'angajator', "
                "'vechime_angajator_luni', 'obligatii_declarate'. Daca lipseste ceva, "
                "intoarce lista in 'missing' — cere-i utilizatorului exact acele "
                "date. NU depune cererea: acordul si trimiterea raman ale omului."
            ),
            callback=prepare_credit_application,
            allowed_agents=_AGENTI,
            required_permissions=frozenset({PERMISSION_ACCOUNTS_READ}),
            # Pregateste o mutatie, nu o face. Contractul din tools/base.py cere
            # confirmare doar pentru MUTATES, dar o punem si aici: e cel mai
            # aproape de „bani in joc" din tot ce are asistentul.
            side_effect=SideEffect.PREPARES_MUTATION,
            risk_level=RiskLevel.MEDIUM,
            requires_confirmation=True,
        ),
        ToolDefinition(
            name="get_credit_applications",
            description=(
                "Cererile de credit ale utilizatorului curent, cu starea fiecareia si ce "
                "urmeaza sa se intample. Foloseste-l pentru 'unde e cererea mea', 'ce se "
                "intampla cu creditul pe care l-am cerut'."
            ),
            callback=get_credit_applications,
            allowed_agents=_AGENTI,
            required_permissions=frozenset({PERMISSION_ACCOUNTS_READ}),
            side_effect=SideEffect.READ_ONLY,
            risk_level=RiskLevel.LOW,
        ),
        ToolDefinition(
            name="get_credit_decision",
            description=(
                "Decizia pe o cerere de credit si motivele ei, asa cum le-a scris motorul: "
                "scor, grad de indatorare, factorii de punctaj sau criteriile de respingere. "
                "Foloseste-l pentru 'de ce am fost respins', 'de ce e cererea in analiza'. "
                "Fara 'application_id' raspunde despre cea mai recenta cerere."
            ),
            callback=get_credit_decision,
            allowed_agents=_AGENTI,
            required_permissions=frozenset({PERMISSION_ACCOUNTS_READ}),
            side_effect=SideEffect.READ_ONLY,
            risk_level=RiskLevel.LOW,
        ),
        ToolDefinition(
            name="get_active_credits",
            description=(
                "Creditele in derulare ale utilizatorului: sold ramas, rata lunara, dobanda "
                "si durata. Foloseste-l pentru 'cat mai am de platit', 'ce credite am'."
            ),
            callback=get_active_credits,
            allowed_agents=_AGENTI,
            required_permissions=frozenset({PERMISSION_ACCOUNTS_READ}),
            side_effect=SideEffect.READ_ONLY,
            risk_level=RiskLevel.LOW,
        ),
        ToolDefinition(
            name="get_next_installment",
            description=(
                "Urmatoarea rata neplatita de pe fiecare credit activ, cu suma si scadenta. "
                "Foloseste-l pentru 'cand am rata', 'cat platesc luna asta'."
            ),
            callback=get_next_installment,
            allowed_agents=_AGENTI,
            required_permissions=frozenset({PERMISSION_ACCOUNTS_READ}),
            side_effect=SideEffect.READ_ONLY,
            risk_level=RiskLevel.LOW,
        ),
        ToolDefinition(
            name="simulate_credit",
            description=(
                "Calculeaza rata lunara, DAE si costul total pentru o suma ('suma') si o "
                "durata in luni ('luni'), cu motorul de amortizare al bancii. Foloseste-l "
                "pentru 'ce rata as avea la X lei pe Y ani'. NU spune daca cererea ar fi "
                "aprobata — pentru asta e nevoie de o evaluare, nu de o simulare."
            ),
            callback=simulate_credit,
            allowed_agents=_AGENTI,
            required_permissions=frozenset({PERMISSION_ACCOUNTS_READ}),
            side_effect=SideEffect.COMPUTE,
            risk_level=RiskLevel.LOW,
        ),
    ]
