from app.infrastructure.supabase import get_admin_client
from app.infrastructure.supabase_client import get_service_client


def descarca_imagine(bucket: str, cale: str) -> bytes:
    client = get_service_client()
    return client.storage.from_(bucket).download(cale)


def gaseste_id_user_dupa_email(email: str) -> str | None:
    client = get_service_client()
    raspuns = (
        client.table("profiles")
        .select("id")
        .ilike("email", email.strip())
        .limit(1)
        .execute()
    )
    if not raspuns.data:
        return None
    return raspuns.data[0]["id"]


def gaseste_selfie_verificat(id_user: str) -> str | None:
    """Ultima poza selfie cu status 'verified' a userului — singura acceptata
    ca referinta pentru login biometric (nu 'pending_review'/'rejected')."""
    client = get_service_client()
    raspuns = (
        client.table("identity_verifications")
        .select("selfie_image_path")
        .eq("id_user", id_user)
        .eq("status", "verified")
        .order("creat_la", desc=True)
        .limit(1)
        .execute()
    )
    if not raspuns.data:
        return None
    return raspuns.data[0]["selfie_image_path"]


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


# -----------------------------------------------------------------------------
# Citirile administratorului
#
# Merg cu service-role fiindca trec peste toate conturile si fiindca URL-urile
# semnate se cer tot de acolo. Politicile din 0005 raman ca plasa de siguranta
# pentru accesul facut cu sesiunea unui admin, dar aici bariera e verificarea
# explicita din ruta (cere_administrator) — service-role nu intreaba pe nimeni.
# -----------------------------------------------------------------------------

CAMPURI_CAZ = (
    "id,id_user,buletin_image_path,selfie_image_path,extracted_cnp,"
    "similarity_score,threshold_folosit,status,reviewed_by,reviewed_at,notes,creat_la"
)

# Cat traieste un link catre o poza de buletin. Destul cat sa se uite un om la
# ea, prea putin cat sa fie trimis mai departe si sa mai insemne ceva.
SECUNDE_URL_SEMNAT = 300


def listeaza_dupa_status(status: str, limita: int = 100) -> list[dict]:
    client = get_admin_client()
    raspuns = (
        client.table("identity_verifications")
        .select(CAMPURI_CAZ)
        .eq("status", status)
        .order("creat_la", desc=True)
        .limit(limita)
        .execute()
    )
    return raspuns.data or []


def obtine_caz(id_verificare: str) -> dict | None:
    client = get_admin_client()
    raspuns = (
        client.table("identity_verifications")
        .select(CAMPURI_CAZ)
        .eq("id", id_verificare)
        .maybe_single()
        .execute()
    )
    return raspuns.data if raspuns else None


def listeaza_neinceputi(limita: int = 100) -> list[dict]:
    """Conturi ramase pe verification_status='pending' — nicio dovada trimisa
    inca, deci nimic de revizuit in sensul obisnuit (vezi listeaza_dupa_status)."""
    client = get_admin_client()
    raspuns = (
        client.table("profiles")
        .select("id,nume,email,creat_la")
        .eq("verification_status", "pending")
        .order("creat_la", desc=True)
        .limit(limita)
        .execute()
    )
    return raspuns.data or []


def forteaza_verificat(id_user: str) -> dict | None:
    """Marcheaza manual contul ca verificat, ocolind fluxul OCR+selfie.

    Garda `.eq("verification_status", "pending")` tine actiunea in granitele
    ei: nu poate rescrie un cont deja respins sau in revizuire, unde exista
    deja dovezi si eventual o decizie — pentru acelea e fluxul cu poze
    (decide), nu acesta.
    """
    client = get_admin_client()
    raspuns = (
        client.table("profiles")
        .update({"verification_status": "verified"})
        .eq("id", id_user)
        .eq("verification_status", "pending")
        .execute()
    )
    date = raspuns.data or []
    return date[0] if date else None


def profiluri(ids: list[str]) -> dict[str, dict]:
    """Numele, emailul si CNP-ul declarat, pe id — o cerere, nu una de fiecare."""
    if not ids:
        return {}

    client = get_admin_client()
    raspuns = (
        client.table("profiles")
        .select("id,nume,email,cnp,verification_status")
        .in_("id", ids)
        .execute()
    )
    return {str(rand["id"]): rand for rand in (raspuns.data or [])}


def url_semnat(bucket: str, cale: str, secunde: int = SECUNDE_URL_SEMNAT) -> str | None:
    """Link temporar catre o poza dintr-un bucket privat.

    Niciodata getPublicUrl: bucket-urile de buletine si selfie-uri sunt private
    tocmai ca pozele sa nu poata fi deschise de cine da peste adresa lor.
    """
    client = get_admin_client()
    try:
        raspuns = client.storage.from_(bucket).create_signed_url(cale, secunde)
    except Exception:
        return None

    if isinstance(raspuns, dict):
        return raspuns.get("signedURL") or raspuns.get("signedUrl")
    return None


def scrie_decizie(
    id_verificare: str, status: str, reviewed_by: str, notes: str | None
) -> dict | None:
    """Scrie decizia. Trigger-ul din 0005 duce statusul si in profil."""
    from datetime import datetime, timezone

    client = get_admin_client()
    raspuns = (
        client.table("identity_verifications")
        .update(
            {
                "status": status,
                "reviewed_by": reviewed_by,
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "notes": notes,
            }
        )
        .eq("id", id_verificare)
        .execute()
    )
    date = raspuns.data or []
    return date[0] if date else None


def scrie_acces(
    id_administrator: str,
    actiune: str,
    id_utilizator: str | None = None,
    detalii: str | None = None,
) -> None:
    client = get_admin_client()
    client.table("acces_administrator").insert(
        {
            "id_administrator": id_administrator,
            "id_utilizator": id_utilizator,
            "actiune": actiune,
            "detalii": detalii,
        }
    ).execute()
