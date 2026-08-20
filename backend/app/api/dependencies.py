from functools import lru_cache

import jwt
from fastapi import Header, HTTPException, status

from app.infrastructure.config import get_settings


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

    if x_internal_api_key and x_user_id and x_internal_api_key == setari.backend_internal_api_key:
        return AuthContext(user_id=x_user_id, via_internal_key=True)

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autentificare necesara.")
