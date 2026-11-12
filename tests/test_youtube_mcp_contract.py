"""Offline MCP v2 protocol contract against an in-memory, unauthenticated server."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

try:
    from mcp import Client
    from meta_facebook_mcp_publisher.youtube_readonly_mcp import mcp
except ImportError:
    # The publisher's base CI intentionally tests without optional MCP SDK.
    # The dedicated YouTube-MCP workflow installs it and runs both tests.
    Client = None
    mcp = None


@unittest.skipIf(Client is None, "optional MCP SDK is not installed")
class YouTubeMCPContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_registers_only_read_tools_and_blocks_without_oauth(self):
        with patch.dict(os.environ, {
            "YOUTUBE_READONLY_ACCESS_TOKEN": "",
            "YOUTUBE_EXPECTED_CHANNEL_ID": "",
        }):
            async with Client(mcp) as client:
                tools = await client.list_tools()
                names = {tool.name for tool in tools.tools}
                self.assertEqual(names, {
                    "youtube_connection_status",
                    "youtube_my_channel",
                    "youtube_my_recent_videos",
                    "youtube_my_analytics",
                })
                result = await client.call_tool("youtube_connection_status", {})
                self.assertFalse(result.is_error)
                self.assertIn("BLOCKED_NO_OAUTH", str(result))
                self.assertNotIn("Bearer ", str(result))

    async def test_rejects_owner_data_without_google_consent(self):
        with patch.dict(os.environ, {"YOUTUBE_READONLY_ACCESS_TOKEN": ""}):
            async with Client(mcp) as client:
                result = await client.call_tool("youtube_my_channel", {})
                self.assertTrue(result.is_error)
                self.assertIn("Error executing tool youtube_my_channel", str(result))
