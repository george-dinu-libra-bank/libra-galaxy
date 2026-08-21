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


def _candidati_din_text(text: str) -> list[str]:
    """Cauta pe fiecare linie, dupa ce ii scoatem spatiile interne — Tesseract
    baga uneori spatii in mijlocul unui numar, dar rareori rupe randul."""
    candidati = []
    for linie in text.splitlines():
        linie_compacta = re.sub(r"[^0-9]", "", linie)
        candidati.extend(CNP_REGEX.findall(linie_compacta))
    return candidati


def extrage_cnp(imagine_bytes: bytes) -> tuple[str | None, float]:
    """
    Citeste textul de pe poza buletinului prin Tesseract si extrage CNP-ul.

    Incearca mai multe variante de preprocesare x moduri de segmentare si
    aduna toate potrivirile de 13 cifre gasite; alege cea mai frecventa.
    Incredere = frecventa candidatului castigator / total incercari — mare
    cand toate incercarile converg spre acelasi CNP, mica cand rezultatele
    sunt imprastiate. Cifra de control CNP se valideaza separat (validCnp in
    frontend) — aici ne limitam la formatul brut.
    """
    try:
        imagine = Image.open(io.BytesIO(imagine_bytes))
        imagine.load()
    except Exception:
        logger.warning("extrage_cnp: imagine ilizibila")
        return None, 0.0

    toate_potrivirile: list[str] = []
    incercari = 0

    for varianta in _variante_preprocesare(imagine):
        for psm in PSM_MODURI:
            incercari += 1
            try:
                text = pytesseract.image_to_string(varianta, config=f"--psm {psm} -c tessedit_char_whitelist=0123456789")
            except Exception:
                logger.exception("extrage_cnp: tesseract a esuat pentru psm=%s", psm)
                continue
            toate_potrivirile.extend(_candidati_din_text(text))

    if not toate_potrivirile:
        return None, 0.0

    numaratoare = Counter(toate_potrivirile)
    cnp_castigator, frecventa = numaratoare.most_common(1)[0]
    incredere = min(1.0, frecventa / max(incercari, 1))

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
