import asyncio
import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from meta_facebook_mcp_publisher.youtube_remote_access import (
    AccessConfig, AccessGate, AccessVerifier, PUBLIC_HOST,
)

ISSUER = "https://example.cloudflareaccess.com"
AUD = "a" * 64
EMAIL = "owner@example.com"


@pytest.fixture
def keys():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = AccessVerifier(AccessConfig(ISSUER, AUD, EMAIL))
    verifier.keys = SimpleNamespace(get_signing_key_from_jwt=lambda _: SimpleNamespace(key=private.public_key()))
    return private, other, verifier


def token(private, **overrides):
    now = int(time.time())
    claims = dict(iss=ISSUER, aud=[AUD], sub="owner-id", email=EMAIL,
                  type="app", iat=now-10, exp=now+120)
    claims.update(overrides)
    return jwt.encode(claims, private, algorithm="RS256", headers={"kid": "test"})


def test_verifier_valid_and_forged(keys):
    private, other, verify = keys
    assert verify(token(private))
    assert not verify(token(other))
    assert not verify("not-a-token")
    assert not verify(jwt.encode({"iss": ISSUER}, "secret", algorithm="HS256"))


@pytest.mark.parametrize("override", [
    {"iss": "https://evil.example"},
    {"aud": ["wrong"]},
    {"email": "intruder@example.com"},
    {"type": "org"},
    {"sub": ""},
    {"exp": 1},
    {"iat": 4102444800},
    {"nbf": 4102444800},
])
def test_verifier_claims(keys, override):
    private, _, verify = keys
    assert not verify(token(private, **override))


def test_jwks_failure_denies(keys):
    private, _, verify = keys
    def fail(_):
        raise OSError("JWKS unavailable")
    verify.keys = SimpleNamespace(get_signing_key_from_jwt=fail)
    assert not verify(token(private))


def test_config(monkeypatch):
    monkeypatch.setenv("CF_ACCESS_TEAM_DOMAIN", ISSUER)
    monkeypatch.setenv("CF_ACCESS_AUD", AUD)
    monkeypatch.setenv("CF_ACCESS_OWNER_EMAIL", EMAIL)
    assert AccessConfig.from_env() == AccessConfig(ISSUER, AUD, EMAIL)
    monkeypatch.setenv("CF_ACCESS_TEAM_DOMAIN", "evil.example")
    with pytest.raises(ValueError):
        AccessConfig.from_env()


def request(headers, method="POST", path="/mcp", verifier=lambda token: token == "valid"):
    forwarded = []
    sent = []

    async def app(scope, receive, send):
        forwarded.append(True)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"OK"})

    async def send(message):
        sent.append(message)

    async def receive():
        raise AssertionError("Gate must not read request body")

    gate = AccessGate(app, verifier)
    asyncio.run(gate({"type": "http", "method": method, "path": path,
                      "headers": headers}, receive, send))
    return sent[0]["status"], bool(forwarded)


HOST = (b"host", PUBLIC_HOST.encode())
ASSERTION = (b"cf-access-jwt-assertion", b"valid")


@pytest.mark.parametrize("method", ["POST", "GET", "DELETE"])
def test_all_methods_require_assertion(method):
    assert request([HOST], method) == (401, False)
    assert request([HOST, ASSERTION], method) == (200, True)


@pytest.mark.parametrize("headers,status", [
    ([HOST, (b"authorization", b"Bearer valid")], 401),
    ([HOST, (b"cf-access-jwt-assertion", b"invalid")], 401),
    ([HOST, ASSERTION, ASSERTION], 401),
    ([(b"host", b"evil.example"), ASSERTION], 421),
    ([HOST, HOST, ASSERTION], 421),
    ([HOST, (b"origin", b"https://evil.example"), ASSERTION], 403),
])
def test_gate_denies(headers, status):
    assert request(headers) == (status, False)


def test_unknown_route_and_method():
    assert request([HOST, ASSERTION], path="/admin") == (404, False)
    assert request([HOST, ASSERTION], method="PUT") == (405, False)
