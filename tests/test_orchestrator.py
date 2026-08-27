from pathlib import Path

from meta_facebook_mcp_publisher import (
    MultiPlatformPublisher,
    Platform,
    PlatformCapability,
    PlatformPublishRequest,
    PublishResult,
)


class FakeClient:
    def publish_video(self, request: PlatformPublishRequest) -> PublishResult:
        return PublishResult(True, request.platform.value, remote_id="remote-1", status="CONFIRMED")


def test_missing_connector_degrades_only_that_platform(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake mp4")

    publisher = MultiPlatformPublisher(
        clients={Platform.YOUTUBE: FakeClient()},
        capabilities={
            Platform.YOUTUBE: PlatformCapability(Platform.YOUTUBE, connected=True, production_ready=True),
            Platform.TIKTOK: PlatformCapability(Platform.TIKTOK, connected=False, production_ready=False, reason="missing oauth"),
        },
    )

    requests = [
        PlatformPublishRequest(
            platform=Platform.YOUTUBE,
            video_path=video,
            caption="caption",
            idempotency_key="yt-1",
            human_approved=True,
            video_qc_passed=True,
            originality_reviewed=True,
            publishing_enabled=True,
            access_token="token",
            account_id="channel",
        ),
        PlatformPublishRequest(
            platform=Platform.TIKTOK,
            video_path=video,
            caption="caption",
            idempotency_key="tt-1",
            human_approved=True,
            video_qc_passed=True,
            originality_reviewed=True,
            publishing_enabled=True,
            access_token="token",
            account_id="creator",
        ),
    ]

    results = publisher.publish_many(requests)

    assert results[0].ok
    assert results[1].status == "DEGRADED_NOT_CONNECTED"
