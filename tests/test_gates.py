from pathlib import Path

from meta_facebook_mcp_publisher.gates import evaluate_publish_gates
from meta_facebook_mcp_publisher.models import PublishRequest


def test_blocks_without_human_approval(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake mp4 for policy test")

    request = PublishRequest(
        page_id="123",
        page_access_token="token",
        video_path=video,
        description="caption",
        idempotency_key="key-1",
        human_approved=False,
        video_qc_passed=True,
        originality_reviewed=True,
        publishing_enabled=True,
    )

    decision = evaluate_publish_gates(request)

    assert not decision.allowed
    assert "HUMAN_APPROVED" in decision.failed_gates


def test_allows_when_required_gates_pass(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake mp4 for policy test")

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

    assert evaluate_publish_gates(request).allowed


def test_blocks_when_reels_limit_is_reached(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake mp4 for policy test")

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
        published_count_24h=30,
    )

    decision = evaluate_publish_gates(request)

    assert not decision.allowed
    assert "REELS_RATE_LIMIT_ALLOWED" in decision.failed_gates

