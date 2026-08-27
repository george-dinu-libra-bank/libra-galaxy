"""Transforma randurile brute in trasaturi. Pur, fara retea — de aceea testabil."""

import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

SPATII = re.compile(r"\s+")
CIFRE_LUNGI = re.compile(r"\d{4,}")
# Cuvintele care preced un numar de referinta si raman orfane dupa ce il scoatem.
MARCAJE_REFERINTA = re.compile(r"\b(ref|nr|id|cod|tranzactie|auth)\.?$")

# Miscarile de credit ale bancii, care NU sunt plati facute de om.
#
# Descrierile sunt scrise de RPC-urile din 0010_credite_operatiuni.sql, cu
# format fix: `format('Rata %s/%s credit', ...)` la linia 236 si cele doua
# variante de rambursare anticipata la 367-368. Tiparul e cunoscut, nu ghicit.
#
# Se scot inainte de orice analiza fiindca produceau semnalari absurde. Rata
# 1/12, 2/12 si 3/12 arata ca trei comercianti DIFERITI — `normalizeaza_comerciant`
# taie numerele de referinta lungi, dar nu si „1/12" — asa ca fiecare rata
# devenea „prima plata la un comerciant nou". Rezultatul: banca il intreba pe
# client daca a autorizat plata propriilor rate.
#
# Motivul de fond e insa mai simplu decat bug-ul de grupare: ratele nu sunt un
# comportament al omului. El nu alege cand si cat se ia; le genereaza banca din
# graficul creditului. Detectia intreaba „e neobisnuit pentru el?", iar la o
# miscare pe care nu el o face intrebarea nu are inteles.
MISCARE_CREDIT = re.compile(
    r"^\s*(rata\s+\d+\s*/\s*\d+\s+credit"
    r"|rambursare\s+anticipata\s+(integrala|partiala)\s+credit)\s*$",
    re.IGNORECASE,
)


def e_miscare_de_credit(descriere: str | None) -> bool:
    """Randul e o rata sau o rambursare generata de banca, nu o plata a omului."""
    return bool(descriere) and MISCARE_CREDIT.match(descriere) is not None


@dataclass(frozen=True, slots=True)
class Plata:
    id: str
    moment: datetime
    suma: float
    valuta: str
    comerciant: str
    iesire: bool
    # De unde a venit plata. Null pentru tot ce s-a intamplat inaintea 0050 si
    # pentru miscarile generate de sistem (rate, dobanzi).
    ip: str | None = None


def normalizeaza_comerciant(descriere: str | None) -> str:
    """Descrierile contin des coduri si numere de referinta care fac fiecare plata
    sa para unica. Le scoatem, ca sa putem grupa dupa acelasi comerciant."""
    if not descriere:
        return "necunoscut"
    text = CIFRE_LUNGI.sub("", descriere.lower().strip())
    text = SPATII.sub(" ", text).strip(" -_/")
    text = MARCAJE_REFERINTA.sub("", text).strip(" -_/")
    return text or "necunoscut"


def comerciant_pentru_om(descriere: str | None) -> str:
    """Numele comerciantului asa cum se scrie intr-un text citit de un om.

    `normalizeaza_comerciant` e facut pentru grupare, deci trece totul prin
    litere mici — bun ca sa stim ca „Kaufland ref 123" si „KAUFLAND ref 456"
    sunt acelasi loc, dar intr-o scrisoare catre client „plata la kaufland"
    arata neingrijit. Aici se taie doar codul de referinta si se pastreaza
    scrierea originala: „Kaufland ref 99929175" ramane „Kaufland".

    Codurile se scot fiindca pentru omul care citeste sunt zgomot: nu-l ajuta
    sa-si aminteasca plata si fac fraza de doua ori mai lunga.
    """
    if not descriere:
        return "necunoscut"
    text = CIFRE_LUNGI.sub("", descriere.strip())
    text = SPATII.sub(" ", text).strip(" -_/")
    text = MARCAJE_REFERINTA.sub("", text).strip(" -_/")
    return text or "necunoscut"


def normalizeaza(randuri: list[dict], user_id: UUID) -> list[Plata]:
    """Randurile brute, ca plati.

    Miscarile de credit se lasa afara aici, in punctul comun, nu la fiecare
    apelant: si detectia, si raportul, si antrenarea modelului trebuie sa vada
    aceeasi realitate. Detectia venitului (app/credit/venit.py) nu e atinsa —
    ea se uita doar la incasari, iar ratele sunt iesiri.
    """
    plati: list[Plata] = []
    for rand in randuri:
        if e_miscare_de_credit(rand.get("descriere")):
            continue
        try:
            moment = datetime.fromisoformat(str(rand["creat_la"]).replace("Z", "+00:00"))
        except ValueError:
            continue
        plati.append(
            Plata(
                id=str(rand["id"]),
                moment=moment,
                suma=float(rand["suma"]),
                valuta=rand.get("valuta", "RON"),
                comerciant=normalizeaza_comerciant(rand.get("descriere")),
                iesire=str(rand.get("id_user_send")) == str(user_id),
                ip=(rand.get("ip") or None),
            )
        )
    return sorted(plati, key=lambda p: p.moment)


FEREASTRA_RAFALA = 86400.0  # secunde; cate plati la acelasi comerciant intr-o zi


def vector(plata: Plata, istoric: list[Plata], toate: list[Plata] | None = None) -> list[float]:
    """Trasaturile pe care le vede modelul.

    Ordinea conteaza: acelasi vector trebuie produs la antrenare si la inferenta.

    `istoric` sunt platile la acelasi comerciant, `toate` sunt toate platile de
    iesire ale utilizatorului. Din amandoua se folosesc numai cele dinaintea
    platii evaluate: la inferenta viitorul oricum nu exista, iar la antrenare
    l-am da modelului un avantaj pe care nu-l va avea in productie.

    Doua trasaturi se uita dincolo de comerciantul curent, pentru ca fara ele
    tiparele care conteaza raman invizibile:

    - `suma / mediana generala` — un sir de plati mici la un comerciant nou isi
      trage singur mediana in jos, deci raportat la el insusi pare normal. Fata
      de cat cheltuie omul de obicei, nu mai pare.
    - `plati in ultimele 24h` — patru plati intr-o zi la un magazin vizitat
      saptamanal e un ritm anormal, chiar daca fiecare suma in parte e obisnuita.

    Ziua din luna, ziua saptamanii si numarul de plati anterioare au fost scoase
    dupa masuratori: raspund la "cat de rar e comerciantul", nu la "cat de
    neobisnuita e plata". IsolationForest alege dimensiunea de taiere la
    intamplare, deci fiecare trasatura fara legatura cu intrebarea fura din
    taieturile utile. Pe setul de testare, scoaterea lor a dus semnalarile
    corecte de la 0 din 8 la 5 din 8.
    """
    anterioare = [p for p in istoric if p.moment < plata.moment]
    sume = [p.suma for p in anterioare]
    mediana_comerciant = _mediana(sume) if sume else plata.suma

    referinta = toate if toate is not None else istoric
    sume_generale = [p.suma for p in referinta if p.moment < plata.moment]
    mediana_generala = _mediana(sume_generale) if sume_generale else plata.suma

    zile_de_la_ultima = (
        (plata.moment - anterioare[-1].moment).total_seconds() / 86400 if anterioare else -1.0
    )
    in_24h = sum(
        1
        for p in anterioare
        if (plata.moment - p.moment).total_seconds() <= FEREASTRA_RAFALA
    )

    return [
        plata.suma,
        plata.suma / mediana_comerciant if mediana_comerciant else 1.0,
        plata.suma / mediana_generala if mediana_generala else 1.0,
        zile_de_la_ultima,
        float(in_24h),
        # Locul: platile de la un IP nemaivazut. Se uita la toate platile
        # omului, nu doar la cele de la acest comerciant — un loc nou e nou
        # indiferent unde plateste.
        loc_nou(plata, referinta),
    ]


def loc_nou(plata: Plata, referinta: list[Plata]) -> float:
    """1.0 daca plata vine dintr-un loc de unde omul n-a mai platit.

    Se compara IP-ul cu cele din platile lui anterioare, nu cu ale altcuiva:
    intrebarea e „e neobisnuit PENTRU EL", ca peste tot in modulul asta.

    Lipsa IP-ului intoarce 0.0, nu o valoare-santinela separata. Distinctia
    conteaza: o a treia valoare ar fi insemnat „loc necunoscut" ca si cum ar fi
    un fapt despre plata, cand de fapt e o lipsa a noastra — iar pe datele de
    azi, unde aproape nimic n-are IP, santinela ar fi devenit coloana dominanta
    si ar fi impins modelul sa taie dupa ea.
    """
    if not plata.ip:
        return 0.0

    vazute = {p.ip for p in referinta if p.ip and p.moment < plata.moment}
    if not vazute:
        # Primul IP inregistrat al omului nu e „nou": nu exista cu ce sa fie
        # comparat. Altfel fiecare client ar fi semnalat la prima plata de dupa
        # pornirea capturarii.
        return 0.0

    return 0.0 if plata.ip in vazute else 1.0


def _mediana(valori: list[float]) -> float:
    if not valori:
        return 0.0
    ordonate = sorted(valori)
    mijloc = len(ordonate) // 2
    if len(ordonate) % 2:
        return ordonate[mijloc]
    return (ordonate[mijloc - 1] + ordonate[mijloc]) / 2


def mediana(valori: list[float]) -> float:
    return _mediana(valori)


def deviatie_absoluta_mediana(valori: list[float]) -> float:
    """MAD — masura de imprastiere care nu e trasa de o singura plata uriasa,
    spre deosebire de deviatia standard."""
    if not valori:
        return 0.0
    med = _mediana(valori)
    return _mediana([abs(v - med) for v in valori])
