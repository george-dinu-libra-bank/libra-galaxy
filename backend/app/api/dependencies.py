"""Cine e apelantul, si ce are voie.

Verificarea tokenului se face intr-un singur loc, prin JWKS: Supabase semneaza
acum cu chei asimetrice, deci se valideaza cu cheia publica a proiectului, fara
niciun secret in .env si fara o cerere in plus catre Supabase la fiecare apel.

Doua contexte, pentru ca sunt doua feluri de rute:

- `AuthContext` (get_current_user_or_internal) — pentru fluxul de verificare a
  identitatii, care poate fi apelat si de serverul Next.js inainte sa existe o
  sesiune. Scrie cu service-role, deci isi verifica singur drepturile.
- `UserContext` (get_current_user) — pentru rutele care citesc date in numele
  utilizatorului. Pastreaza tokenul, ca clientul Supabase sa fie construit cu
  el si RLS sa ramana bariera din baza de date.
"""

from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

import jwt
from anyio import to_thread
from fastapi import Depends, Header, HTTPException, status
from supabase import Client

from app.infrastructure.config import Settings, get_settings
from app.infrastructure.supabase import create_user_client, get_admin_client

ROL_ADMIN = "admin"


class AuthContext:
    def __init__(self, user_id: str, via_internal_key: bool):
        self.user_id = user_id
        self.via_internal_key = via_internal_key


@dataclass(frozen=True, slots=True)
class UserContext:
    user_id: UUID
    access_token: str


@lru_cache
def _jwk_client(jwks_url: str) -> jwt.PyJWKClient:
    # Cache-uit per proces; PyJWKClient isi cacheuieste si el intern cheile
    # (dupa "kid"), deci nu batem JWKS-ul la fiecare cerere.
    return jwt.PyJWKClient(jwks_url)


def _sub_din_token(token: str, setari: Settings) -> str:
    """Id-ul utilizatorului dintr-un JWT valid. Arunca 401 daca nu e valid."""
    try:
        cheie_semnare = _jwk_client(setari.supabase_jwks_url).get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            cheie_semnare.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalid."
        ) from exc

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalid.")
    return str(sub)


def get_current_user_or_internal(
    authorization: str | None = Header(default=None),
    x_internal_api_key: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> AuthContext:
    """
    Autentifica apelantul in doua moduri, per ARCHITECTURE.md §5:

    1. JWT Supabase (Authorization: Bearer <token>) — cazul normal, cand
       userul are deja o sesiune.
    2. Cheie interna (X-Internal-Api-Key + X-User-Id) — folosita DOAR de
       serverul Next.js, imediat dupa signUp(), cand confirmarea pe email e
       activata si inca nu exista o sesiune Supabase. Cheia nu ajunge
       niciodata in browser; Next.js e contextul de incredere in aceasta
       fereastra ingusta (vezi identitate.ts).

    user_id-ul din body nu e niciodata acceptat ca atare — apelantul routei
    trebuie sa-l verifice fata de acest context.
    """
    setari = get_settings()

    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
        return AuthContext(user_id=_sub_din_token(token, setari), via_internal_key=False)

    if (
        x_internal_api_key
        and x_user_id
        and setari.backend_internal_api_key
        and x_internal_api_key == setari.backend_internal_api_key
    ):
        return AuthContext(user_id=x_user_id, via_internal_key=True)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Autentificare necesara."
    )


def _bearer_token(authorization: str | None) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Lipseste tokenul de autentificare.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


def get_current_user(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> UserContext:
    """Utilizatorul, cu tokenul pastrat pentru clientul cu RLS."""
    token = _bearer_token(authorization)
    return UserContext(user_id=UUID(_sub_din_token(token, settings)), access_token=token)


def get_user_supabase(
    user: UserContext = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> Client:
    return create_user_client(settings, user.access_token)


def get_admin_supabase() -> Client:
    """Clientul privilegiat, ca dependinta — ca sa poata fi inlocuit in teste."""
    return get_admin_client()


async def este_admin(user_id: UUID | str, client: Client) -> bool:
    """Are utilizatorul rolul de admin in public.user_roles?

    Interogarea merge cu service-role dinadins: verificarea de drepturi nu
    trebuie sa depinda de politicile pe care tot ea le deblocheaza. Fiindca
    ocoleste RLS, raspunsul e folosit numai ca sa se decida daca cererea trece
    mai departe — datele propriu-zise se citesc dupa aceea cu clientul
    utilizatorului, unde RLS ramane a doua bariera.
    """

    def interogare() -> list[dict]:
        raspuns = (
            client
            .table("user_roles")
            .select("role")
            .eq("user_id", str(user_id))
            .eq("role", ROL_ADMIN)
            .limit(1)
            .execute()
        )
        return raspuns.data or []

    return bool(await to_thread.run_sync(interogare))


async def cere_administrator(
    user: UserContext = Depends(get_current_user),
    client_admin: Client = Depends(get_admin_supabase),
) -> UserContext:
    """Lasa sa treaca numai administratorii. Verificarea e mereu pe server.

    Ascunderea butonului in interfata nu e o bariera; oricine poate chema ruta
    direct. Rolul se citeste din baza de date la fiecare cerere, nu din token:
    un rol pus in JWT ar ramane valabil pana expira tokenul, inclusiv dupa ce
    i-a fost luat cuiva dreptul.
    """
    try:
        admin = await este_admin(user.user_id, client_admin)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Nu am putut verifica drepturile contului.",
        ) from exc

    if not admin:
        # Acelasi raspuns si cand contul nu are rol, si cand nu exista deloc:
        # cine incearca ruta nu trebuie sa afle ce a nimerit.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Aceasta zona e disponibila numai administratorilor.",
        )

    return user
