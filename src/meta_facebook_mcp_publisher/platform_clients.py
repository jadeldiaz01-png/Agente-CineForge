from __future__ import annotations

import json
from typing import Callable
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
        return json.loads(response.read().decode("utf-8"))


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
        headers = {"Authorization": f"Bearer {request.access_token}", "Content-Type": "application/json"}
        raw = self.transport("POST", "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status", payload, None, headers)
        remote_id = raw.get("id") or raw.get("headers", {}).get("location")
        return PublishResult(bool(remote_id), self.platform.value, str(remote_id) if remote_id else None, "CONFIRMED" if remote_id else "UNKNOWN", raw_response=raw)


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
        return PublishResult(bool(remote_id), self.platform.value, str(remote_id) if remote_id else None, "DISPATCHED" if remote_id else "UNKNOWN", raw_response=raw)


class XClient:
    platform = Platform.X

    def __init__(self, transport: JsonTransport | None = None) -> None:
        self.transport = transport or _default_json_transport

    def publish_video(self, request: PlatformPublishRequest) -> PublishResult:
        decision = evaluate_platform_publish_gates(request)
        if not decision.allowed:
            return PublishResult(False, self.platform.value, status="BLOCKED_BY_POLICY", error=",".join(decision.failed_gates))

        headers = {"Authorization": f"Bearer {request.access_token}", "Content-Type": "application/json"}
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

