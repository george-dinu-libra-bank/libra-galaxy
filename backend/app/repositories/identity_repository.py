import logging

from app.infrastructure.supabase import get_admin_client
from app.infrastructure.supabase_client import get_service_client

logger = logging.getLogger(__name__)


def descarca_imagine(bucket: str, cale: str) -> bytes:
    client = get_service_client()
    return client.storage.from_(bucket).download(cale)


def sterge_imagine(bucket: str, cale: str) -> None:
    """Sterge o poza din storage. Nu esueaza cererea care o cheama: o poza care
    ramane in plus cateva zile e mai putin rau decat o verificare care pica
    pentru ca stergerea ei a mers prost."""
    client = get_service_client()
    try:
        client.storage.from_(bucket).remove([cale])
    except Exception:
        logger.exception("sterge_imagine: stergere esuata (bucket=%s, cale=%s)", bucket, cale)


def gaseste_selfie_referinta(id_user: str) -> str | None:
    """Selfie-ul retinut la inregistrare (sau la ultima verificare), pentru
    cazul in care buletinul e trimis mai tarziu, fara un selfie nou."""
    client = get_service_client()
    raspuns = (
        client.table("profiles")
        .select("selfie_referinta_path")
        .eq("id", id_user)
        .maybe_single()
        .execute()
    )
    date = raspuns.data if raspuns else None
    return date.get("selfie_referinta_path") if date else None


def seteaza_selfie_referinta(id_user: str, cale: str) -> None:
    client = get_service_client()
    client.table("profiles").update({"selfie_referinta_path": cale}).eq("id", id_user).execute()


def gaseste_user_dupa_email(email: str) -> tuple[str | None, bool]:
    """
    (id_user, biometrie_activata) pentru emailul dat, sau (None, False).

    Cele doua se citesc impreuna pentru ca apelantul le vrea pe amandoua
    inainte sa decida ceva — vezi verifica_login_fata.

    `biometrie_activata` a aparut in migratia 0019, care se aplica manual pe
    Supabase cloud. Pana atunci coloana lipseste, iar select-ul intoarce
    eroare; in cazul asta reincercam fara ea si presupunem `True`, adica exact
    comportamentul de dinainte. Un login biometric n-are voie sa se strice
    fiindca o migratie inca n-a fost rulata.
    """
    client = get_service_client()

    try:
        raspuns = (
            client.table("profiles")
            .select("id, biometrie_activata")
            .ilike("email", email.strip())
            .limit(1)
            .execute()
        )
    except Exception:
        logger.warning(
            "gaseste_user_dupa_email: coloana biometrie_activata lipseste "
            "(migratia 0019 neaplicata?), continui ca si cum ar fi activata"
        )
        raspuns = (
            client.table("profiles")
            .select("id")
            .ilike("email", email.strip())
            .limit(1)
            .execute()
        )

    if not raspuns.data:
        return None, False

    rand = raspuns.data[0]
    return rand["id"], bool(rand.get("biometrie_activata", True))


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


def listeaza_toate_profilurile(limita: int = 500) -> list[dict]:
    client = get_admin_client()
    raspuns = (
        client.table("profiles")
        .select("id,nume,email,verification_status,creat_la")
        .order("creat_la", desc=True)
        .limit(limita)
        .execute()
    )
    return raspuns.data or []


def restabileste_referinta_biometrica(id_user: str, cale_poza: str, id_administrator: str) -> dict | None:
    """Insereaza o verificare noua, deja 'verified', cu poza data de admin ca
    reper biometric — pentru conturile ramase fara nimic de comparat dupa ce
    pozele din storage au disparut.

    Foloseste aceeasi poza si pentru buletin_image_path (coloana e NOT NULL
    in schema): nu exista un buletin nou aici, doar reperul de fata pe care
    administratorul il atesta direct, fara OCR/comparatie automata.
    """
    from datetime import datetime, timezone

    client = get_admin_client()
    raspuns = (
        client.table("identity_verifications")
        .insert(
            {
                "id_user": id_user,
                "buletin_image_path": cale_poza,
                "selfie_image_path": cale_poza,
                "status": "verified",
                "reviewed_by": id_administrator,
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "notes": "Referinta biometrica restabilita manual de admin (poze sterse din storage).",
            }
        )
        .execute()
    )
    date = raspuns.data or []
    return date[0] if date else None
