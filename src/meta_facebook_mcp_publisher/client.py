from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import Callable
from urllib import request as urlrequest

from .gates import evaluate_publish_gates
from .models import PublishRequest, PublishResult

Transport = Callable[[str, dict[str, str], bytes, str], dict]


def _default_transport(url: str, fields: dict[str, str], file_bytes: bytes, filename: str) -> dict:
    boundary = "----codex-meta-publisher-boundary"
    body = _multipart_body(boundary, fields, file_bytes, filename)
    req = urlrequest.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urlrequest.urlopen(req, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def _multipart_body(boundary: str, fields: dict[str, str], file_bytes: bytes, filename: str) -> bytes:
    chunks: list[bytes] = []
    for key, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode(),
                str(value).encode(),
                b"\r\n",
            ]
        )

    content_type = mimetypes.guess_type(filename)[0] or "video/mp4"
    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="source"; filename="{filename}"\r\n'.encode(),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            file_bytes,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return b"".join(chunks)


class MetaFacebookClient:
    def __init__(self, graph_version: str = "v26.0", transport: Transport | None = None) -> None:
        self.graph_version = graph_version
        self.transport = transport or _default_transport

    def publish_video(self, publish_request: PublishRequest) -> PublishResult:
        decision = evaluate_publish_gates(publish_request)
        if not decision.allowed:
            return PublishResult(
                ok=False,
                platform="facebook",
                status="BLOCKED_BY_POLICY",
                error=",".join(decision.failed_gates),
            )

        video_path: Path = publish_request.video_path
        endpoint = f"https://graph-video.facebook.com/{self.graph_version}/{publish_request.page_id}/videos"
        fields = {
            "access_token": publish_request.page_access_token,
            "description": publish_request.description,
        }
        if publish_request.is_reel:
            fields["published"] = "true"

        try:
            raw = self.transport(endpoint, fields, video_path.read_bytes(), video_path.name)
        except Exception as exc:
            return PublishResult(ok=False, platform="facebook", status="UNKNOWN", error=str(exc))

        remote_id = str(raw.get("id")) if raw.get("id") is not None else None
        return PublishResult(
            ok=bool(remote_id),
            platform="facebook",
            remote_id=remote_id,
            status="CONFIRMED" if remote_id else "UNKNOWN",
            raw_response=raw,
        )

