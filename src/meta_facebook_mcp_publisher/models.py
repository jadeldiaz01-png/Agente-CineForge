from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class Platform(StrEnum):
    FACEBOOK = "facebook"
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    X = "x"


@dataclass(frozen=True)
class PublishRequest:
    page_id: str
    page_access_token: str
    video_path: Path
    description: str
    idempotency_key: str
    human_approved: bool
    video_qc_passed: bool
    originality_reviewed: bool
    publishing_enabled: bool = False
    is_reel: bool = True
    published_count_24h: int = 0
    reels_daily_limit: int = 30
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PlatformPublishRequest:
    platform: Platform
    video_path: Path
    caption: str
    idempotency_key: str
    human_approved: bool
    video_qc_passed: bool
    originality_reviewed: bool
    publishing_enabled: bool = False
    access_token: str = ""
    account_id: str = ""
    published_count_24h: int = 0
    daily_limit: int = 30
    public_posting_audited: bool = True
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PublishResult:
    ok: bool
    platform: str
    remote_id: str | None = None
    status: str = "UNKNOWN"
    error: str | None = None
    raw_response: dict | None = None


@dataclass(frozen=True)
class PlatformCapability:
    platform: Platform
    connected: bool
    production_ready: bool
    reason: str = ""
