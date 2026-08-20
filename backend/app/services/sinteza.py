"""Paragraful de sinteza al raportului, scris de model.

Se aseaza deasupra faptelor, niciodata in locul lor. Modelul primeste exact
constatarile deja calculate si are voie sa le lege intre ele — sa observe ca
trei dintre ele sunt in aceeasi saptamana, ca doua sunt la comercianti noi —
nu sa adauge cifre sau concluzii proprii.

De ce nu genereaza modelul tot raportul: un raport pe baza caruia cineva
blocheaza un cont trebuie sa iasa identic de fiecare data si sa contina exact
ce a produs detectorul. Sinteza e singura parte unde variatia nu strica nimic,
fiindca faptele raman dedesubt, verificabile.

Daca modelul nu e configurat sau nu raspunde, raportul se face fara sinteza —
la fel cum detectia merge fara model.joblib.
"""

import logging

from app.infrastructure.llm import ClientModel
from app.services.raport_service import ETICHETE_TIP, Raport

logger = logging.getLogger(__name__)

MAX_CONSTATARI_IN_PROMPT = 25

INSTRUCTIUNI = """Esti analist intr-o banca. Primesti constatarile unui detector
de plati atipice pentru un singur cont si scrii un paragraf de sinteza pentru
colegul care va verifica manual contul.

Reguli:
- Scrie in romana, la persoana a treia, despre "contul" sau "titularul". Nu te
  adresa cititorului cu "verificati"; spune ce merita verificat.
- Cel mult 4 propozitii, si opreste-te. Un paragraf, fara titluri, fara liste,
  fara formatare. Daca ai spus ce era de spus in doua propozitii, sunt de ajuns.
- Nu inventa nicio cifra. Foloseste numai sumele si datele primite.
- Nu spune ca e frauda. Sunt constatari statistice; scrie despre ce merita verificat.
- Cauta legatura dintre constatari: perioada comuna, acelasi comerciant, tipuri
  care se repeta. Daca nu exista nicio legatura, spune ca semnalarile par izolate.
- Nu repeta lista constatarilor: e deja in tabelul de dedesubt.
- Nu insira ce nu poti sti din datele primite."""


def _descrie(raport: Raport) -> str:
    linii = [
        f"Cont: {raport.nume}",
        f"Perioada analizata: ultimele {raport.zile} de zile",
        f"Tranzactii in perioada: {raport.total_tranzactii}",
        f"Constatari: {len(raport.constatari)}",
        "",
        "Constatarile, cea mai grava prima:",
    ]
    for c in raport.constatari[:MAX_CONSTATARI_IN_PROMPT]:
        linii.append(
            f"- {c.data} | {ETICHETE_TIP.get(c.tip, c.tip)} | {c.suma:.2f} {c.valuta} "
            f"| {c.comerciant} | scor {c.scor:.2f} | {c.explicatie}"
        )
    if len(raport.constatari) > MAX_CONSTATARI_IN_PROMPT:
        linii.append(
            f"(inca {len(raport.constatari) - MAX_CONSTATARI_IN_PROMPT} constatari, "
            "mai putin grave)"
        )
    return "\n".join(linii)


async def scrie_sinteza(raport: Raport, client: ClientModel) -> str | None:
    """Paragraful de sinteza, sau None daca modelul nu poate fi folosit."""
    if not raport.constatari:
        return None

    try:
        raspuns = await client.completeaza(
            [
                {"role": "system", "content": INSTRUCTIUNI},
                {"role": "user", "content": _descrie(raport)},
            ]
        )
    except Exception:
        logger.exception("sinteza nu a putut fi generata; raportul merge fara ea")
        return None

    text = (raspuns.text or "").strip()
    return text or None
