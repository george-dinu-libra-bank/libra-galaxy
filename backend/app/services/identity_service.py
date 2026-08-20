from app.infrastructure.errors import DescarcareImagineError, ScriereRezultatError
from app.infrastructure.face_match import verifica_fete
from app.infrastructure.logging import obtine_logger
from app.infrastructure.ocr import extrage_cnp
from app.repositories import identity_repository
from app.schemas.identity import VerificaIdentitateRequest, VerificaIdentitateResponse

logger = obtine_logger(__name__)

BUCKET_BULETINE = "buletine"
BUCKET_SELFIE = "selfie-uri"


def extrage_cnp_din_buletin(imagine_bytes: bytes) -> tuple[str | None, float]:
    return extrage_cnp(imagine_bytes)


def _descarca(bucket: str, cale: str) -> bytes:
    try:
        return identity_repository.descarca_imagine(bucket, cale)
    except Exception:
        logger.exception("verifica_identitate: descarcare esuata (bucket=%s, cale=%s)", bucket, cale)
        raise DescarcareImagineError(bucket, cale) from None


def verifica_identitate(cerere: VerificaIdentitateRequest) -> VerificaIdentitateResponse:
    buletin_bytes = _descarca(BUCKET_BULETINE, cerere.buletin_path)
    selfie_bytes = _descarca(BUCKET_SELFIE, cerere.selfie_path)

    rezultat = verifica_fete(buletin_bytes, selfie_bytes)

    # Niciodata 'rejected' automat — un scor mic sau o fata nedetectata
    # inseamna revizuire manuala, nu respingere; respingerea e o actiune de
    # admin (viitor).
    status = "verified" if rezultat.verified else "pending_review"

    try:
        identity_repository.inregistreaza_verificare(
            id_user=cerere.user_id,
            buletin_path=cerere.buletin_path,
            selfie_path=cerere.selfie_path,
            extracted_cnp=cerere.extracted_cnp,
            similarity_score=rezultat.score,
            threshold_folosit=rezultat.threshold,
            status=status,
        )
    except Exception:
        logger.exception("verifica_identitate: scriere in identity_verifications esuata (id_user=%s)", cerere.user_id)
        raise ScriereRezultatError() from None

    if not rezultat.fata_detectata:
        logger.info("verifica_identitate: fata nedetectata, marcat pending_review (id_user=%s)", cerere.user_id)

    return VerificaIdentitateResponse(
        verified=rezultat.verified,
        score=rezultat.score,
        threshold=rezultat.threshold,
        status=status,
    )
