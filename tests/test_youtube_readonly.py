import os
import unittest
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from meta_facebook_mcp_publisher.youtube_readonly import (
    YouTubeReadOnlyClient, YouTubeReadOnlyError
)


class FakeTransport:
    def __init__(self):
        self.calls = []

    def __call__(self, url, headers):
        self.calls.append((url, headers))
        assert url.startswith("https://")
        assert "Bearer " in headers["Authorization"]
        endpoint = urlsplit(url)
        q = parse_qs(endpoint.query)
        if endpoint.path.endswith("/channels") and q.get("part") == ["snippet,statistics"]:
            return {"items": [{"id": "UC1234567890123456789012", "snippet": {
                "title": "Demo", "publishedAt": "2025-02-01T00:00:00Z"
            }, "statistics": {"viewCount": "100", "videoCount": "2"}}]}
        if endpoint.path.endswith("/channels"):
            return {"items": [{"id": "UC1234567890123456789012", "contentDetails": {
                "relatedPlaylists": {"uploads": "UUtest"}
            }}]}
        if endpoint.path.endswith("/playlistItems"):
            return {"items": [{"contentDetails": {
                "videoId": "abc123", "videoPublishedAt": "2026-01-01T00:00:00Z"
            }, "snippet": {"title": "One"}}]}
        if endpoint.path.endswith("/reports"):
            return {"columnHeaders": [{"name": "views"}, {
                "name": "estimatedMinutesWatched"}, {"name": "subscribersGained"}],
                "rows": [[120, 76.5, 2]]}
        raise AssertionError(endpoint.path)


class YouTubeReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.pin = patch.dict(os.environ, {"YOUTUBE_EXPECTED_CHANNEL_ID": "UC1234567890123456789012"})
        self.pin.start()
        self.addCleanup(self.pin.stop)

    def test_no_oauth_token_fails_closed(self):
        with patch.dict(os.environ, {"YOUTUBE_READONLY_ACCESS_TOKEN": ""}):
            with self.assertRaisesRegex(YouTubeReadOnlyError, "NOT_CONNECTED"):
                YouTubeReadOnlyClient().channel_profile()

    def test_channel_profile_and_no_writes(self):
        tx = FakeTransport()
        client = YouTubeReadOnlyClient(token="dummy-offline-token", transport=tx)
        result = client.channel_profile()
        self.assertEqual(result["title"], "Demo")
        self.assertEqual(result["views"], "100")
        self.assertEqual(len(tx.calls), 1)
        self.assertNotIn("publish_video", dir(client))
        self.assertNotIn("delete_video", dir(client))
        self.assertNotIn("upload", tx.calls[0][0])

    def test_recent_uploads_limit_and_playlist(self):
        tx = FakeTransport()
        c = YouTubeReadOnlyClient(token="dummy", transport=tx)
        self.assertEqual(c.recent_videos(3)["videos"][0]["video_id"], "abc123")
        self.assertEqual(parse_qs(urlsplit(tx.calls[-1][0]).query)["maxResults"], ["3"])
        for bad in [0, 21, -1, True, "5"]:
            with self.assertRaises(ValueError):
                c.recent_videos(bad)

    def test_analytics_uses_only_aggregate_nonmonetary_metrics(self):
        tx = FakeTransport()
        c = YouTubeReadOnlyClient(token="dummy", transport=tx)
        result = c.channel_analytics("2026-01-01", "2026-01-31")
        self.assertEqual(result["metrics"]["views"], 120)
        query = parse_qs(urlsplit(tx.calls[-1][0]).query)
        self.assertEqual(query["ids"], ["channel==MINE"])
        self.assertNotIn("estimatedRevenue", query["metrics"][0])
        self.assertEqual(len(tx.calls), 2)
        self.assertEqual(parse_qs(urlsplit(tx.calls[0][0]).query)["part"], ["id"])

    def test_channel_identity_gate_blocks_private_data(self):
        tx = FakeTransport()
        client = YouTubeReadOnlyClient(token="dummy", transport=tx)
        with patch.dict(os.environ, {"YOUTUBE_EXPECTED_CHANNEL_ID": ""}):
            with self.assertRaisesRegex(YouTubeReadOnlyError, "NOT_CONFIGURED"):
                client.recent_videos()
        self.assertEqual(len(tx.calls), 1)
        with patch.dict(os.environ, {"YOUTUBE_EXPECTED_CHANNEL_ID": "UCAAAAAAAAAAAAAAAAAAAAAA"}):
            with self.assertRaisesRegex(YouTubeReadOnlyError, "MISMATCH"):
                client.channel_analytics("2026-01-01", "2026-01-30")
        # Only the identity check is made; no private playlist or analytics query.
        self.assertEqual(len(tx.calls), 2)
        self.assertTrue(all(urlsplit(url).path.endswith("/channels") for url, _ in tx.calls))

    def test_date_validation_and_no_calls(self):
        tx = FakeTransport()
        c = YouTubeReadOnlyClient(token="dummy", transport=tx)
        for start, end in [
            ("2025/01/01", "2025-01-30"),
            ("2025-05-01", "2025-04-30"),
            ("2025-01-01", "2025-05-01"),
            ("2026-01-01", "2030-01-01"),
        ]:
            with self.assertRaises(ValueError):
                c.channel_analytics(start, end)
        self.assertEqual(tx.calls, [])

    def test_errors_never_echo_access_token(self):
        secret = "sensitive-dummy-value"
        def broken(url, headers):
            raise RuntimeError(secret)
        c = YouTubeReadOnlyClient(token=secret, transport=broken)
        with self.assertRaises(YouTubeReadOnlyError) as error:
            c.channel_profile()
        self.assertNotIn(secret, str(error.exception))

    def test_fixed_https_allowlist_and_no_upload(self):
        tx = FakeTransport()
        c = YouTubeReadOnlyClient(token="dummy", transport=tx)
        with self.assertRaisesRegex(YouTubeReadOnlyError, "ENDPOINT_NOT_ALLOWED"):
            c._get("https://evil.example/youtube/v3/channels", {"mine": "true"})
        self.assertEqual(tx.calls, [])


if __name__ == "__main__":
    unittest.main()
