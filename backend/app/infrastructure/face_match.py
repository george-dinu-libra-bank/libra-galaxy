import io

import numpy as np
from deepface import DeepFace
from PIL import Image

from app.infrastructure.config import get_settings
from app.infrastructure.logging import obtine_logger

logger = obtine_logger(__name__)


class RezultatVerificare:
    def __init__(self, verified: bool, score: float | None, threshold: float, fata_detectata: bool):
        self.verified = verified
        self.score = score
        self.threshold = threshold
        self.fata_detectata = fata_detectata


def _in_array(imagine_bytes: bytes) -> np.ndarray:
    imagine = Image.open(io.BytesIO(imagine_bytes)).convert("RGB")
    return np.array(imagine)


def verifica_fete(buletin_bytes: bytes, selfie_bytes: bytes) -> RezultatVerificare:
    """
    Compara fata din poza buletinului cu selfie-ul, folosind modelul ArcFace.

    enforce_detection=True: daca DeepFace NU gaseste o fata clara intr-una din
    poze, aruncam intentionat (ValueError) — cu enforce_detection=False,
    DeepFace compara imaginile intregi ca si cum ar fi fete cand nu detecteaza
    niciuna, ceea ce poate produce potriviri false intre persoane complet
    diferite. O poza fara fata detectata trebuie tratata ca 'pending_review',
    nu comparata "pe ghicite".
    """
    setari = get_settings()

    try:
        rezultat = DeepFace.verify(
            img1_path=_in_array(buletin_bytes),
            img2_path=_in_array(selfie_bytes),
            model_name=setari.identity_deepface_model,
            detector_backend=setari.identity_detector_backend,
            enforce_detection=True,
        )
    except ValueError:
        logger.warning("verifica_fete: nu s-a detectat o fata clara intr-una din poze")
        return RezultatVerificare(verified=False, score=None, threshold=0.0, fata_detectata=False)
    except Exception:
        logger.exception("verifica_fete: DeepFace.verify a esuat")
        return RezultatVerificare(verified=False, score=None, threshold=0.0, fata_detectata=False)

    prag = setari.identity_verify_distance_threshold
    distanta = float(rezultat["distance"])
    prag_folosit = float(prag if prag is not None else rezultat["threshold"])
    verificat = bool(distanta <= prag_folosit)

    return RezultatVerificare(
        verified=verificat,
        score=distanta,
        threshold=prag_folosit,
        fata_detectata=True,
    )
