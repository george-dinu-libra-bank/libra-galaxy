"""Principal si verificarea JWT-ului real emis de Supabase Auth (docs/SECURITY.md #1).

Nu exista principal de dezvoltare tip `dev:<user_id>:<role>`: Supabase Auth e deja
functional in acest proiect (login/register/callback), deci backend-ul verifica
direct token-ul real, in loc sa introduca o autentificare paralela.

Verificare prin JWKS (ES256), nu printr-un secret HS256 partajat: proiectul
foloseste chei asimetrice (verificat live, /auth/v1/.well-known/jwks.json
raspunde cu chei EC/ES256) — nu exista un "JWT secret" clasic de configurat.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import jwt
from fastapi import Header
from jwt import PyJWKClient

from app.core.config import get_settings
from app.core.errors import AuthInvalidError, AuthRequiredError, ConfigurationError
from app.core.logging import user_id_var

PERMISSION_ASSISTANT_USE = "assistant:use"
PERMISSION_ACCOUNTS_READ = "accounts:read"

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "customer": {PERMISSION_ASSISTANT_USE, PERMISSION_ACCOUNTS_READ},
}

_SUPPORTED_ALGORITHMS = ["ES256", "RS256"]


@dataclass(frozen=True)
class Principal:
    user_id: str
    role: str
    permissions: set[str] = field(default_factory=set)
    locale: str = "ro"
    # Token-ul JWT brut, cat tine request-ul — nu se logheaza (vezi redactarea
    # din core/logging.py). Necesar doar pentru create_user_client (RLS pastrat),
    # folosit azi de adaptorul financial_advisor peste agentul lui Cristi.
    access_token: str | None = None

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions


@lru_cache
def _jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)


def get_jwks_client() -> PyJWKClient:
    """Punct de injectare pentru teste — monkeypatch aici, nu pe _decode_supabase_jwt."""
    settings = get_settings()
    if not settings.supabase_url:
        raise ConfigurationError("SUPABASE_URL nu este configurat.")
    return _jwks_client(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")


def _decode_supabase_jwt(token: str) -> dict:
    try:
        signing_key = get_jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(token, signing_key.key, algorithms=_SUPPORTED_ALGORITHMS, audience="authenticated")
    except jwt.PyJWTError as exc:
        raise AuthInvalidError("Token invalid sau expirat.") from exc


async def get_principal(authorization: str | None = Header(default=None)) -> Principal:
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthRequiredError("Lipseste antetul Authorization.")

    token = authorization.removeprefix("Bearer ").strip()
    claims = _decode_supabase_jwt(token)

    user_id = claims.get("sub")
    if not user_id:
        raise AuthInvalidError("Token fara subiect (sub).")

    role = "customer"
    locale = (claims.get("user_metadata") or {}).get("locale", "ro")

    user_id_var.set(user_id)
    return Principal(
        user_id=user_id, role=role, permissions=set(ROLE_PERMISSIONS.get(role, set())),
        locale=locale, access_token=token,
    )


async def get_principal_or_internal(
    authorization: str | None = Header(default=None),
    x_internal_api_key: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> Principal:
    """Pentru rute apelate de Next.js inainte sa existe o sesiune Supabase
    (inregistrare cu confirmare pe email activata — vezi api/routes/identity.py).
    Cheia interna nu ajunge niciodata in browser; Next.js e contextul de
    incredere in aceasta fereastra ingusta. In afara asta, verificarea e
    identica cu get_principal — un singur decodor de JWT in tot backend-ul.
    """
    settings = get_settings()

    if (
        x_internal_api_key
        and x_user_id
        and settings.backend_internal_api_key
        and x_internal_api_key == settings.backend_internal_api_key
    ):
        user_id_var.set(x_user_id)
        return Principal(user_id=x_user_id, role="customer", permissions=set(ROLE_PERMISSIONS.get("customer", set())))

    return await get_principal(authorization)
