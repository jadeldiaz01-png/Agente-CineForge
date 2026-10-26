"""Read-only external status reconciler: never interprets upload as public release.

This read is explicitly separate from the publication command. Remote ids must
be associated with the reserved attempt in a trusted operations ledger.
"""
from __future__ import annotations

import json
import re
from urllib import request as urlrequest
from urllib.parse import urlencode

from .models import PublishResult


class ReconciliationError(ValueError):
    pass


def _read_json(method: str, url: str, token: str, body: dict | None = None) -> dict:
    encoded = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json; charset=UTF-8"
    req = urlrequest.Request(url, method=method, headers=headers, data=encoded)
    with urlrequest.urlopen(req, timeout=20) as response:
        if response.geturl() != url:
            raise ReconciliationError("REDIRECT_NOT_ALLOWED")
        data = response.read(512 * 1024 + 1)
        if len(data) > 512 * 1024:
            raise ReconciliationError("RESPONSE_TOO_LARGE")
        parsed = json.loads(data)
        if not isinstance(parsed, dict):
            raise ReconciliationError("RESPONSE_NOT_OBJECT")
        return parsed


def tiktok_status(publish_id: str, access_token: str, transport=None) -> PublishResult:
    if not access_token or not isinstance(publish_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:~\-]{1,64}", publish_id):
        return PublishResult(False, "tiktok", status="RECONCILIATION_BLOCKED", error="ID_OR_TOKEN_INVALID")
    transport = transport or _read_json
    try:
        response = transport("POST", "https://open.tiktokapis.com/v2/post/publish/status/fetch/",
                             access_token, {"publish_id": publish_id})
        if (response.get("error") or {}).get("code") != "ok":
            return PublishResult(False, "tiktok", status="UNKNOWN", error="TIKTOK_STATUS_QUERY_UNVERIFIED")
        data = response.get("data") or {}
        status = data.get("status")
        if status == "FAILED":
            return PublishResult(False, "tiktok", status="REMOTE_FAILED", error="TIKTOK_REMOTE_FAILED")
        ids = data.get("publicaly_available_post_id") or []
        if status == "PUBLISH_COMPLETE" and isinstance(ids, list) and ids:
            post_id = str(ids[0])
            if re.fullmatch(r"[0-9]{6,32}", post_id):
                return PublishResult(True, "tiktok", remote_id=post_id, status="CONFIRMED_PUBLIC")
        return PublishResult(False, "tiktok", status="REMOTE_UNVERIFIED", error="TIKTOK_NOT_PUBLICLY_AVAILABLE")
    except (OSError, ValueError, TypeError, KeyError):
        return PublishResult(False, "tiktok", status="UNKNOWN", error="TIKTOK_STATUS_QUERY_FAILED")


def youtube_status(video_id: str, access_token: str, transport=None) -> PublishResult:
    if not access_token or not isinstance(video_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{6,32}", video_id):
        return PublishResult(False, "youtube", status="RECONCILIATION_BLOCKED", error="ID_OR_TOKEN_INVALID")
    transport = transport or _read_json
    query = urlencode({"id": video_id, "part": "status"})
    try:
        response = transport("GET", f"https://www.googleapis.com/youtube/v3/videos?{query}", access_token)
        items = response.get("items") or []
        matched = next((v for v in items if v.get("id") == video_id), None)
        if not matched:
            return PublishResult(False, "youtube", status="REMOTE_UNVERIFIED", error="YOUTUBE_ID_NOT_VERIFIED")
        status = matched.get("status") or {}
        if status.get("uploadStatus") in {"failed", "rejected", "deleted"}:
            return PublishResult(False, "youtube", status="REMOTE_FAILED", error="YOUTUBE_REMOTE_FAILED")
        if status.get("uploadStatus") == "processed" and status.get("privacyStatus") == "public":
            return PublishResult(True, "youtube", remote_id=video_id, status="CONFIRMED_PUBLIC")
        return PublishResult(False, "youtube", status="REMOTE_UNVERIFIED", error="YOUTUBE_NOT_PUBLICLY_AVAILABLE")
    except (OSError, ValueError, TypeError, KeyError):
        return PublishResult(False, "youtube", status="UNKNOWN", error="YOUTUBE_STATUS_QUERY_FAILED")
