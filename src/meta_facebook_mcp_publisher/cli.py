from __future__ import annotations

import argparse
import os
from pathlib import Path

from .client import MetaFacebookClient
from .models import Platform, PlatformCapability, PlatformPublishRequest, PublishRequest, PublishResult
from .orchestrator import MultiPlatformPublisher
from .platform_clients import TikTokClient, XClient, YouTubeClient


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _print_result(result: PublishResult) -> None:
    remote = result.remote_id or "-"
    error = result.error or "-"
    print(f"{result.platform}\t{result.status}\tok={result.ok}\tremote_id={remote}\terror={error}")


def run() -> int:
    parser = argparse.ArgumentParser(description="Run gated social video publishing.")
    parser.add_argument("--video", required=True, help="Path to the approved MP4 video.")
    parser.add_argument("--caption", required=True, help="Caption/description to publish.")
    parser.add_argument("--platforms", required=True, help="Comma-separated platforms: facebook,youtube,tiktok,x")
    parser.add_argument("--idempotency-key", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--human-approved", action="store_true")
    parser.add_argument("--video-qc-passed", action="store_true")
    parser.add_argument("--originality-reviewed", action="store_true")
    args = parser.parse_args()

    video_path = Path(args.video)
    selected = [Platform(item.strip()) for item in args.platforms.split(",") if item.strip()]

    if args.dry_run:
        for platform in selected:
            _print_result(PublishResult(True, platform.value, status="DRY_RUN_CONFIRMED", remote_id="dry-run"))
        return 0

    capabilities = {
        Platform.FACEBOOK: PlatformCapability(
            Platform.FACEBOOK,
            connected=bool(os.getenv("META_PAGE_ACCESS_TOKEN") and os.getenv("META_PAGE_ID")),
            production_ready=_env_bool("META_PUBLISHING_ENABLED"),
            reason="Meta Page credentials or production flag missing",
        ),
        Platform.YOUTUBE: PlatformCapability(
            Platform.YOUTUBE,
            connected=bool(os.getenv("YOUTUBE_OAUTH_ACCESS_TOKEN") and os.getenv("YOUTUBE_CHANNEL_ID")),
            production_ready=_env_bool("YOUTUBE_PUBLISHING_ENABLED"),
            reason="YouTube OAuth credentials or production flag missing",
        ),
        Platform.TIKTOK: PlatformCapability(
            Platform.TIKTOK,
            connected=bool(os.getenv("TIKTOK_ACCESS_TOKEN") and os.getenv("TIKTOK_ACCOUNT_ID")),
            production_ready=_env_bool("TIKTOK_PUBLISHING_ENABLED"),
            reason="TikTok OAuth credentials, audit, or production flag missing",
        ),
        Platform.X: PlatformCapability(
            Platform.X,
            connected=bool(os.getenv("X_USER_ACCESS_TOKEN") and os.getenv("X_ACCOUNT_ID")),
            production_ready=_env_bool("X_PUBLISHING_ENABLED"),
            reason="X user token or production flag missing",
        ),
    }
    publisher = MultiPlatformPublisher(
        clients={
            Platform.YOUTUBE: YouTubeClient(),
            Platform.TIKTOK: TikTokClient(),
            Platform.X: XClient(),
        },
        capabilities=capabilities,
    )

    results: list[PublishResult] = []
    for platform in selected:
        if platform == Platform.FACEBOOK:
            req = PublishRequest(
                page_id=os.getenv("META_PAGE_ID", ""),
                page_access_token=os.getenv("META_PAGE_ACCESS_TOKEN", ""),
                video_path=video_path,
                description=args.caption,
                idempotency_key=args.idempotency_key,
                human_approved=args.human_approved,
                video_qc_passed=args.video_qc_passed,
                originality_reviewed=args.originality_reviewed,
                publishing_enabled=_env_bool("META_PUBLISHING_ENABLED"),
                published_count_24h=int(os.getenv("META_PUBLISHED_COUNT_24H", "0")),
                reels_daily_limit=int(os.getenv("META_REELS_DAILY_LIMIT", "30")),
            )
            results.append(MetaFacebookClient(os.getenv("META_GRAPH_VERSION", "v26.0")).publish_video(req))
            continue

        account_env = {
            Platform.YOUTUBE: ("YOUTUBE_CHANNEL_ID", "YOUTUBE_OAUTH_ACCESS_TOKEN", "YOUTUBE_DAILY_UPLOAD_LIMIT"),
            Platform.TIKTOK: ("TIKTOK_ACCOUNT_ID", "TIKTOK_ACCESS_TOKEN", "TIKTOK_DAILY_POST_LIMIT"),
            Platform.X: ("X_ACCOUNT_ID", "X_USER_ACCESS_TOKEN", "X_DAILY_POST_LIMIT"),
        }[platform]
        requests = [
            PlatformPublishRequest(
                platform=platform,
                video_path=video_path,
                caption=args.caption,
                idempotency_key=f"{args.idempotency_key}:{platform.value}",
                human_approved=args.human_approved,
                video_qc_passed=args.video_qc_passed,
                originality_reviewed=args.originality_reviewed,
                publishing_enabled=_env_bool(f"{platform.value.upper()}_PUBLISHING_ENABLED"),
                access_token=os.getenv(account_env[1], ""),
                account_id=os.getenv(account_env[0], ""),
                daily_limit=int(os.getenv(account_env[2], "30")),
                public_posting_audited=_env_bool("TIKTOK_PUBLIC_POSTING_AUDITED", True)
                if platform == Platform.TIKTOK
                else True,
            )
        ]
        results.extend(publisher.publish_many(requests))

    for result in results:
        _print_result(result)

    return 0 if all(result.ok for result in results) else 2


if __name__ == "__main__":
    raise SystemExit(run())

