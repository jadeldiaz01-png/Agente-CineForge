from __future__ import annotations

import json
from typing import Callable
from urllib.parse import urlparse
from urllib import request as urlrequest

from .gates import evaluate_platform_publish_gates
from .models import Platform, PlatformPublishRequest, PublishResult

JsonTransport = Callable[[str, str, dict, bytes | None, dict[str, str]], dict]


def _default_json_transport(
    method: str,
    url: str,
    payload: dict,
    file_bytes: bytes | None,
    headers: dict[str, str],
) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload else file_bytes
    req = urlrequest.Request(url, data=data, method=method, headers=headers)
    with urlrequest.urlopen(req, timeout=90) as response:
        content = response.read()
        result = json.loads(content.decode("utf-8")) if content else {}
        return dict(result, _http_status=response.status)


class YouTubeClient:
    platform = Platform.YOUTUBE

    def __init__(self, transport: JsonTransport | None = None) -> None:
        self.transport = transport or _default_json_transport

    def publish_video(self, request: PlatformPublishRequest) -> PublishResult:
        decision = evaluate_platform_publish_gates(request)
        if not decision.allowed:
            return PublishResult(False, self.platform.value, status="BLOCKED_BY_POLICY", error=",".join(decision.failed_gates))

        payload = {
            "snippet": {
                "title": request.metadata.get("title", "Untitled video"),
                "description": request.caption,
                "tags": [tag for tag in request.metadata.get("tags", "").split(",") if tag],
                "categoryId": request.metadata.get("category_id", "22"),
            },
            "status": {"privacyStatus": request.metadata.get("privacy_status", "private")},
        }
        headers = {"Authorization": f"Bearer {request.access_token}", "Content-Type": "application/json",
                   "X-Upload-Content-Type": "video/mp4",
                   "X-Upload-Content-Length": str(request.video_path.stat().st_size)}
        try:
            init = self.transport("POST", "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status", payload, None, headers)
            location = str((init.get("headers") or {}).get("location", ""))
            parsed = urlparse(location)
            if parsed.scheme != "https" or parsed.hostname != "www.googleapis.com":
                return PublishResult(False, self.platform.value, status="UNKNOWN", error="YOUTUBE_UPLOAD_SESSION_INVALID")
            video = request.video_path.read_bytes()
            complete = self.transport("PUT", location, {}, video,
                                      {"Authorization": f"Bearer {request.access_token}", "Content-Type": "video/mp4",
                                       "Content-Length": str(len(video))})
            rid = complete.get("id")
            return PublishResult(bool(rid), self.platform.value, str(rid) if rid else None,
                                 "UPLOAD_CONFIRMED" if rid else "UNKNOWN",
                                 None if rid else "YOUTUBE_FINAL_UPLOAD_NOT_CONFIRMED", complete)
        except Exception:
            return PublishResult(False, self.platform.value, status="UNKNOWN", error="YOUTUBE_UPLOAD_OUTCOME_UNKNOWN")


class TikTokClient:
    platform = Platform.TIKTOK

    def __init__(self, transport: JsonTransport | None = None) -> None:
        self.transport = transport or _default_json_transport

    def publish_video(self, request: PlatformPublishRequest) -> PublishResult:
        decision = evaluate_platform_publish_gates(request)
        if not decision.allowed:
            return PublishResult(False, self.platform.value, status="BLOCKED_BY_POLICY", error=",".join(decision.failed_gates))

        payload = {
            "post_info": {
                "title": request.caption,
                "privacy_level": request.metadata.get("privacy_level", "SELF_ONLY"),
                "disable_duet": request.metadata.get("disable_duet", "true") == "true",
                "disable_comment": request.metadata.get("disable_comment", "false") == "true",
                "disable_stitch": request.metadata.get("disable_stitch", "true") == "true",
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": request.video_path.stat().st_size,
                "chunk_size": request.video_path.stat().st_size,
                "total_chunk_count": 1,
            },
        }
        headers = {"Authorization": f"Bearer {request.access_token}", "Content-Type": "application/json; charset=UTF-8"}
        raw = self.transport("POST", "https://open.tiktokapis.com/v2/post/publish/video/init/", payload, None, headers)
        remote_id = raw.get("data", {}).get("publish_id")
        upload_url = str(raw.get("data", {}).get("upload_url", ""))
        parsed = urlparse(upload_url)
        if not remote_id or parsed.scheme != "https" or parsed.hostname != "open-upload.tiktokapis.com":
            return PublishResult(False, self.platform.value, status="UNKNOWN", error="TIKTOK_UPLOAD_URL_INVALID")
        size = request.video_path.stat().st_size
        if not 0 < size <= 64 * 1024 * 1024:
            return PublishResult(False, self.platform.value, status="BLOCKED_BY_POLICY", error="TIKTOK_CHUNKED_UPLOAD_NOT_CERTIFIED")
        try:
            upload = self.transport("PUT", upload_url, {}, request.video_path.read_bytes(),
                                    {"Content-Type": "video/mp4", "Content-Length": str(size),
                                     "Content-Range": f"bytes 0-{size-1}/{size}"})
        except Exception:
            return PublishResult(False, self.platform.value, status="UNKNOWN", error="TIKTOK_UPLOAD_OUTCOME_UNKNOWN")
        if upload.get("_http_status") != 201:
            return PublishResult(False, self.platform.value, status="UNKNOWN", error="TIKTOK_UPLOAD_NOT_CONFIRMED")
        # HTTP 201 is an upload transfer acknowledgment, NOT public posting confirmation.
        return PublishResult(False, self.platform.value, str(remote_id), "DISPATCHED_UNVERIFIED",
                             "TIKTOK_STATUS_RECONCILIATION_REQUIRED", upload)


class XClient:
    platform = Platform.X

    def __init__(self, transport: JsonTransport | None = None) -> None:
        self.transport = transport or _default_json_transport

    def publish_video(self, request: PlatformPublishRequest) -> PublishResult:
        decision = evaluate_platform_publish_gates(request)
        if not decision.allowed:
            return PublishResult(False, self.platform.value, status="BLOCKED_BY_POLICY", error=",".join(decision.failed_gates))

        headers = {"Authorization": f"Bearer {request.access_token}", "Content-Type": "application/json"}
        # No APPEND, FINALIZE or remote processing verification exists yet.
        return PublishResult(False, self.platform.value, status="BLOCKED_BY_POLICY",
                             error="X_VIDEO_UPLOAD_NOT_CERTIFIED")
        init_payload = {
            "media_type": "video/mp4",
            "media_category": "tweet_video",
            "total_bytes": request.video_path.stat().st_size,
        }
        media = self.transport("POST", "https://api.x.com/2/media/upload/initialize", init_payload, None, headers)
        media_id = media.get("data", {}).get("id")
        if not media_id:
            return PublishResult(False, self.platform.value, status="UNKNOWN", error="MEDIA_INIT_FAILED", raw_response=media)

        post_payload = {"text": request.caption, "media": {"media_ids": [media_id]}}
        raw = self.transport("POST", "https://api.x.com/2/tweets", post_payload, None, headers)
        remote_id = raw.get("data", {}).get("id")
        return PublishResult(bool(remote_id), self.platform.value, str(remote_id) if remote_id else None, "CONFIRMED" if remote_id else "UNKNOWN", raw_response=raw)

