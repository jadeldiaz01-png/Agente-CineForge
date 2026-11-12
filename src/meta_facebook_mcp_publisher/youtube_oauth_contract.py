"""OAuth 2.0 / PKCE request contract for a future HTTPS consent broker.

This module only creates an authorization request and validates callback state.
It never exchanges codes, stores tokens, serves a callback or opens a network
connection. Production launch requires an independently secured OAuth broker.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from base64 import urlsafe_b64encode
from hashlib import sha256
from hmac import compare_digest
from secrets import token_urlsafe
from urllib.parse import urlencode, urlsplit

AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
READ_ONLY_SCOPES = (
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
)


@dataclass(frozen=True)
class AuthorizationAttempt:
    authorization_url: str
    state: str = field(repr=False)
    code_verifier: str = field(repr=False)


class OAuthConfigurationError(ValueError):
    pass


def _validate_client_id(client_id: str) -> None:
    if (
        not isinstance(client_id, str)
        or len(client_id) > 256
        or not client_id.endswith(".apps.googleusercontent.com")
        or len(client_id) < 40
        or any(c.isspace() for c in client_id)
    ):
        raise OAuthConfigurationError("GOOGLE_OAUTH_CLIENT_ID_INVALID")


def _validate_redirect_uri(redirect_uri: str) -> None:
    try:
        parsed = urlsplit(redirect_uri)
        port = parsed.port
    except (TypeError, ValueError):
        raise OAuthConfigurationError("GOOGLE_OAUTH_REDIRECT_INVALID") from None
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or "." not in parsed.hostname
        or parsed.hostname.endswith(".localhost")
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or not parsed.path.startswith("/")
        or parsed.query
        or parsed.fragment
        or len(redirect_uri) > 2048
    ):
        raise OAuthConfigurationError("GOOGLE_OAUTH_REDIRECT_INVALID")


def create_authorization_attempt(client_id: str, redirect_uri: str) -> AuthorizationAttempt:
    """Create a strict read-only Google consent link; state/verifier remain ephemeral."""
    _validate_client_id(client_id)
    _validate_redirect_uri(redirect_uri)
    state = token_urlsafe(32)
    verifier = token_urlsafe(64)
    challenge = urlsafe_b64encode(sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    args = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(READ_ONLY_SCOPES),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "access_type": "online",
        "include_granted_scopes": "false",
    }
    return AuthorizationAttempt(
        authorization_url=AUTHORIZATION_ENDPOINT + "?" + urlencode(args),
        state=state,
        code_verifier=verifier,
    )


def validate_authorization_callback(
    attempt: AuthorizationAttempt,
    *,
    received_state: str,
    authorization_code: str | None = None,
    error: str | None = None,
) -> str:
    """Return the sensitive one-time code only to trusted broker caller, never log it."""
    if not isinstance(received_state, str) or not compare_digest(
        attempt.state, received_state
    ):
        raise OAuthConfigurationError("GOOGLE_OAUTH_STATE_MISMATCH")
    if error is not None:
        raise OAuthConfigurationError("GOOGLE_OAUTH_PROVIDER_DENIED")
    if not authorization_code or not isinstance(authorization_code, str):
        raise OAuthConfigurationError("GOOGLE_OAUTH_CODE_MISSING")
    return authorization_code
