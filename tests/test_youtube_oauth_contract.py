"""No-network tests of Google OAuth PKCE request and callback validation."""
from __future__ import annotations

import unittest
from urllib.parse import parse_qs, urlsplit

from meta_facebook_mcp_publisher.youtube_oauth_contract import (
    OAuthConfigurationError,
    READ_ONLY_SCOPES,
    create_authorization_attempt,
    validate_authorization_callback,
)

CLIENT = "123456789012-exampleabc123.apps.googleusercontent.com"
REDIRECT = "https://youtube-auth.jadeltechrd.com/oauth/callback"


class TestYouTubeOAuthContract(unittest.TestCase):
    def test_pkce_state_and_read_only_scopes(self):
        attempt = create_authorization_attempt(CLIENT, REDIRECT)
        parsed = urlsplit(attempt.authorization_url)
        query = parse_qs(parsed.query)
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "accounts.google.com")
        self.assertEqual(query["scope"][0].split(), list(READ_ONLY_SCOPES))
        self.assertEqual(query["redirect_uri"], [REDIRECT])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["access_type"], ["online"])
        self.assertNotIn("youtube.upload", str(query))
        self.assertNotIn("force-ssl", str(query))
        self.assertNotIn("client_secret", str(query))
        self.assertNotIn(attempt.code_verifier, attempt.authorization_url)
        self.assertNotIn(attempt.state, repr(attempt))

    def test_attempts_are_nondeterministic(self):
        a = create_authorization_attempt(CLIENT, REDIRECT)
        b = create_authorization_attempt(CLIENT, REDIRECT)
        self.assertNotEqual(a.state, b.state)
        self.assertNotEqual(a.code_verifier, b.code_verifier)

    def test_bad_client_or_redirect_rejected(self):
        for client in ["", "fake", "x" * 1000, "x.apps.googleusercontent.com\n"]:
            with self.assertRaises(OAuthConfigurationError):
                create_authorization_attempt(client, REDIRECT)
        for redirect in [
            "http://youtube-auth.jadeltechrd.com/oauth/callback",
            "https://example.com@evil.test/callback",
            "https://localhost/callback",
            "https://youtube-auth.jadeltechrd.com:8000/oauth/callback",
            "https://youtube-auth.jadeltechrd.com/oauth/callback#code",
            "https://youtube-auth.jadeltechrd.com/oauth/callback?code=abc",
        ]:
            with self.assertRaises(OAuthConfigurationError):
                create_authorization_attempt(CLIENT, redirect)

    def test_callback_state_checks(self):
        attempt = create_authorization_attempt(CLIENT, REDIRECT)
        self.assertEqual(
            validate_authorization_callback(
                attempt, received_state=attempt.state, authorization_code="one-time-code"
            ),
            "one-time-code",
        )
        for wrong in ["", "malicious", attempt.state[:-1]]:
            with self.assertRaisesRegex(OAuthConfigurationError, "STATE_MISMATCH"):
                validate_authorization_callback(
                    attempt, received_state=wrong, authorization_code="one-time-code"
                )
        with self.assertRaisesRegex(OAuthConfigurationError, "PROVIDER_DENIED"):
            validate_authorization_callback(
                attempt, received_state=attempt.state, error="access_denied"
            )
        with self.assertRaisesRegex(OAuthConfigurationError, "CODE_MISSING"):
            validate_authorization_callback(attempt, received_state=attempt.state)
