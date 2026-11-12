"""Fail-closed, GET-only YouTube channel and analytics client.

Authentication is a separately consented OAuth 2.0 access token with READ-ONLY
Google scopes. This module never initiates OAuth or publishes videos.
"""

from __future__ import annotations

from datetime import date, timedelta
import json
import os
import re
from typing import Callable, Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


DATA_API = "https://www.googleapis.com/youtube/v3"
ANALYTICS_API = "https://youtubeanalytics.googleapis.com/v2/reports"
ALLOWED_HOSTS = frozenset({"www.googleapis.com", "youtubeanalytics.googleapis.com"})
Transport = Callable[[str, dict[str, str]], dict[str, Any]]


class YouTubeReadOnlyError(Exception):
    """A sanitized connection/authorization error that excludes credentials."""


def _https_get_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=12) as response:
            result = json.loads(response.read(1_000_001).decode("utf-8"))
    except HTTPError as exc:
        raise YouTubeReadOnlyError(f"YOUTUBE_HTTP_{exc.code}") from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise YouTubeReadOnlyError("YOUTUBE_NETWORK_OR_RESPONSE_ERROR") from None
    if not isinstance(result, dict):
        raise YouTubeReadOnlyError("YOUTUBE_INVALID_RESPONSE")
    return result


def _iso_date(text: str) -> date:
    if not isinstance(text, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise ValueError("DATE_MUST_BE_YYYY_MM_DD")
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise ValueError("INVALID_DATE") from None


class YouTubeReadOnlyClient:
    def __init__(self, token: str | None = None, transport: Transport | None = None):
        self._token = (token if token is not None else os.environ.get("YOUTUBE_READONLY_ACCESS_TOKEN", "")).strip()
        self._transport = transport or _https_get_json

    def _get(self, base: str, params: dict[str, object]) -> dict[str, Any]:
        if not self._token:
            raise YouTubeReadOnlyError("YOUTUBE_READONLY_OAUTH_NOT_CONNECTED")
        url = base + "?" + urlencode(params)
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
            raise YouTubeReadOnlyError("YOUTUBE_ENDPOINT_NOT_ALLOWED")
        if not (
            (base.startswith(DATA_API + "/") and parsed.hostname == "www.googleapis.com")
            or (base == ANALYTICS_API and parsed.hostname == "youtubeanalytics.googleapis.com")
        ):
            raise YouTubeReadOnlyError("YOUTUBE_ENDPOINT_NOT_ALLOWED")
        try:
            data = self._transport(
                url,
                {"Authorization": "Bearer " + self._token, "Accept": "application/json"},
            )
        except YouTubeReadOnlyError:
            raise
        except Exception:
            # Do not allow transport exception details (possibly containing token) to escape.
            raise YouTubeReadOnlyError("YOUTUBE_TRANSPORT_FAILED") from None
        if not isinstance(data, dict):
            raise YouTubeReadOnlyError("YOUTUBE_INVALID_RESPONSE")
        if "error" in data:
            raise YouTubeReadOnlyError("YOUTUBE_API_ERROR")
        return data

    def _mine(self, part: str) -> dict[str, Any]:
        response = self._get(DATA_API + "/channels", {"part": part, "mine": "true"})
        items = response.get("items") or []
        if not isinstance(items, list) or not items or not isinstance(items[0], dict):
            raise YouTubeReadOnlyError("YOUTUBE_CHANNEL_NOT_FOUND")
        return items[0]

    def _require_pinned_channel(self, channel: dict[str, Any]) -> None:
        """Require owner-confirmed channel identity for analytics and video lists."""
        expected = os.environ.get("YOUTUBE_EXPECTED_CHANNEL_ID", "").strip()
        if not re.fullmatch(r"UC[A-Za-z0-9_-]{22}", expected):
            raise YouTubeReadOnlyError("YOUTUBE_EXPECTED_CHANNEL_NOT_CONFIGURED")
        if channel.get("id") != expected:
            raise YouTubeReadOnlyError("YOUTUBE_CHANNEL_ID_MISMATCH")

    def channel_profile(self) -> dict[str, Any]:
        """Read metadata for the account/channel chosen during OAuth."""
        data = self._mine("snippet,statistics")
        snippet, stats = data.get("snippet") or {}, data.get("statistics") or {}
        return {
            "channel_id": data.get("id"),
            "title": snippet.get("title"),
            "published_at": snippet.get("publishedAt"),
            "views": stats.get("viewCount"),
            "subscribers": stats.get("subscriberCount"),
            "videos": stats.get("videoCount"),
            "subscribers_hidden": stats.get("hiddenSubscriberCount", False),
            "source": "YouTube Data API channels.list mine=true",
        }

    def recent_videos(self, limit: int = 5) -> dict[str, Any]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
            raise ValueError("LIMIT_MUST_BE_1_TO_20")
        channel = self._mine("contentDetails")
        self._require_pinned_channel(channel)
        uploads = (channel.get("contentDetails") or {}).get("relatedPlaylists") or {}
        playlist_id = uploads.get("uploads")
        if not isinstance(playlist_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{2,100}", playlist_id):
            raise YouTubeReadOnlyError("UPLOADS_PLAYLIST_MISSING")
        data = self._get(DATA_API + "/playlistItems", {
            "part": "snippet,contentDetails", "playlistId": playlist_id, "maxResults": limit
        })
        items = data.get("items") or []
        return {
            "channel_id": channel.get("id"),
            "videos": [
                {
                    "video_id": (item.get("contentDetails") or {}).get("videoId"),
                    "title": (item.get("snippet") or {}).get("title"),
                    "published_at": (item.get("contentDetails") or {}).get("videoPublishedAt"),
                }
                for item in items[:limit] if isinstance(item, dict)
            ],
            "source": "YouTube Data API playlistItems.list",
        }

    def channel_analytics(self, start_date: str, end_date: str) -> dict[str, Any]:
        start, end = _iso_date(start_date), _iso_date(end_date)
        if end < start or (end - start) > timedelta(days=90):
            raise ValueError("DATE_WINDOW_MUST_BE_0_TO_90_DAYS")
        if end > date.today():
            raise ValueError("END_DATE_MUST_NOT_BE_IN_FUTURE")
        # Never query analytics for an unpinned or mismatching OAuth identity.
        channel = self._mine("id")
        self._require_pinned_channel(channel)
        metrics = "views,estimatedMinutesWatched,subscribersGained"
        response = self._get(ANALYTICS_API, {
            "ids": "channel==MINE", "startDate": start_date,
            "endDate": end_date, "metrics": metrics,
        })
        headers = response.get("columnHeaders") or []
        rows = response.get("rows") or []
        column_names = [h.get("name") for h in headers if isinstance(h, dict)]
        if not rows:
            values: dict[str, Any] = {}
        elif len(rows) == 1 and len(rows[0]) == len(column_names):
            values = dict(zip(column_names, rows[0]))
        else:
            raise YouTubeReadOnlyError("ANALYTICS_INVALID_SHAPE")
        return {
            "start_date": start_date, "end_date": end_date, "metrics": values,
            "data_available": bool(rows), "source": "YouTube Analytics API reports.query",
            "note": "Analytics may lag; no revenue metrics requested or inferred.",
        }
