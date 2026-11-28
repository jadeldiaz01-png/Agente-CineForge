"""Fail-closed Cloudflare Access origin for the YouTube MCP.

Cloudflare Managed OAuth handles discovery and authorization at the edge.
The origin independently validates the signed Access application assertion.
Never expose the local unauthenticated MCP directly through the tunnel.
"""
from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from typing import Callable

import jwt
from jwt import PyJWKClient

PUBLIC_HOST = "youtube-mcp.jadeltechrd.com"
ALLOWED_HOSTS = {PUBLIC_HOST, PUBLIC_HOST + ":443", "127.0.0.1:8765"}
ALLOWED_ORIGINS = {"https://" + PUBLIC_HOST, "https://chatgpt.com"}


@dataclass(frozen=True)
class AccessConfig:
    issuer: str
    audience: str
    owner_email: str

    @classmethod
    def from_env(cls) -> AccessConfig:
        domain = os.environ.get("CF_ACCESS_TEAM_DOMAIN", "").strip().lower()
        domain = domain.removeprefix("https://").rstrip("/")
        audience = os.environ.get("CF_ACCESS_AUD", "").strip()
        email = os.environ.get("CF_ACCESS_OWNER_EMAIL", "").strip().lower()
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,62})\.cloudflareaccess\.com", domain):
            raise ValueError("Configure a Cloudflare Access team domain.")
        if not re.fullmatch(r"[a-fA-F0-9]{64}", audience):
            raise ValueError("Configure the application-specific Access AUD.")
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise ValueError("Configure exactly one authorized owner email.")
        return cls("https://" + domain, audience, email)


class AccessVerifier:
    def __init__(self, config: AccessConfig):
        self.config = config
        self.keys = PyJWKClient(
            config.issuer + "/cdn-cgi/access/certs",
            cache_jwk_set=True, lifespan=300, timeout=5,
        )

    def __call__(self, token: str) -> bool:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str) or not header["kid"]:
                return False
            key = self.keys.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token, key, algorithms=["RS256"],
                issuer=self.config.issuer, audience=self.config.audience,
                options={"require": ["exp", "iat", "iss", "aud", "sub", "email", "type"]},
            )
            return (
                claims.get("type") == "app"
                and isinstance(claims.get("sub"), str) and bool(claims["sub"])
                and isinstance(claims.get("email"), str)
                and claims["email"].lower() == self.config.owner_email
            )
        except Exception:
            # Malformed, expired, unknown key, JWKS outage: deny, never log JWTs.
            return False


class AccessGate:
    """Authenticate every HTTP request, including initialize and tools/list."""
    def __init__(self, app, verify: Callable[[str], bool]):
        self.app = app
        self.verify = verify
        self._slots = asyncio.Semaphore(8)

    @staticmethod
    async def deny(send, status: int):
        headers = [(b"content-type", b"text/plain"), (b"cache-control", b"no-store")]
        if status == 401:
            headers.append((b"www-authenticate", b"Bearer"))
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": b"Access denied"})

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
            return
        if scope["type"] != "http":
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
            return

        def values(name):
            return [v for k, v in scope.get("headers", []) if k.lower() == name]

        if scope.get("path") != "/mcp":
            await self.deny(send, 404)
            return
        if scope.get("method") not in {"POST", "GET", "DELETE"}:
            await self.deny(send, 405)
            return
        hosts = values(b"host")
        if len(hosts) != 1 or hosts[0].decode("latin1").lower() not in ALLOWED_HOSTS:
            await self.deny(send, 421)
            return
        origins = values(b"origin")
        if len(origins) > 1 or (origins and origins[0].decode("latin1") not in ALLOWED_ORIGINS):
            await self.deny(send, 403)
            return
        assertions = values(b"cf-access-jwt-assertion")
        if len(assertions) != 1 or not 1 <= len(assertions[0]) <= 16384:
            await self.deny(send, 401)
            return
        try:
            token = assertions[0].decode("ascii")
            async with self._slots:
                allowed = await asyncio.to_thread(self.verify, token)
        except Exception:
            allowed = False
        if not allowed:
            await self.deny(send, 401)
            return
        await self.app(scope, receive, send)


def build_app():
    from mcp.server.fastmcp import FastMCP
    from mcp.server.transport_security import TransportSecuritySettings
    from mcp.types import ToolAnnotations
    from .youtube_mcp_server import youtube_channel_info, upload_youtube_video

    config = AccessConfig.from_env()
    # Keep publishing disabled unless an operator explicitly enables it in the service environment.
    os.environ.setdefault("YOUTUBE_PUBLISHING_ENABLED", "false")
    os.environ.setdefault("YOUTUBE_PUBLIC_POSTING_AUDITED", "false")
    server = FastMCP(
        "cineforge-youtube-remote",
        host="127.0.0.1", port=8765,
        stateless_http=True, json_response=True,
        streamable_http_path="/mcp",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=sorted(ALLOWED_HOSTS),
            allowed_origins=sorted(ALLOWED_ORIGINS),
        ),
    )
    server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))(
        youtube_channel_info
    )
    server.tool(annotations=ToolAnnotations(
        readOnlyHint=False, destructiveHint=True, openWorldHint=True,
    ))(upload_youtube_video)
    return AccessGate(server.streamable_http_app(), AccessVerifier(config))


def main():
    import uvicorn
    uvicorn.run(build_app(), host="127.0.0.1", port=8765,
                proxy_headers=False, access_log=False, limit_concurrency=32)


if __name__ == "__main__":
    main()
