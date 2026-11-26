from __future__ import annotations

import os
from urllib.parse import urlsplit

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from .youtube_mcp_server import _configured_client, _load_secret_file, youtube_channel_info

_TRUE_VALUES = {"1", "true", "yes", "on"}
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _csv_values(name: str) -> list[str]:
    return [value.strip() for value in os.getenv(name, "").split(",") if value.strip()]


def _port() -> int:
    try:
        port = int(os.getenv("YOUTUBE_MCP_HTTP_PORT", "8766"))
    except ValueError as exc:
        raise ValueError("YOUTUBE_MCP_HTTP_PORT must be an integer.") from exc
    if not 1 <= port <= 65535:
        raise ValueError("YOUTUBE_MCP_HTTP_PORT must be between 1 and 65535.")
    return port


def _transport_security(port: int) -> TransportSecuritySettings:
    default_hosts = [f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"]
    default_origins = [
        f"http://127.0.0.1:{port}",
        f"http://localhost:{port}",
        f"http://[::1]:{port}",
    ]
    hosts = list(dict.fromkeys(default_hosts + _csv_values("YOUTUBE_MCP_HTTP_ALLOWED_HOSTS")))
    origins = list(dict.fromkeys(default_origins + _csv_values("YOUTUBE_MCP_HTTP_ALLOWED_ORIGINS")))

    for value in hosts:
        if (
            not value
            or any(character.isspace() for character in value)
            or any(character in value for character in "/?#@")
            or value == "*"
            or ("*" in value and not value.endswith(":*"))
        ):
            raise ValueError("YOUTUBE_MCP_HTTP_ALLOWED_HOSTS must contain exact host entries.")

    for value in origins:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or (parsed.hostname.lower() not in _LOCAL_HOSTS and parsed.scheme != "https")
        ):
            raise ValueError("YOUTUBE_MCP_HTTP_ALLOWED_ORIGINS must contain exact HTTP(S) origins.")

    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=origins,
    )


def _build_read_only_server() -> FastMCP:
    port = _port()
    app = FastMCP(
        "cineforge-youtube-readonly",
        host="127.0.0.1",
        port=port,
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        transport_security=_transport_security(port),
    )
    app.tool()(youtube_channel_info)
    return app


def main() -> None:
    if os.getenv("YOUTUBE_MCP_HTTP_ENABLED", "").strip().lower() not in _TRUE_VALUES:
        raise RuntimeError("YOUTUBE_MCP_HTTP_ENABLED is off; remote MCP server blocked.")
    _load_secret_file()
    _configured_client()
    _build_read_only_server().run(transport="streamable-http")


if __name__ == "__main__":
    main()
