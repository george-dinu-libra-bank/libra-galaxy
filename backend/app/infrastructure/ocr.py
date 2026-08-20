import io
import re
from collections import Counter

import numpy as np
import pytesseract
from PIL import Image, ImageOps

from app.infrastructure.logging import obtine_logger

logger = obtine_logger(__name__)

# CNP romanesc: prima cifra 1-8 (sex+secol), urmata de 12 cifre.
CNP_REGEX = re.compile(r"[1-8]\d{12}")

# Moduri de segmentare Tesseract incercate pe rand: buletinul are text
# imprastiat (poza, etichete, cifre), nu un bloc uniform, deci un singur PSM
# rateaza des. 6 = bloc uniform, 11 = text rasfirat, 4 = coloana unica, 3 = auto.
PSM_MODURI = ("6", "11", "4", "3")


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
