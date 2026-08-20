from app.infrastructure.supabase_client import get_service_client


def descarca_imagine(bucket: str, cale: str) -> bytes:
    client = get_service_client()
    return client.storage.from_(bucket).download(cale)


def inregistreaza_verificare(
    id_user: str,
    buletin_path: str,
    selfie_path: str,
    extracted_cnp: str | None,
    similarity_score: float | None,
    threshold_folosit: float,
    status: str,
) -> None:
    """Scrie o incercare de verificare — trigger-ul din 0007 sincronizeaza profiles.verification_status.

    similarity_score poate fi None cand DeepFace n-a gasit o fata clara
    intr-una din poze (vezi face_match.verifica_fete) — nu inseamna scor 0.
    """
    client = get_service_client()
    client.table("identity_verifications").insert(
        {
            "id_user": id_user,
            "buletin_image_path": buletin_path,
            "selfie_image_path": selfie_path,
            "extracted_cnp": extracted_cnp,
            "similarity_score": round(similarity_score, 5) if similarity_score is not None else None,
            "threshold_folosit": round(threshold_folosit, 5),
            "status": status,
        }
    ).execute()
