"""Motivarea deciziei, in limbaj natural.

Ordinea e importanta si e inversa fata de cum se construiesc de obicei lucrurile
astea: **textul determinist e implicit, modelul de limbaj e optional.**

Motivul nu e economia de tokeni, ci ca decizia de creditare trebuie sa poata fi
comunicata si cand Foundry nu raspunde, si cand cheia nu e configurata — la fel
ca detectia de neregularitati, care merge fara ANTHROPIC_API_KEY (alerte.py).
Un client caruia i se respinge cererea trebuie sa afle de ce, nu sa primeasca o
eroare de infrastructura.

Modelul nu decide si nu recalculeaza nimic: primeste decizia luata si o rescrie
mai cald. Daca da gres, ramane textul de aici.
"""

from __future__ import annotations

INTRO = {
    "aprobat": "Felicitări, cererea ta a fost aprobată.",
    "analiza_manuala": "Cererea ta a intrat în analiză manuală.",
    "respins": "Din păcate, nu putem aproba cererea în forma actuală.",
}

INCHEIERE = {
    "aprobat": "Oferta e valabilă 7 zile — o poți accepta din aplicație.",
    "analiza_manuala": "Un coleg o verifică și primești un răspuns în cel mult două zile lucrătoare.",
    "respins": "Poți relua cererea oricând, cu o sumă mai mică sau o perioadă mai lungă.",
}

# Îndrumarea depinde de ce anume a blocat cererea, nu doar de verdict.
#
# Prima versiune închidea orice respingere cu „încearcă o sumă mai mică". Pentru
# cineva blocat de identitatea neverificată, sfatul era pur și simplu greșit: nicio
# sumă nu i-ar fi rezolvat problema. Un mesaj care trimite omul într-o direcție
# inutilă e mai rău decât unul generic — îl face să încerce de trei ori degeaba.
INDRUMARE_DUPA_MOTIV = {
    "identitate_neverificata":
        "Verifică-ți identitatea din Setări — durează un minut, cu buletinul și un selfie. "
        "După aceea poți relua cererea.",
    "venit_sub_minim":
        "Venitul net lunar e criteriul care nu e îndeplinit. Dacă ai și alte venituri "
        "eligibile, încarcă o adeverință și reluăm analiza.",
    "grad_indatorare_depasit":
        "Rata ar depăși cât îți permiți lunar. Încearcă o sumă mai mică sau o perioadă "
        "mai lungă — ambele scad rata.",
    "vechime_angajator_insuficienta":
        "Îți mai trebuie puțină vechime la angajatorul actual. Revino după ce o "
        "împlinești.",
    "vechime_venituri_insuficienta":
        "Nu avem încă suficient istoric de venituri. Revino după câteva luni de "
        "încasări în cont.",
    "suma_in_afara_limitelor":
        "Alege o sumă din intervalul produsului și reia cererea.",
    "perioada_in_afara_limitelor":
        "Alege o perioadă din intervalul produsului și reia cererea.",
    "cnp_invalid":
        "Nu am putut citi datele de identitate de pe profil. Contactează suportul.",
}


def _indrumare(decizie: str, motive: list[dict]) -> str:
    """Primul motiv pentru care avem un sfat concret; altfel, textul generic.

    Ordinea din `motive` e cea din reguli.py, deci stabilă — doi clienți cu
    aceleași probleme primesc același sfat.
    """
    if decizie == "respins":
        for motiv in motive:
            indrumare = INDRUMARE_DUPA_MOTIV.get(motiv["cod"])
            if indrumare:
                return indrumare
    return INCHEIERE.get(decizie, "")


# Cand lipseste dovada de venit, sfatul generic („un coleg o verifica") e
# adevarat dar inutil: omul n-are ce face cu el. Aici stie exact ce sa faca, si
# de ce l-ar ajuta.
INDRUMARE_DOCUMENT = (
    "Ca să mergem mai departe avem nevoie de o dovadă a venitului. Încarcă o adeverință "
    "de venit din aplicație — o citim automat, iar un coleg confirmă suma."
)


def explicatie_determinista(
    decizie: str,
    motive: list[dict],
    factori: list[dict],
    scor: int | None,
    cere_document: bool = False,
) -> str:
    """Explicatia construita din datele deciziei, fara model de limbaj."""
    parti = [INTRO.get(decizie, "")]

    if motive:
        # La respingere pe criterii hard, motivele sunt tot ce conteaza: sunt
        # concrete si actionabile ("venitul minim e 3.000 RON"), spre deosebire
        # de un scor.
        parti.append(_lista(motiv["text"] for motiv in motive))
    elif factori:
        parti.append(f"Punctajul de evaluare este {scor} din 100.")
        slabe = _cele_mai_slabe(factori)
        if slabe and decizie != "aprobat":
            parti.append("Au cântărit cel mai mult:")
            parti.append(_lista(factor["explicatie"] for factor in slabe))
        elif slabe:
            parti.append("Au contat în favoarea ta: " + ", ".join(
                factor["explicatie"].rstrip(".").lower() for factor in _cele_mai_bune(factori)
            ) + ".")

    # Cererea de document bate indrumarea generica: e mai concreta si e singura
    # pe care omul o poate urma imediat.
    parti.append(INDRUMARE_DOCUMENT if cere_document else _indrumare(decizie, motive))
    return "\n\n".join(parte for parte in parti if parte)


def _lista(texte) -> str:
    return "\n".join(f"• {text}" for text in texte)


def _cele_mai_slabe(factori: list[dict], cate: int = 3) -> list[dict]:
    """Factorii cu cel mai mare punctaj pierdut — ce ar trebui sa schimbe omul.

    Se ordoneaza dupa puncte pierdute in absolut, nu dupa procent: un factor de
    30 de puncte din care s-au luat 10 conteaza mai mult decat unul de 10 puncte
    luat integral, chiar daca al doilea arata mai rau procentual.
    """
    pierdute = [f for f in factori if f["maxim"] - f["puncte"] > 0]
    return sorted(pierdute, key=lambda f: f["maxim"] - f["puncte"], reverse=True)[:cate]


def _cele_mai_bune(factori: list[dict], cate: int = 2) -> list[dict]:
    return sorted(factori, key=lambda f: f["puncte"], reverse=True)[:cate]
