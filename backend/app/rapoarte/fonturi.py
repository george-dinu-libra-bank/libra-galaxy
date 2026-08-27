"""Fontul cu diacritice pentru PDF-urile generate cu reportlab.

Helvetica, fontul implicit din reportlab, e codat Latin-1 si nu contine s si t
cu virgula (ș, ț) sau a cu caciula (ă): reportlab deseneaza patrate negre in
locul lor. Cautam un font TrueType care acopera romana si il inregistram o
singura data pe proces.

Modulul a fost desprins din `pdf_raport.py` cand a aparut al doilea document
generat din backend (contractul de credit). Cautarea era deja scrisa acolo si
rezolvata; ce lipsea era un loc din care sa o poata folosi si altcineva.
"""

from __future__ import annotations

import logging
import pathlib

logger = logging.getLogger(__name__)

# DejaVu acopera complet romana si vine cu imaginea Debian a containerului. Daca
# lipseste (backend rulat direct pe Windows), cadem inapoi pe Helvetica:
# documentul iese fara diacritice, dar iese — un PDF lipsa ar fi mai rau decat
# unul urat.
_CAI = (
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("C:/Windows/Fonts/DejaVuSans.ttf", "C:/Windows/Fonts/DejaVuSans-Bold.ttf"),
    # Arial exista pe orice Windows si acopera romana.
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
)

_IMPLICIT = ("Helvetica", "Helvetica-Bold")
_FAMILIE = ("RaportRO", "RaportRO-Bold")

# Rezultatul cautarii, memorat: inregistrarea aceluiasi TTF de doua ori nu e o
# eroare, dar cautarea pe disc la fiecare document ar fi.
_gasit: tuple[str, str] | None = None


def inregistreaza() -> tuple[str, str]:
    """Numele fontului normal si al celui bold, gata de folosit in reportlab."""
    global _gasit

    if _gasit is not None:
        return _gasit

    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    for cale_normal, cale_bold in _CAI:
        if not (pathlib.Path(cale_normal).exists() and pathlib.Path(cale_bold).exists()):
            continue
        try:
            pdfmetrics.registerFont(TTFont(_FAMILIE[0], cale_normal))
            pdfmetrics.registerFont(TTFont(_FAMILIE[1], cale_bold))
            pdfmetrics.registerFontFamily(
                _FAMILIE[0], normal=_FAMILIE[0], bold=_FAMILIE[1]
            )
        except Exception:
            logger.exception("fontul %s nu a putut fi inregistrat", cale_normal)
            continue

        _gasit = _FAMILIE
        return _gasit

    logger.warning(
        "niciun font cu diacritice gasit; PDF-urile ies cu Helvetica, "
        "deci fara diacritice romanesti"
    )
    _gasit = _IMPLICIT
    return _gasit
