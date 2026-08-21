import logging

from app.core.errors import IdentityImageDownloadError, IdentityResultWriteError
from app.infrastructure.face_match import verifica_fete
from app.infrastructure.ocr import extrage_cnp
from app.repositories import identity_repository
from app.schemas.identity import VerificaIdentitateRequest, VerificaIdentitateResponse

logger = logging.getLogger(__name__)

BUCKET_BULETINE = "buletine"
BUCKET_SELFIE = "selfie-uri"


def extrage_cnp_din_buletin(imagine_bytes: bytes) -> tuple[str | None, float]:
    return extrage_cnp(imagine_bytes)


def _descarca(bucket: str, cale: str) -> bytes:
    try:
        return identity_repository.descarca_imagine(bucket, cale)
    except Exception:
        logger.exception("verifica_identitate: descarcare esuata (bucket=%s, cale=%s)", bucket, cale)
        raise IdentityImageDownloadError(f"Nu am putut descarca imaginea din storage ({bucket}/{cale}).") from None


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
        raise IdentityResultWriteError(
            "Am comparat fetele, dar nu am putut salva rezultatul in baza de date."
        ) from None

    if not rezultat.fata_detectata:
        logger.info("verifica_identitate: fata nedetectata, marcat pending_review (id_user=%s)", cerere.user_id)

    return VerificaIdentitateResponse(
        verified=rezultat.verified,
        score=rezultat.score,
        threshold=rezultat.threshold,
        status=status,
    )


def verifica_login_fata(email: str, imagine_live_bytes: bytes) -> bool:
    """
    Login biometric: compara 1:1 cadrul live cu ultimul selfie 'verified' al
    contului cu emailul dat — nu cauta in toata baza (1:N ar fi lent si mult
    mai expus la fals-pozitive). Orice pas care nu gaseste ceva (cont
    inexistent, fara selfie verificat) se termina tacut cu False, ca sa nu
    se poata deduce din raspuns daca un email exista sau e verificat.
    """
    id_user = identity_repository.gaseste_id_user_dupa_email(email)
    if not id_user:
        return False

    cale_selfie = identity_repository.gaseste_selfie_verificat(id_user)
    if not cale_selfie:
        return False

    try:
        selfie_referinta_bytes = identity_repository.descarca_imagine(BUCKET_SELFIE, cale_selfie)
    except Exception:
        logger.exception("verifica_login_fata: descarcare selfie referinta esuata (id_user=%s)", id_user)
        return False

    rezultat = verifica_fete(selfie_referinta_bytes, imagine_live_bytes)
    return rezultat.verified
