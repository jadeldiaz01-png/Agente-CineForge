from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
import json
import math
from pathlib import Path

from .models import Platform


class TrendDecisionStatus(StrEnum):
    APPROVED_FOR_BRIEF = "APPROVED_FOR_BRIEF"
    NEEDS_MORE_EVIDENCE = "NEEDS_MORE_EVIDENCE"
    BLOCKED_POLICY_RISK = "BLOCKED_POLICY_RISK"
    BLOCKED_RIGHTS_RISK = "BLOCKED_RIGHTS_RISK"
    BLOCKED_LOW_QUALITY = "BLOCKED_LOW_QUALITY"


@dataclass(frozen=True)
class PlatformTrendSpec:
    platform: Platform
    preferred_ratio: str
    preferred_resolution: str
    preferred_duration_seconds: tuple[int, int]
    preferred_codecs: tuple[str, ...]
    trend_sources: tuple[str, ...]
    required_quality_gates: tuple[str, ...]


@dataclass(frozen=True)
class TrendSignal:
    platform: Platform
    topic: str
    source: str
    source_url: str
    observed_at: datetime
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    saves: int = 0
    reposts: int = 0
    published_at: datetime | None = None
    creator_followers: int | None = None
    region: str = "global"
    category: str = "general"
    evidence_level: str = "observed"


@dataclass(frozen=True)
class TrendCandidate:
    topic: str
    platforms: tuple[Platform, ...]
    signals: tuple[TrendSignal, ...]
    audience: str
    creative_angle: str
    hook_pattern: str
    originality_risk: float
    policy_risk: float
    rights_verified: bool
    source_urls: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TrendScore:
    topic: str
    score: float
    opportunity: float
    engagement_quality: float
    velocity: float
    freshness: float
    cross_platform_fit: float
    risk_penalty: float
    status: TrendDecisionStatus
    failed_gates: tuple[str, ...]


@dataclass(frozen=True)
class CreativeBrief:
    topic: str
    target_platforms: tuple[Platform, ...]
    hook: str
    premise: str
    format_notes: tuple[str, ...]
    quality_gates: tuple[str, ...]
    evidence_urls: tuple[str, ...]
    trend_score: TrendScore


PLATFORM_TREND_SPECS: dict[Platform, PlatformTrendSpec] = {
    Platform.FACEBOOK: PlatformTrendSpec(
        platform=Platform.FACEBOOK,
        preferred_ratio="9:16",
        preferred_resolution="1080x1920",
        preferred_duration_seconds=(15, 90),
        preferred_codecs=("H.264", "H.265"),
        trend_sources=("Meta insights", "Facebook Reels performance", "public platform references"),
        required_quality_gates=("vertical_9_16", "mp4", "caption_safe_zone", "rights_review", "human_approval"),
    ),
    Platform.YOUTUBE: PlatformTrendSpec(
        platform=Platform.YOUTUBE,
        preferred_ratio="9:16",
        preferred_resolution="1080x1920",
        preferred_duration_seconds=(15, 60),
        preferred_codecs=("H.264", "AAC"),
        trend_sources=("YouTube Data API videos.list chart=mostPopular", "channel analytics", "search trend samples"),
        required_quality_gates=("shorts_safe_zone", "thumbnail_or_first_frame", "retention_hook", "rights_review", "human_approval"),
    ),
    Platform.TIKTOK: PlatformTrendSpec(
        platform=Platform.TIKTOK,
        preferred_ratio="9:16",
        preferred_resolution="1080x1920",
        preferred_duration_seconds=(5, 60),
        preferred_codecs=("H.264", "AAC"),
        trend_sources=("TikTok Research API where permitted", "TikTok Creative Center", "account analytics"),
        required_quality_gates=("fast_hook", "native_caption_style", "no_watermark_reuse", "rights_review", "human_approval"),
    ),
    Platform.X: PlatformTrendSpec(
        platform=Platform.X,
        preferred_ratio="9:16",
        preferred_resolution="1080x1920",
        preferred_duration_seconds=(6, 140),
        preferred_codecs=("H.264", "AAC"),
        trend_sources=("X API posts/search where plan permits", "media metrics", "topic monitoring"),
        required_quality_gates=("mobile_legible_text", "chunked_upload_ready", "alt_text_ready", "rights_review", "human_approval"),
    ),
}


REQUIRED_INTELLIGENCE_LAYERS: tuple[str, ...] = (
    "platform_api_connector",
    "trend_signal_ingestion",
    "metric_normalization",
    "velocity_and_freshness_scoring",
    "cross_platform_fit_scoring",
    "audience_and_category_mapping",
    "rights_and_originality_review",
    "policy_and_safety_review",
    "premium_video_quality_spec",
    "creative_brief_generation",
    "human_approval_gate",
    "evidence_and_lineage_ledger",
    "post_publish_metrics_feedback",
)


def list_required_trend_layers() -> tuple[str, ...]:
    return REQUIRED_INTELLIGENCE_LAYERS


def score_trend_candidate(candidate: TrendCandidate, now: datetime | None = None) -> TrendScore:
    if not candidate.signals:
        return TrendScore(
            topic=candidate.topic,
            score=0.0,
            opportunity=0.0,
            engagement_quality=0.0,
            velocity=0.0,
            freshness=0.0,
            cross_platform_fit=0.0,
            risk_penalty=1.0,
            status=TrendDecisionStatus.NEEDS_MORE_EVIDENCE,
            failed_gates=("TREND_SIGNAL_PRESENT",),
        )

    now = now or datetime.now(UTC)
    engagement_quality = _engagement_quality(candidate.signals)
    velocity = _velocity(candidate.signals, now)
    freshness = _freshness(candidate.signals, now)
    cross_platform_fit = min(1.0, len(set(candidate.platforms)) / 4)
    opportunity = (0.35 * engagement_quality) + (0.30 * velocity) + (0.20 * freshness) + (0.15 * cross_platform_fit)
    risk_penalty = min(1.0, (candidate.originality_risk * 0.55) + (candidate.policy_risk * 0.45))
    score = max(0.0, min(1.0, opportunity * (1.0 - risk_penalty)))

    failed: list[str] = []
    if len(candidate.signals) < 2:
        failed.append("MINIMUM_TWO_EVIDENCE_SIGNALS")
    if not candidate.rights_verified:
        failed.append("RIGHTS_VERIFIED")
    if candidate.originality_risk > 0.35:
        failed.append("ORIGINALITY_RISK_ALLOWED")
    if candidate.policy_risk > 0.25:
        failed.append("POLICY_RISK_ALLOWED")
    if score < 0.45:
        failed.append("MINIMUM_PREMIUM_OPPORTUNITY_SCORE")

    status = TrendDecisionStatus.APPROVED_FOR_BRIEF
    if "RIGHTS_VERIFIED" in failed or "ORIGINALITY_RISK_ALLOWED" in failed:
        status = TrendDecisionStatus.BLOCKED_RIGHTS_RISK
    elif "POLICY_RISK_ALLOWED" in failed:
        status = TrendDecisionStatus.BLOCKED_POLICY_RISK
    elif "MINIMUM_PREMIUM_OPPORTUNITY_SCORE" in failed:
        status = TrendDecisionStatus.BLOCKED_LOW_QUALITY
    elif failed:
        status = TrendDecisionStatus.NEEDS_MORE_EVIDENCE

    return TrendScore(
        topic=candidate.topic,
        score=round(score, 4),
        opportunity=round(opportunity, 4),
        engagement_quality=round(engagement_quality, 4),
        velocity=round(velocity, 4),
        freshness=round(freshness, 4),
        cross_platform_fit=round(cross_platform_fit, 4),
        risk_penalty=round(risk_penalty, 4),
        status=status,
        failed_gates=tuple(failed),
    )


def build_creative_brief(candidate: TrendCandidate, now: datetime | None = None) -> CreativeBrief:
    trend_score = score_trend_candidate(candidate, now)
    platform_notes = tuple(
        f"{spec.platform.value}: {spec.preferred_ratio}, {spec.preferred_resolution}, {spec.preferred_duration_seconds[0]}-{spec.preferred_duration_seconds[1]}s"
        for spec in (PLATFORM_TREND_SPECS[platform] for platform in candidate.platforms)
    )
    gates = tuple(dict.fromkeys(gate for platform in candidate.platforms for gate in PLATFORM_TREND_SPECS[platform].required_quality_gates))
    return CreativeBrief(
        topic=candidate.topic,
        target_platforms=candidate.platforms,
        hook=candidate.hook_pattern,
        premise=candidate.creative_angle,
        format_notes=platform_notes,
        quality_gates=gates,
        evidence_urls=tuple(dict.fromkeys(candidate.source_urls or tuple(signal.source_url for signal in candidate.signals))),
        trend_score=trend_score,
    )


def load_candidates_jsonl(path: Path) -> tuple[TrendCandidate, ...]:
    candidates: list[TrendCandidate] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        try:
            candidates.append(_candidate_from_payload(payload))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid trend candidate JSONL at line {line_number}: {exc}") from exc
    return tuple(candidates)


def rank_creative_briefs(candidates: tuple[TrendCandidate, ...], now: datetime | None = None) -> tuple[CreativeBrief, ...]:
    briefs = tuple(build_creative_brief(candidate, now) for candidate in candidates)
    return tuple(sorted(briefs, key=lambda brief: brief.trend_score.score, reverse=True))


def _candidate_from_payload(payload: dict) -> TrendCandidate:
    signals = tuple(
        TrendSignal(
            platform=Platform(signal["platform"]),
            topic=signal.get("topic", payload["topic"]),
            source=signal["source"],
            source_url=signal["source_url"],
            observed_at=_parse_datetime(signal["observed_at"]),
            views=int(signal.get("views", 0)),
            likes=int(signal.get("likes", 0)),
            comments=int(signal.get("comments", 0)),
            shares=int(signal.get("shares", 0)),
            saves=int(signal.get("saves", 0)),
            reposts=int(signal.get("reposts", 0)),
            published_at=_parse_datetime(signal["published_at"]) if signal.get("published_at") else None,
            creator_followers=signal.get("creator_followers"),
            region=signal.get("region", "global"),
            category=signal.get("category", "general"),
            evidence_level=signal.get("evidence_level", "observed"),
        )
        for signal in payload.get("signals", ())
    )
    return TrendCandidate(
        topic=payload["topic"],
        platforms=tuple(Platform(platform) for platform in payload["platforms"]),
        signals=signals,
        audience=payload.get("audience", "general"),
        creative_angle=payload["creative_angle"],
        hook_pattern=payload["hook_pattern"],
        originality_risk=float(payload.get("originality_risk", 1.0)),
        policy_risk=float(payload.get("policy_risk", 1.0)),
        rights_verified=bool(payload.get("rights_verified", False)),
        source_urls=tuple(payload.get("source_urls", ())),
    )


def _engagement_quality(signals: tuple[TrendSignal, ...]) -> float:
    rates: list[float] = []
    for signal in signals:
        if signal.views <= 0:
            continue
        meaningful_actions = signal.likes + (2 * signal.comments) + (3 * signal.shares) + (2 * signal.saves) + (2 * signal.reposts)
        rates.append(min(1.0, meaningful_actions / max(signal.views, 1) * 20))
    return sum(rates) / len(rates) if rates else 0.0


def _velocity(signals: tuple[TrendSignal, ...], now: datetime) -> float:
    velocities: list[float] = []
    for signal in signals:
        reference = signal.published_at or signal.observed_at
        age_hours = max(1.0, (now - reference).total_seconds() / 3600)
        views_per_hour = signal.views / age_hours
        velocities.append(min(1.0, math.log10(max(views_per_hour, 1)) / 5))
    return sum(velocities) / len(velocities) if velocities else 0.0


def _freshness(signals: tuple[TrendSignal, ...], now: datetime) -> float:
    ages = [max(0.0, (now - signal.observed_at).total_seconds() / 3600) for signal in signals]
    if not ages:
        return 0.0
    average_age = sum(ages) / len(ages)
    return max(0.0, min(1.0, 1.0 - (average_age / 168)))


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
