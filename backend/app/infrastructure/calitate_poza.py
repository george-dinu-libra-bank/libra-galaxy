"""
Verificarea calitatii unei poze inainte sa ajunga la DeepFace sau la OCR.

Rostul modulului e sa transforme un esec mut intr-un mesaj concret. Pana acum
singurul semnal despre o poza proasta venea din face_match.py, unde
`enforce_detection=True` arunca ValueError si contul ateriza pe
'pending_review' — corect, dar omul nu afla niciodata *de ce*. Un selfie
negru, ars de lumina sau miscat arata identic cu unul bun in interfata.

Aici nu se decide nimic despre identitate: doar se masoara poza (expunere,
claritate, contrast, cate fete se vad) si se intorc mesaje gata de afisat.
"""

import io
import logging
from dataclasses import dataclass

import numpy as np
from PIL import Image

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Problema:
    cod: str
    mesaj: str
    blocanta: bool


@dataclass(frozen=True)
class RaportCalitate:
    acceptabila: bool
    probleme: list[Problema]
    # Doar pentru log, ca pragurile sa se poata calibra pe camere reale.
    # Nu pleaca spre client: ruta e neautentificata, iar numerele brute n-ar
    # ajuta pe nimeni in afara de cine vrea sa ghiceasca ce trece filtrul.
    metrici: dict[str, float]


# Fractiunea de pixeli complet infundati / complet arsi de la care poza e
# compromisa chiar daca media pare rezonabila (contrejour clasic: fata in
# umbra pe un fundal de fereastra).
PRAG_UMBRE = 0.35
PRAG_LUMINI = 0.25

# Deviatia standard sub care poza e "in ceata" — lumina difuza, fara contrast.
PRAG_CONTRAST = 25.0

# Cat de "ars" trebuie sa fie cel mai luminos bloc dintr-o poza de buletin ca
# sa fie reflexie, nu supraexpunere generala (vezi _reflexie_locala).
PRAG_REFLEXIE = 0.9

# Sub atat, Tesseract n-are ce citi de pe buletin.
LATURA_MIN_DOCUMENT = 800


def _in_array(imagine_bytes: bytes) -> np.ndarray:
    imagine = Image.open(io.BytesIO(imagine_bytes)).convert("RGB")
    return np.array(imagine)


def _luma(arr: np.ndarray) -> np.ndarray:
    """Luminanta Rec.709 — mai apropiata de perceptia ochiului decat media RGB."""
    return arr[..., :3].astype(np.float32) @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


def _expunere(gri: np.ndarray) -> tuple[float, float, float]:
    """(medie, fractiune de pixeli sub 16, fractiune de pixeli peste 245)."""
    return float(gri.mean()), float(np.mean(gri < 16)), float(np.mean(gri > 245))


def _contrast(gri: np.ndarray) -> float:
    return float(gri.std())


def _claritate(gri: np.ndarray) -> float | None:
    """
    Varianta Laplacianului: mica pe o poza miscata sau focalizata gresit.

    cv2 se importa lazy, in try/except, ca in ocr.py: daca lipseste sau crapa,
    pierdem doar verificarea de blur, nu tot raportul.
    """
    try:
        import cv2

        return float(cv2.Laplacian(gri.astype(np.float64), cv2.CV_64F).var())
    except Exception:
        logger.exception("calitate_poza: nu am putut calcula claritatea (cv2)")
        return None


def _reflexie_locala(gri: np.ndarray, blocuri: int = 16) -> float:
    """
    Cel mai "ars" bloc din poza, ca fractiune de pixeli albi.

    Un procent global de pixeli albi nu distinge o poza supraexpusa in
    intregime de o pata de blit pe folia buletinului. O grila grosiera da
    exact diferenta care conteaza: cat de *concentrata* e lumina.
    """
    inaltime, latime = gri.shape
    pas_y = max(1, inaltime // blocuri)
    pas_x = max(1, latime // blocuri)

    maxim = 0.0
    for y in range(0, inaltime - pas_y + 1, pas_y):
        for x in range(0, latime - pas_x + 1, pas_x):
            maxim = max(maxim, float(np.mean(gri[y : y + pas_y, x : x + pas_x] >= 250)))
    return maxim


def _detecteaza_fete(arr: np.ndarray) -> list[dict] | None:
    """
    Fetele gasite de yunet, sau None cand detectorul nu a putut rula deloc.

    Distinctia conteaza: None inseamna "nu stim" si sarim peste verificarile
    de fata, pe cand [] inseamna "am cautat si nu e nicio fata". Fara ea, o
    picare a TensorFlow i-ar spune userului ca nu i se vede fata.

    Capcana: cu enforce_detection=False, DeepFace NU intoarce lista goala cand
    nu gaseste nimic — intoarce o pseudo-fata care acopera toata imaginea, cu
    confidence 0. Fara filtrul de mai jos, cazul 'fara_fata' nu s-ar declansa
    niciodata.

    Importul e lazy, ca in face_match.py: DeepFace trage TensorFlow dupa el.
    """
    setari = get_settings()

    try:
        from deepface import DeepFace

        fete = DeepFace.extract_faces(
            img_path=arr,
            detector_backend=setari.identity_detector_backend,
            enforce_detection=False,
            # Nu ne trebuie decupajul aliniat, doar coordonatele — align=True
            # ar roti degeaba fiecare fata.
            align=False,
        )
    except Exception:
        logger.exception("calitate_poza: detectia fetelor a esuat")
        return None

    prag = setari.calitate_incredere_detectie_min
    return [fata for fata in fete if float(fata.get("confidence") or 0.0) >= prag]


def _decupeaza(arr: np.ndarray, zona: dict) -> np.ndarray:
    x = max(0, int(zona.get("x", 0)))
    y = max(0, int(zona.get("y", 0)))
    latime = int(zona.get("w", 0))
    inaltime = int(zona.get("h", 0))

    if latime <= 0 or inaltime <= 0:
        return arr

    decupaj = arr[y : y + inaltime, x : x + latime]
    return decupaj if decupaj.size else arr


def _arie_relativa(zona: dict, arr: np.ndarray) -> float:
    total = float(arr.shape[0] * arr.shape[1])
    if total <= 0:
        return 0.0
    return (float(zona.get("w", 0)) * float(zona.get("h", 0))) / total


def _raport(probleme: list[Problema], metrici: dict[str, float]) -> RaportCalitate:
    return RaportCalitate(
        acceptabila=not any(problema.blocanta for problema in probleme),
        probleme=probleme,
        metrici=metrici,
    )


def _ilizibila(mesaj: str) -> RaportCalitate:
    return _raport([Problema("ilizibila", mesaj, True)], {})


def analizeaza_selfie(imagine_bytes: bytes) -> RaportCalitate:
    """
    Problemele se intorc in ordinea importantei, nu in ordinea in care se
    calculeaza: o poza neagra n-are nicio fata detectabila, dar mesajul util
    e "e prea intuneric", nu "nu gasim nicio fata".
    """
    try:
        arr = _in_array(imagine_bytes)
    except Exception:
        logger.warning("analizeaza_selfie: imagine ilizibila")
        return _ilizibila("Nu am putut citi poza. Încearcă din nou.")

    setari = get_settings()
    fete = _detecteaza_fete(arr)
    zona = fete[0]["facial_area"] if fete else None

    # Expunerea si claritatea se masoara pe fata, nu pe toata poza: un fundal
    # alb stralucitor "compenseaza" statistic o fata lasata complet in umbra,
    # iar poza ar trece desi ArcFace n-are ce compara. Fara fata detectata
    # cadem pe imaginea intreaga, ca sa putem totusi spune "e prea intuneric".
    tinta = _decupeaza(arr, zona) if zona else arr
    gri = _luma(tinta)

    medie, umbre, lumini = _expunere(gri)
    claritate = _claritate(gri)
    contrast = _contrast(gri)

    probleme: list[Problema] = []

    if medie < setari.calitate_luma_min or umbre > PRAG_UMBRE:
        probleme.append(
            Problema(
                "prea_intunecata",
                "Poza e prea întunecată. Aprinde o lumină sau mută-te lângă o fereastră.",
                True,
            )
        )
    elif medie > setari.calitate_luma_max or lumini > PRAG_LUMINI:
        probleme.append(
            Problema(
                "prea_luminoasa",
                "E prea multă lumină — fața ta e arsă de lumină. "
                "Evită să ai soarele sau becul direct în spate.",
                True,
            )
        )

    # Pe o poza cu expunerea stricata, claritatea si contrastul nu mai
    # inseamna nimic (un dreptunghi negru are varianta zero, deci ar iesi si
    # "neclara", si "stearsa"). Un singur mesaj, cel adevarat.
    expunere_stricata = bool(probleme)

    if fete is not None:
        if not fete:
            probleme.append(
                Problema(
                    "fara_fata",
                    "Nu găsim nicio față în poză. Privește direct spre cameră, cu tot chipul în cadru.",
                    True,
                )
            )
        elif len(fete) > 1:
            probleme.append(
                Problema(
                    "mai_multe_fete",
                    "Sunt mai multe fețe în poză. Trebuie să fii singur în cadru.",
                    True,
                )
            )
        elif _arie_relativa(zona or {}, arr) < setari.calitate_arie_fata_min:
            probleme.append(
                Problema("fata_prea_mica", "Ești prea departe. Apropie-te de cameră.", True)
            )

    if not expunere_stricata:
        if claritate is not None and claritate < setari.calitate_blur_min_selfie:
            probleme.append(
                Problema(
                    "neclara",
                    "Poza e neclară. Ține telefonul nemișcat și încearcă din nou.",
                    True,
                )
            )
        if contrast < PRAG_CONTRAST:
            probleme.append(
                Problema(
                    "contrast_slab",
                    "Poza pare ștearsă. Dacă poți, caută un loc cu lumină mai bună.",
                    False,
                )
            )

    metrici = {
        "medie_luma": round(medie, 1),
        "umbre": round(umbre, 3),
        "lumini": round(lumini, 3),
        "contrast": round(contrast, 1),
        "fete": float(len(fete)) if fete is not None else -1.0,
        "arie_fata": round(_arie_relativa(zona, arr), 3) if zona else 0.0,
    }
    if claritate is not None:
        metrici["claritate"] = round(claritate, 1)

    return _raport(probleme, metrici)


def analizeaza_document(imagine_bytes: bytes) -> RaportCalitate:
    """
    Buletinul, nu o fata: aici conteaza ca Tesseract sa poata citi CNP-ul, nu
    ca ArcFace sa poata compara. De aceea nu se detecteaza nicio fata (poza de
    pe buletin e mica si tiparita, ar da rezultate aiurea), pragul de blur e
    mai strict, si apar doua verificari proprii — reflexia blitului in folie
    si rezolutia prea mica.
    """
    try:
        arr = _in_array(imagine_bytes)
    except Exception:
        logger.warning("analizeaza_document: imagine ilizibila")
        return _ilizibila("Nu am putut citi poza. Încearcă alt fișier.")

    setari = get_settings()
    gri = _luma(arr)

    medie, umbre, lumini = _expunere(gri)
    claritate = _claritate(gri)
    reflexie = _reflexie_locala(gri)
    latura_lunga = max(arr.shape[0], arr.shape[1])

    probleme: list[Problema] = []

    if medie < setari.calitate_luma_min or umbre > PRAG_UMBRE:
        probleme.append(
            Problema(
                "prea_intunecata",
                "Poza buletinului e prea întunecată — nu se disting cifrele. "
                "Mută-te într-un loc mai luminat.",
                True,
            )
        )
    elif medie > setari.calitate_luma_max or lumini > PRAG_LUMINI:
        probleme.append(
            Problema(
                "prea_luminoasa",
                "E prea multă lumină pe buletin și textul se pierde. Mai stinge din lumină.",
                True,
            )
        )

    expunere_stricata = bool(probleme)

    if not expunere_stricata:
        if reflexie > PRAG_REFLEXIE:
            probleme.append(
                Problema(
                    "reflexie",
                    "Se reflectă lumina în buletin. Înclină-l puțin sau stinge blițul.",
                    True,
                )
            )
        if claritate is not None and claritate < setari.calitate_blur_min_document:
            probleme.append(
                Problema(
                    "neclara",
                    "Poza buletinului e neclară — CNP-ul nu se poate citi. Ține telefonul nemișcat.",
                    True,
                )
            )

    if latura_lunga < LATURA_MIN_DOCUMENT:
        probleme.append(
            Problema(
                "rezolutie_mica",
                "Poza e prea mică. Apropie-te, ca buletinul să umple tot cadrul.",
                True,
            )
        )

    metrici = {
        "medie_luma": round(medie, 1),
        "umbre": round(umbre, 3),
        "lumini": round(lumini, 3),
        "reflexie": round(reflexie, 3),
        "latura_lunga": float(latura_lunga),
    }
    if claritate is not None:
        metrici["claritate"] = round(claritate, 1)

    return _raport(probleme, metrici)
