"""Local stdio MCP tools for authorized, read-only YouTube research.

Requires the optional MCP Python SDK v2. Do not expose stdio over a public URL.
The ChatGPT-side connection can be done with the existing Windsor.ai connector;
this module is for the CineForge/VPS runtime after separate OAuth provisioning.
"""
from __future__ import annotations

import os

from .youtube_readonly import YouTubeReadOnlyClient, YouTubeReadOnlyError

try:
    from mcp.server.mcpserver import MCPServer
except ImportError as exc:
    raise RuntimeError(
        "MCP_V2_REQUIRED: install with pip install '.[youtube-mcp]'"
    ) from exc

mcp = MCPServer(
    "CineForge YouTube ReadOnly",
    instructions="Only GET-only channel metadata and historical analytics; no uploads, edits, deletes or publication.",
)


@mcp.tool()
def youtube_connection_status() -> dict:
    """Diagnose connection without returning tokens, secrets or account email."""
    if not os.environ.get("YOUTUBE_READONLY_ACCESS_TOKEN", "").strip():
        return {"status": "BLOCKED_NO_OAUTH", "channel_verified": False}
    expected = os.environ.get("YOUTUBE_EXPECTED_CHANNEL_ID", "").strip()
    if not expected:
        return {"status": "BLOCKED_CHANNEL_NOT_PINNED", "channel_verified": False}
    try:
        profile = YouTubeReadOnlyClient().channel_profile()
    except YouTubeReadOnlyError:
        return {"status": "BLOCKED_AUTH_OR_API", "channel_verified": False}
    if profile.get("channel_id") != expected:
        return {"status": "BLOCKED_CHANNEL_MISMATCH", "channel_verified": False}
    return {
        "status": "CONNECTED_READONLY", "channel_verified": True,
        "channel_id": expected, "channel_title": profile.get("title"),
    }


@mcp.tool()
def youtube_my_channel() -> dict:
    """Read the authenticated YouTube channel name and aggregate public metrics."""
    return YouTubeReadOnlyClient().channel_profile()


@mcp.tool()
def youtube_my_recent_videos(limit: int = 5) -> dict:
    """Read recent uploads of the OAuth-selected channel; maximum 20."""
    return YouTubeReadOnlyClient().recent_videos(limit=limit)


@mcp.tool()
def youtube_my_analytics(start_date: str, end_date: str) -> dict:
    """Read views, watch minutes, and subscribers gained for up to 90 days."""
    return YouTubeReadOnlyClient().channel_analytics(start_date, end_date)


if __name__ == "__main__":
    mcp.run(transport="stdio")
