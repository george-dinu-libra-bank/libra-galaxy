import base64
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from jwt import PyJWK

import app.core.security as security_module
from app.core.errors import AuthInvalidError, AuthRequiredError
from app.core.security import get_principal

_PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())


def _jwk_for(public_key) -> PyJWK:
    numbers = public_key.public_numbers()

    def encode(n: int) -> str:
        return base64.urlsafe_b64encode(n.to_bytes(32, "big")).rstrip(b"=").decode("ascii")

    return PyJWK.from_json(
        json.dumps({"kty": "EC", "crv": "P-256", "alg": "ES256", "use": "sig", "x": encode(numbers.x), "y": encode(numbers.y)})
    )


class _FakeJwksClient:
    """Simuleaza PyJWKClient fara sa loveasca reteaua — cheia EC de test generata mai sus."""

    def get_signing_key_from_jwt(self, _token: str) -> PyJWK:
        return _jwk_for(_PRIVATE_KEY.public_key())


@pytest.fixture(autouse=True)
def _fake_jwks(monkeypatch):
    monkeypatch.setattr(security_module, "get_jwks_client", lambda: _FakeJwksClient())
    yield


def _token(**claims) -> str:
    payload = {"sub": "user-123", "aud": "authenticated", "exp": int(time.time()) + 3600, **claims}
    return jwt.encode(payload, _PRIVATE_KEY, algorithm="ES256")


async def test_valid_token_resolves_principal():
    principal = await get_principal(authorization=f"Bearer {_token()}")
    assert principal.user_id == "user-123"
    assert principal.role == "customer"
    assert "assistant:use" in principal.permissions


async def test_missing_header_raises_auth_required():
    with pytest.raises(AuthRequiredError):
        await get_principal(authorization=None)


async def test_malformed_header_raises_auth_required():
    with pytest.raises(AuthRequiredError):
        await get_principal(authorization="NotBearer xyz")


async def test_expired_token_raises_auth_invalid():
    expired = jwt.encode(
        {"sub": "user-123", "aud": "authenticated", "exp": int(time.time()) - 10}, _PRIVATE_KEY, algorithm="ES256"
    )
    with pytest.raises(AuthInvalidError):
        await get_principal(authorization=f"Bearer {expired}")


async def test_wrong_signature_raises_auth_invalid():
    other_key = ec.generate_private_key(ec.SECP256R1())
    token = jwt.encode(
        {"sub": "user-123", "aud": "authenticated", "exp": int(time.time()) + 3600}, other_key, algorithm="ES256"
    )
    with pytest.raises(AuthInvalidError):
        await get_principal(authorization=f"Bearer {token}")


async def test_token_without_subject_raises_auth_invalid():
    token = jwt.encode({"aud": "authenticated", "exp": int(time.time()) + 3600}, _PRIVATE_KEY, algorithm="ES256")
    with pytest.raises(AuthInvalidError):
        await get_principal(authorization=f"Bearer {token}")
