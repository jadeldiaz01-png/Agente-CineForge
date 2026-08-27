from __future__ import annotations

from datetime import UTC, datetime, timedelta

from meta_facebook_mcp_publisher.models import Platform
from meta_facebook_mcp_publisher.trend_intelligence import (
    TrendCandidate,
    TrendDecisionStatus,
    TrendSignal,
    build_creative_brief,
    list_required_trend_layers,
    score_trend_candidate,
)


def test_high_quality_cross_platform_candidate_is_approved_for_brief() -> None:
    now = datetime(2026, 8, 27, tzinfo=UTC)
    candidate = TrendCandidate(
        topic="premium ai video workflow",
        platforms=(Platform.FACEBOOK, Platform.YOUTUBE, Platform.TIKTOK),
        signals=(
            TrendSignal(
                platform=Platform.YOUTUBE,
                topic="premium ai video workflow",
                source="youtube_data_api",
                source_url="https://developers.google.com/youtube/v3/docs/videos/list",
                observed_at=now - timedelta(hours=2),
                published_at=now - timedelta(hours=8),
                views=500_000,
                likes=42_000,
                comments=2_100,
                shares=8_000,
                saves=5_000,
            ),
            TrendSignal(
                platform=Platform.FACEBOOK,
                topic="premium ai video workflow",
                source="meta_insights",
                source_url="https://developers.facebook.com/documentation/video-api/guides/reels-publishing",
                observed_at=now - timedelta(hours=3),
                published_at=now - timedelta(hours=10),
                views=320_000,
                likes=22_000,
                comments=1_500,
                shares=6_000,
                saves=4_000,
            ),
        ),
        audience="creators and small businesses",
        creative_angle="Show a before/after transformation from raw idea to polished Reel.",
        hook_pattern="Most videos fail before the first second. Fix this first.",
        originality_risk=0.1,
        policy_risk=0.05,
        rights_verified=True,
    )

    score = score_trend_candidate(candidate, now)

    assert score.status == TrendDecisionStatus.APPROVED_FOR_BRIEF
    assert score.score >= 0.45
    assert score.failed_gates == ()


def test_missing_rights_blocks_candidate_even_with_strong_metrics() -> None:
    now = datetime(2026, 8, 27, tzinfo=UTC)
    candidate = TrendCandidate(
        topic="copied viral clip",
        platforms=(Platform.TIKTOK, Platform.X),
        signals=(
            TrendSignal(
                platform=Platform.TIKTOK,
                topic="copied viral clip",
                source="tiktok_research_api",
                source_url="https://developers.tiktok.com/doc/research-api-get-started",
                observed_at=now,
                views=1_000_000,
                likes=120_000,
                comments=10_000,
                shares=20_000,
            ),
            TrendSignal(
                platform=Platform.X,
                topic="copied viral clip",
                source="x_api",
                source_url="https://docs.x.com/x-api/media/introduction",
                observed_at=now,
                views=600_000,
                likes=40_000,
                comments=3_000,
                shares=9_000,
            ),
        ),
        audience="general",
        creative_angle="Reuse a viral clip directly.",
        hook_pattern="You will not believe this clip.",
        originality_risk=0.7,
        policy_risk=0.1,
        rights_verified=False,
    )

    score = score_trend_candidate(candidate, now)

    assert score.status == TrendDecisionStatus.BLOCKED_RIGHTS_RISK
    assert "RIGHTS_VERIFIED" in score.failed_gates


def test_creative_brief_includes_platform_format_and_quality_gates() -> None:
    now = datetime(2026, 8, 27, tzinfo=UTC)
    candidate = TrendCandidate(
        topic="short documentary hook",
        platforms=(Platform.FACEBOOK, Platform.YOUTUBE),
        signals=(
            TrendSignal(
                platform=Platform.YOUTUBE,
                topic="short documentary hook",
                source="youtube_data_api",
                source_url="https://developers.google.com/youtube/v3/docs/videos/list",
                observed_at=now,
                views=100_000,
                likes=8_000,
                comments=900,
                shares=1_400,
            ),
            TrendSignal(
                platform=Platform.FACEBOOK,
                topic="short documentary hook",
                source="meta_insights",
                source_url="https://developers.facebook.com/documentation/video-api/guides/reels-publishing",
                observed_at=now,
                views=90_000,
                likes=7_500,
                comments=700,
                shares=1_100,
            ),
        ),
        audience="mobile video viewers",
        creative_angle="A cinematic mini-story with a visible payoff.",
        hook_pattern="The moment everything changed was not what you think.",
        originality_risk=0.05,
        policy_risk=0.05,
        rights_verified=True,
    )

    brief = build_creative_brief(candidate, now)

    assert any("1080x1920" in note for note in brief.format_notes)
    assert "rights_review" in brief.quality_gates
    assert "human_approval" in brief.quality_gates


def test_required_layers_include_lineage_and_feedback() -> None:
    layers = list_required_trend_layers()

    assert "evidence_and_lineage_ledger" in layers
    assert "post_publish_metrics_feedback" in layers
