from __future__ import annotations

from dataclasses import dataclass

from .models import PlatformPublishRequest, PublishRequest


@dataclass(frozen=True)
class PublishGateDecision:
    allowed: bool
    failed_gates: tuple[str, ...]


def evaluate_publish_gates(request: PublishRequest) -> PublishGateDecision:
    failed: list[str] = []

    if not request.publishing_enabled:
        failed.append("PUBLISHING_ENABLED")
    if not request.page_id:
        failed.append("PAGE_ID_PRESENT")
    if not request.page_access_token:
        failed.append("META_TOKEN_PRESENT")
    if not request.video_path.exists() or not request.video_path.is_file():
        failed.append("VIDEO_FILE_EXISTS")
    if request.video_path.suffix.lower() != ".mp4":
        failed.append("VIDEO_IS_MP4")
    if not request.video_qc_passed:
        failed.append("VIDEO_QC_PASSED")
    if not request.originality_reviewed:
        failed.append("ORIGINALITY_REVIEWED")
    if not request.human_approved:
        failed.append("HUMAN_APPROVED")
    if not request.idempotency_key:
        failed.append("IDEMPOTENCY_KEY_PRESENT")
    if request.is_reel and request.published_count_24h >= request.reels_daily_limit:
        failed.append("REELS_RATE_LIMIT_ALLOWED")

    return PublishGateDecision(allowed=not failed, failed_gates=tuple(failed))


def evaluate_platform_publish_gates(request: PlatformPublishRequest) -> PublishGateDecision:
    failed: list[str] = []

    if not request.publishing_enabled:
        failed.append("PUBLISHING_ENABLED")
    if not request.access_token:
        failed.append("ACCESS_TOKEN_PRESENT")
    if not request.account_id:
        failed.append("ACCOUNT_ID_PRESENT")
    if not request.video_path.exists() or not request.video_path.is_file():
        failed.append("VIDEO_FILE_EXISTS")
    if request.video_path.suffix.lower() != ".mp4":
        failed.append("VIDEO_IS_MP4")
    if not request.video_qc_passed:
        failed.append("VIDEO_QC_PASSED")
    if not request.originality_reviewed:
        failed.append("ORIGINALITY_REVIEWED")
    if not request.human_approved:
        failed.append("HUMAN_APPROVED")
    if not request.idempotency_key:
        failed.append("IDEMPOTENCY_KEY_PRESENT")
    if request.published_count_24h >= request.daily_limit:
        failed.append("RATE_LIMIT_ALLOWED")
    if not request.public_posting_audited:
        failed.append("PUBLIC_POSTING_AUDITED")

    return PublishGateDecision(allowed=not failed, failed_gates=tuple(failed))
