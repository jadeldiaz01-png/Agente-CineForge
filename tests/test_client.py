from pathlib import Path

from meta_facebook_mcp_publisher import MetaFacebookClient, PublishRequest


def test_client_does_not_call_transport_when_blocked(tmp_path: Path) -> None:
    calls = []

    def transport(url: str, fields: dict[str, str], file_bytes: bytes, filename: str) -> dict:
        calls.append((url, fields, file_bytes, filename))
        return {"id": "remote-id"}

    request = PublishRequest(
        page_id="123",
        page_access_token="token",
        video_path=tmp_path / "missing.mp4",
        description="caption",
        idempotency_key="key-1",
        human_approved=True,
        video_qc_passed=True,
        originality_reviewed=True,
        publishing_enabled=True,
    )

    result = MetaFacebookClient(transport=transport).publish_video(request)

    assert not result.ok
    assert result.status == "BLOCKED_BY_POLICY"
    assert calls == []


def test_client_posts_to_graph_video_endpoint(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake mp4 for client test")
    captured = {}

    def transport(url: str, fields: dict[str, str], file_bytes: bytes, filename: str) -> dict:
        captured["url"] = url
        captured["fields"] = fields
        captured["file_bytes"] = file_bytes
        captured["filename"] = filename
        return {"id": "987654321"}

    request = PublishRequest(
        page_id="123",
        page_access_token="token",
        video_path=video,
        description="caption",
        idempotency_key="key-1",
        human_approved=True,
        video_qc_passed=True,
        originality_reviewed=True,
        publishing_enabled=True,
    )

    result = MetaFacebookClient(graph_version="v26.0", transport=transport).publish_video(request)

    assert result.ok
    assert result.remote_id == "987654321"
    assert captured["url"] == "https://graph-video.facebook.com/v26.0/123/videos"
    assert captured["fields"]["description"] == "caption"
    assert captured["filename"] == "video.mp4"

