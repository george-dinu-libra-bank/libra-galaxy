"""Cazurile de verificare a identitatii, pentru administrator.

Serviciul nu decide singur nimic: aduna dovezile intr-o forma in care un om
poate hotari, si scrie hotararea lui. Detectia automata a spus deja ce avea de
spus la inregistrare; aici e vorba de cazurile in care nu a fost destul de
sigura.
"""

from app.core.errors import PersistenceError, ResourceNotFoundError, ValidationError
from app.repositories import identity_repository as depozit
from app.schemas.identity import (
    CazVerificare,
    CazVerificareDetaliu,
    ContNeinceput,
    DecizieResponse,
    ForteazaVerificareResponse,
    ProfilAdmin,
    RestabilireBiometrieResponse,
)

BUCKET_BULETIN = "buletine"
BUCKET_SELFIE = "selfie-uri"

STATUS_DE_REVIZUIT = "pending_review"
DECIZII_PERMISE = {"verified", "rejected"}


# Erorile mostenesc din ierarhia app/core/errors.py, ca sa fie prinse de
# handler-ul global din main.py si sa iasa in plicul standard. Branch-ul de unde
# vine fisierul avea o a doua ierarhie proprie (ErrorAplicatie), disparuta la
# unificarea backend-urilor; codul de status e acelasi, purtat acum de clasa in
# loc de un parametru dat la fiecare ridicare.
class CazNegasit(ResourceNotFoundError):
    def __init__(self) -> None:
        super().__init__("Cazul de verificare nu exista.")


class DecizieInvalida(ValidationError):
    def __init__(self, decizie: str) -> None:
        super().__init__(
            f"Decizia '{decizie}' nu e permisa; se accepta verified sau rejected."
        )


class ContNegasit(ResourceNotFoundError):
    def __init__(self) -> None:
        super().__init__("Contul nu exista sau verificarea lui a fost deja inceputa.")


def _numar(valoare) -> float | None:
    return float(valoare) if valoare is not None else None


def _construieste_caz(rand: dict, profil: dict) -> CazVerificare:
    distanta = _numar(rand.get("similarity_score"))
    prag = _numar(rand.get("threshold_folosit"))

    cnp_declarat = profil.get("cnp")
    cnp_extras = rand.get("extracted_cnp")
    # None, nu False, cand OCR-ul n-a citit nimic: "nu stim" si "nu se
    # potriveste" cer reactii diferite de la cel care revizuieste.
    se_potriveste = (
        None if not cnp_extras or not cnp_declarat else cnp_extras == cnp_declarat
    )

    return CazVerificare(
        id=str(rand["id"]),
        id_user=str(rand["id_user"]),
        nume=profil.get("nume", "necunoscut"),
        email=profil.get("email", ""),
        cnp_declarat=cnp_declarat,
        cnp_extras=cnp_extras,
        cnp_se_potriveste=se_potriveste,
        distanta_fete=distanta,
        prag=prag,
        sub_prag=None if distanta is None or prag is None else distanta <= prag,
        status=rand["status"],
        creat_la=str(rand["creat_la"]),
        reviewed_by=str(rand["reviewed_by"]) if rand.get("reviewed_by") else None,
        reviewed_at=str(rand["reviewed_at"]) if rand.get("reviewed_at") else None,
        notes=rand.get("notes"),
    )


def cazuri_de_revizuit(limita: int = 100) -> list[CazVerificare]:
    randuri = depozit.listeaza_dupa_status(STATUS_DE_REVIZUIT, limita)
    if not randuri:
        return []

    profiluri = depozit.profiluri([str(r["id_user"]) for r in randuri])
    return [_construieste_caz(r, profiluri.get(str(r["id_user"]), {})) for r in randuri]


def caz_cu_poze(id_verificare: str) -> CazVerificareDetaliu:
    """Cazul plus link-uri temporare catre cele doua poze.

    Link-urile se genereaza la fiecare deschidere si expira repede: pozele
    raman in bucket-uri private, iar o adresa scursa nu mai inseamna nimic
    dupa cateva minute.
    """
    rand = depozit.obtine_caz(id_verificare)
    if rand is None:
        raise CazNegasit()

    profiluri = depozit.profiluri([str(rand["id_user"])])
    caz = _construieste_caz(rand, profiluri.get(str(rand["id_user"]), {}))

    return CazVerificareDetaliu(
        **caz.model_dump(),
        url_buletin=depozit.url_semnat(BUCKET_BULETIN, rand["buletin_image_path"]),
        url_selfie=depozit.url_semnat(BUCKET_SELFIE, rand["selfie_image_path"]),
        secunde_valabilitate=depozit.SECUNDE_URL_SEMNAT,
    )


def decide(id_verificare: str, decizie: str, id_administrator: str, note: str | None) -> DecizieResponse:
    if decizie not in DECIZII_PERMISE:
        raise DecizieInvalida(decizie)

    caz = depozit.obtine_caz(id_verificare)
    if caz is None:
        raise CazNegasit()

    rand = depozit.scrie_decizie(id_verificare, decizie, id_administrator, note)
    if rand is None:
        raise PersistenceError("Nu am putut salva decizia.")

    # Fereastra in care buletinul are un motiv sa existe (revizuire de admin)
    # tocmai s-a inchis, indiferent de decizie. Selfie-ul ramane: cel aprobat
    # e refolosit la login biometric, iar cel respins se pastreaza pentru
    # dosarul cazului.
    depozit.sterge_imagine(BUCKET_BULETIN, caz["buletin_image_path"])

    return DecizieResponse(
        id=str(rand["id"]),
        status=rand["status"],
        reviewed_at=str(rand["reviewed_at"]) if rand.get("reviewed_at") else None,
    )


def conturi_neincepute(limita: int = 100) -> list[ContNeinceput]:
    randuri = depozit.listeaza_neinceputi(limita)
    return [
        ContNeinceput(
            id=str(r["id"]),
            nume=r.get("nume", "necunoscut"),
            email=r.get("email", ""),
            creat_la=str(r["creat_la"]),
        )
        for r in randuri
    ]


def forteaza_verificare(id_user: str) -> ForteazaVerificareResponse:
    rand = depozit.forteaza_verificat(id_user)
    if rand is None:
        raise ContNegasit()

    return ForteazaVerificareResponse(id=str(rand["id"]), verification_status=rand["verification_status"])


def toate_conturile(limita: int = 500) -> list[ProfilAdmin]:
    randuri = depozit.listeaza_toate_profilurile(limita)
    return [
        ProfilAdmin(
            id=str(r["id"]),
            nume=r.get("nume", "necunoscut"),
            email=r.get("email", ""),
            verification_status=r.get("verification_status", "pending"),
            creat_la=str(r["creat_la"]),
        )
        for r in randuri
    ]


def restabileste_biometrie(id_user: str, poza_path: str, id_administrator: str) -> RestabilireBiometrieResponse:
    rand = depozit.restabileste_referinta_biometrica(id_user, poza_path, id_administrator)
    if rand is None:
        raise PersistenceError("Nu am putut salva referinta biometrica.")

    return RestabilireBiometrieResponse(id=str(rand["id"]), verification_status=rand["status"])
