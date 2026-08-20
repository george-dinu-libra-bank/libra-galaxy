"""Autentificarea apelantilor.

Doua mecanisme, pentru doua nevoi diferite:

1. `get_current_user` / `get_user_supabase` — cazul normal. Verifica tokenul prin
   Supabase si intoarce un client care **pastreaza contextul RLS** al
   utilizatorului. Il folosesc rutele de profil, agenti si alerte.
2. `get_current_user_or_internal` — folosit de verificarea de identitate, care
   ruleaza si inainte sa existe o sesiune. Verifica JWT-ul local prin JWKS, sau
   accepta cheia interna a serverului Next.js.
"""

from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

import jwt
from anyio import to_thread
from fastapi import Depends, Header, HTTPException, status
from supabase import Client

from app.infrastructure.config import Settings, get_settings
from app.infrastructure.supabase import create_auth_client, create_user_client


@dataclass(frozen=True, slots=True)
class UserContext:
    user_id: UUID
    access_token: str


def _bearer_token(authorization: str | None) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Lipseste tokenul de autentificare.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


async def get_current_user(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> UserContext:
    token = _bearer_token(authorization)
    client = create_auth_client(settings)

    try:
        response = await to_thread.run_sync(client.auth.get_user, token)
        user = response.user
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesiunea este invalida sau a expirat.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilizator invalid.")

    return UserContext(user_id=UUID(str(user.id)), access_token=token)


def get_user_supabase(
    user: UserContext = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> Client:
    return create_user_client(settings, user.access_token)


class AuthContext:
    def __init__(self, user_id: str, via_internal_key: bool):
        self.user_id = user_id
        self.via_internal_key = via_internal_key


@lru_cache
def _jwk_client(jwks_url: str) -> jwt.PyJWKClient:
    # Cache-uit per proces; PyJWKClient isi cacheuieste si el intern cheile
    # (dupa "kid"), deci nu batem JWKS-ul la fiecare cerere.
    return jwt.PyJWKClient(jwks_url)


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
        try:
            cheie_semnare = _jwk_client(setari.supabase_jwks_url).get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                cheie_semnare.key,
                algorithms=["ES256", "RS256"],
                audience="authenticated",
            )
        except jwt.PyJWTError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalid.") from exc

        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalid.")

        return AuthContext(user_id=sub, via_internal_key=False)

    # Cheia interna nesetata (sir gol) nu deschide nimic: un header absent sau gol
    # e falsy, iar orice cheie nevida difera de "".
    if x_internal_api_key and x_user_id and x_internal_api_key == setari.backend_internal_api_key:
        return AuthContext(user_id=x_user_id, via_internal_key=True)

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autentificare necesara.")
