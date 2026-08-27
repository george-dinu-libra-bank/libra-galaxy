import io
import logging
import re
from collections import Counter

import numpy as np
import pytesseract
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# CNP romanesc: prima cifra 1-8 (sex+secol), urmata de 12 cifre.
CNP_REGEX = re.compile(r"[1-8]\d{12}")

# Moduri de segmentare Tesseract incercate pe rand: buletinul are text
# imprastiat (poza, etichete, cifre), nu un bloc uniform, deci un singur PSM
# rateaza des. 6 = bloc uniform, 11 = text rasfirat, 4 = coloana unica, 3 = auto.
PSM_MODURI = ("6", "11", "4", "3")

# Pentru text curgator (adeverinta de venit) se folosesc doar modurile de bloc:
# 11 ("text rasfirat") rupe randurile unei adeverinte in bucati si strica
# vecinatatea dintre cuvantul "net" si suma de langa el, care e tot ce conteaza
# acolo. 6 = bloc uniform, 4 = coloana unica.
PSM_TEXT = ("6", "4")

# Pentru cautarea etichetei "CNP" se citeste CU litere, deci doua treceri in
# plus. Doar 6 si 11: eticheta si numarul stau pe acelasi rand, iar modurile
# astea pastreaza randul intact.
PSM_ETICHETA = ("6", "11")

# Eticheta de langa numar pe buletin. `\b` ca sa nu se agate de alte cuvinte.
ETICHETA_CNP = re.compile(r"\bCNP\b", re.IGNORECASE)

# Pachetul tesseract-ocr-ron e instalat in Dockerfile de la inceput, dar
# `extrage_cnp` nu il foloseste: pe cifre, limba nu ajuta. Pe text conteaza —
# fara el, Tesseract citeste diacriticele ca semne aleatorii.
LIMBA = "ron"


def _scaleaza(imagine: Image.Image) -> Image.Image:
    latura_scurta = min(imagine.size)
    if latura_scurta >= 1000:
        return imagine
    factor = 1000 / latura_scurta
    return imagine.resize(
        (int(imagine.width * factor), int(imagine.height * factor)), Image.Resampling.LANCZOS
    )


def _variante_preprocesare(imagine: Image.Image) -> list[Image.Image]:
    """
    Cateva variante ale aceleiasi poze, ca sa creasca sansele OCR pe un
    buletin (fond colorat, hologram, text mic): grayscale simplu si o
    binarizare Otsu (separa mai clar textul negru de fond).
    """
    gri = _scaleaza(ImageOps.grayscale(imagine))
    variante = [ImageOps.autocontrast(gri, cutoff=2)]

    try:
        import cv2

        array = np.array(gri)
        _, binarizata = cv2.threshold(array, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        variante.append(Image.fromarray(binarizata))
    except Exception:
        logger.exception("extrage_cnp: binarizarea Otsu a esuat, continui doar cu grayscale")

    return variante


# Constantele cifrei de control a CNP-ului (standardul romanesc).
CONTROL_CNP = "279146358279"

# Peste atatea cifre pe un rand nu mai e campul CNP, ci banda MRZ de la baza
# buletinului. Un rand cu CNP are 13 cifre, plus eventual cate ceva alaturi
# (seria, o data); un rand de MRZ are 30+. Pe buletinele vechi, banda aia e
# principala sursa de CNP-uri false: contine data nasterii si seria, deci
# produce siruri de 13 cifre care arata exact ca un CNP.
MAX_CIFRE_PE_RAND = 18


def cifra_control_valida(cnp: str) -> bool:
    """
    Verifica cifra de control a unui CNP.

    Aceeasi regula ca validCnp din frontend (lib/validare.ts). Aici nu e
    folosita ca sa RESPINGA, ci ca sa ALEAGA intre mai multi candidati —
    vezi extrage_cnp.
    """
    if len(cnp) != 13 or not cnp.isdigit():
        return False

    suma = sum(int(cnp[i]) * int(CONTROL_CNP[i]) for i in range(12))
    rest = suma % 11
    return (1 if rest == 10 else rest) == int(cnp[12])


def _candidati_langa_eticheta(imagine: Image.Image) -> set[str]:
    """
    CNP-urile gasite pe randul pe care scrie chiar "CNP".

    E singurul indiciu care spune ce INSEAMNA numarul, si de aceea merita cele
    doua treceri de OCR in plus: restul extragerii ruleaza cu
    `tessedit_char_whitelist=0123456789`, care arunca toate literele — deci si
    eticheta. Fara ea, orice sir de 13 cifre de pe buletin arata la fel:
    seria din banda MRZ, datele de valabilitate lipite intre ele, numarul
    documentului.

    Se accepta si randul urmator: pe unele formate eticheta sta deasupra
    numarului, nu in stanga lui.
    """
    gasite: set[str] = set()

    for psm in PSM_ETICHETA:
        try:
            text = pytesseract.image_to_string(imagine, lang=LIMBA, config=f"--psm {psm}")
        except Exception:
            logger.exception("extrage_cnp: trecerea cu litere a esuat pentru psm=%s", psm)
            continue

        linii = text.splitlines()
        for i, linie in enumerate(linii):
            if not ETICHETA_CNP.search(linie):
                continue

            vecinatate = [linie]
            if i + 1 < len(linii):
                vecinatate.append(linii[i + 1])

            for rand in vecinatate:
                gasite.update(CNP_REGEX.findall(re.sub(r"[^0-9]", "", rand)))

    return gasite


def _candidati_din_text(text: str) -> list[tuple[str, bool]]:
    """
    Perechi (candidat, din_zona_vizuala), cate una pentru fiecare potrivire.

    Cauta pe fiecare linie, dupa ce ii scoatem spatiile interne — Tesseract
    baga uneori spatii in mijlocul unui numar, dar rareori rupe randul.

    `din_zona_vizuala` e False pentru randurile prea dense ca sa fie altceva
    decat MRZ. Nu se arunca de tot, doar se prefera celelalte: daca poza prinde
    doar banda de jos, tot e mai bine decat nimic.
    """
    candidati: list[tuple[str, bool]] = []

    for linie in text.splitlines():
        linie_compacta = re.sub(r"[^0-9]", "", linie)
        din_zona_vizuala = len(linie_compacta) <= MAX_CIFRE_PE_RAND

        for potrivire in CNP_REGEX.findall(linie_compacta):
            candidati.append((potrivire, din_zona_vizuala))

    return candidati


def extrage_cnp(imagine_bytes: bytes) -> tuple[str | None, float]:
    """
    Citeste textul de pe poza buletinului prin Tesseract si extrage CNP-ul.

    Incearca mai multe variante de preprocesare x moduri de segmentare si
    aduna toate potrivirile de 13 cifre gasite.

    Alegerea dintre candidati se face in ordinea asta:

      1. sta pe randul pe care scrie "CNP" — singurul indiciu care spune ce
         INSEAMNA numarul, nu doar cum arata;
      2. nu vine din banda MRZ de la baza buletinului;
      3. cifra de control valida, ca sa alegem intre citiri gresite ale
         aceluiasi camp;
      4. cel mai frecvent, ca inainte.

    Frecventa singura nu ajungea deloc. Un buletin e plin de siruri de 13 cifre
    care arata ca un CNP: banda MRZ (contine seria si data nasterii), datele de
    valabilitate lipite intre ele ("06.01.17-02.09.2077" -> 6011702092077),
    numarul documentului. Toate au fost vazute castigand in fata CNP-ului real.

    Ordinea are doua lectii platite:

      * eticheta bate orice euristica de forma, si de aceea merita cele doua
        treceri de OCR in plus — restul ruleaza cu whitelist doar pe cifre,
        care arunca tocmai eticheta;
      * zona bate cifra de control, nu invers: pe un buletin-model, sirul scos
        din MRZ avea intamplator cifra de control valida (se nimereste in 1 caz
        din 11), iar CNP-ul tiparit nu, fiind inventat.

    Incredere = frecventa candidatului castigator / total incercari — mare
    cand toate incercarile converg spre acelasi CNP, mica cand rezultatele
    sunt imprastiate. Frontendul valideaza oricum cifra de control inca o data
    si lasa omul sa corecteze.
    """
    try:
        imagine = Image.open(io.BytesIO(imagine_bytes))
        imagine.load()
    except Exception:
        logger.warning("extrage_cnp: imagine ilizibila")
        return None, 0.0

    toate_potrivirile: list[tuple[str, bool]] = []
    incercari = 0

    variante = _variante_preprocesare(imagine)

    # Trecerea cu litere, o singura data si doar pe prima varianta: e scumpa,
    # iar rolul ei e doar sa spuna care numar sta langa eticheta.
    langa_eticheta = _candidati_langa_eticheta(variante[0]) if variante else set()

    for varianta in variante:
        for psm in PSM_MODURI:
            incercari += 1
            try:
                text = pytesseract.image_to_string(varianta, config=f"--psm {psm} -c tessedit_char_whitelist=0123456789")
            except Exception:
                logger.exception("extrage_cnp: tesseract a esuat pentru psm=%s", psm)
                continue
            toate_potrivirile.extend(_candidati_din_text(text))

    if not toate_potrivirile and not langa_eticheta:
        return None, 0.0

    numaratoare = Counter(cnp for cnp, _ in toate_potrivirile)

    # Trecerea cu litere poate gasi un CNP pe care cea cu whitelist l-a ratat
    # (alt PSM, alta segmentare). Intra in cursa cu frecventa 1, dar cu cel mai
    # tare semnal de partea lui.
    for cnp in langa_eticheta:
        numaratoare.setdefault(cnp, 0)
        numaratoare[cnp] = max(numaratoare[cnp], 1)
    # Un candidat conteaza ca "din zona vizuala" daca a aparut asa macar o
    # data: o singura incercare de OCR care l-a gasit langa eticheta CNP
    # spune mai mult decat zece care l-au gasit in banda de jos.
    din_zona_vizuala = {cnp for cnp, vizuala in toate_potrivirile if vizuala}

    cnp_castigator = max(
        numaratoare,
        key=lambda cnp: (
            cnp in langa_eticheta,
            cnp in din_zona_vizuala,
            cifra_control_valida(cnp),
            numaratoare[cnp],
        ),
    )

    incredere = min(1.0, numaratoare[cnp_castigator] / max(incercari, 1))

    return cnp_castigator, incredere


def extrage_text(imagine_bytes: bytes) -> str:
    """
    Tot textul citibil dintr-o poza, pentru documente scrise (adeverinta de venit).

    Nu se poate folosi `extrage_cnp` pentru asta, si nu e o chestiune de
    parametri: acolo se trimite `tessedit_char_whitelist=0123456789`, care ii
    interzice lui Tesseract sa intoarca vreo litera. Un document din care nu poti
    citi cuvantul "net" nu se poate interpreta — suma bruta si cea neta arata la
    fel cand nu vezi eticheta de langa ele.

    Se intorc toate variantele lipite, nu doar cea mai buna: preprocesarile
    esueaza pe bucati diferite ale aceleiasi poze, iar un numar pierdut de
    binarizare poate fi prins de grayscale. Parserul cauta oricum potriviri, deci
    text in plus il incetineste, nu il induce in eroare.
    """
    try:
        imagine = Image.open(io.BytesIO(imagine_bytes))
        imagine.load()
    except Exception:
        logger.warning("extrage_text: imagine ilizibila")
        return ""

    bucati: list[str] = []
    for varianta in _variante_preprocesare(imagine):
        for psm in PSM_TEXT:
            try:
                bucati.append(
                    pytesseract.image_to_string(varianta, lang=LIMBA, config=f"--psm {psm}")
                )
            except Exception:
                logger.exception("extrage_text: tesseract a esuat pentru psm=%s", psm)

    return "\n".join(bucata.strip() for bucata in bucati if bucata.strip())
