from __future__ import annotations

import json
import os
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
    upload_scope = "https://www.googleapis.com/auth/youtube.upload"
    channel_scope = "https://www.googleapis.com/auth/youtube.readonly"

    def __init__(self, transport: JsonTransport | None = None) -> None:
        # Retained for backwards-compatible construction; uploads use Google's
        # client library because it implements the resumable media protocol.
        self.transport = transport

    @staticmethod
    def _credentials(access_token: str):
        try:
            from google.oauth2.credentials import Credentials
        except ImportError as exc:
            raise RuntimeError("Install the project with its YouTube dependencies.") from exc

        refresh_token = os.getenv("YOUTUBE_OAUTH_REFRESH_TOKEN", "")
        client_id = os.getenv("YOUTUBE_OAUTH_CLIENT_ID", "")
        client_secret = os.getenv("YOUTUBE_OAUTH_CLIENT_SECRET", "")
        if refresh_token and not (client_id and client_secret):
            raise RuntimeError("OAuth refresh requires the configured OAuth client ID and secret.")
        return Credentials(
            token=None if refresh_token else (access_token or None),
            refresh_token=refresh_token or None,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id or None,
            client_secret=client_secret or None,
            scopes=[YouTubeClient.upload_scope, YouTubeClient.channel_scope],
        )

    @classmethod
    def _service(cls, access_token: str):
        try:
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise RuntimeError("Install the project with its YouTube dependencies.") from exc
        return build("youtube", "v3", credentials=cls._credentials(access_token), cache_discovery=False)

    def get_channel_info(self, access_token: str, expected_channel_id: str) -> dict:
        if not expected_channel_id:
            raise ValueError("YOUTUBE_CHANNEL_ID is required.")
        response = self._service(access_token).channels().list(part="id,snippet", mine=True).execute()
        items = response.get("items", [])
        if len(items) != 1 or items[0].get("id") != expected_channel_id:
            raise ValueError("The authorized Google account does not match YOUTUBE_CHANNEL_ID.")
        snippet = items[0].get("snippet", {})
        return {"channel_id": items[0]["id"], "title": snippet.get("title", "")}

    def publish_video(self, request: PlatformPublishRequest) -> PublishResult:
        decision = evaluate_platform_publish_gates(request)
        if not decision.allowed:
            return PublishResult(False, self.platform.value, status="BLOCKED_BY_POLICY", error=",".join(decision.failed_gates))

        privacy = request.metadata.get("privacy_status", "private")
        if privacy not in {"private", "unlisted", "public"}:
            return PublishResult(False, self.platform.value, status="BLOCKED_BY_POLICY", error="INVALID_PRIVACY_STATUS")
        if privacy == "public" and not request.public_posting_audited:
            return PublishResult(False, self.platform.value, status="BLOCKED_BY_POLICY", error="PUBLIC_POSTING_AUDIT_REQUIRED")

        try:
            channel = self.get_channel_info(request.access_token, request.account_id)
            from googleapiclient.http import MediaFileUpload

            raw_tags = request.metadata.get("tags", "")
            tags = raw_tags if isinstance(raw_tags, list) else [tag.strip() for tag in raw_tags.split(",") if tag.strip()]
            payload = {
                "snippet": {
                    "title": request.metadata.get("title", "Untitled video"),
                    "description": request.caption,
                    "tags": tags,
                    "categoryId": request.metadata.get("category_id", "22"),
                },
                "status": {
                    "privacyStatus": privacy,
                    "selfDeclaredMadeForKids": request.metadata.get("made_for_kids", "false") == "true",
                },
            }
            upload = self._service(request.access_token).videos().insert(
                part="snippet,status",
                body=payload,
                media_body=MediaFileUpload(
                    str(request.video_path), mimetype="video/mp4",
                    chunksize=8 * 1024 * 1024, resumable=True,
                ),
            )
            response = None
            while response is None:
                _, response = upload.next_chunk()
            video_id = response.get("id")
            return PublishResult(
                bool(video_id), self.platform.value, str(video_id) if video_id else None,
                "CONFIRMED" if video_id else "UNKNOWN",
                error=None if video_id else "YOUTUBE_UPLOAD_RETURNED_NO_VIDEO_ID",
                raw_response={"channel_id": channel["channel_id"], "video_id": video_id},
            )
        except Exception as exc:
            # Avoid returning third-party request details that may contain secrets.
            return PublishResult(
                False, self.platform.value, status="UNKNOWN",
                error=f"YOUTUBE_UPLOAD_FAILED:{type(exc).__name__}",
            )


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

