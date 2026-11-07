"""Safety and quantitative tests for offline discovery; never publishes."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from meta_facebook_mcp_publisher.clip_intelligence import (
    ClipAnalysisError, MAX_DURATION_SECONDS, analyze_local_video, inspect_source,
    rank_intervals,
)
from meta_facebook_mcp_publisher.clip_cli import main


def test_activity_scoring_is_bounded_and_explainable():
    visual = [0.01] * 35
    audio = [0.002] * 35
    visual[12:20] = [0.8] * 8
    audio[12:20] = [0.8] * 8
    output = rank_intervals(visual, audio, clip_seconds=10, max_clips=3)
    assert len(output) <= 3
    assert all(0 <= c["activity_score_0_100"] <= 100 for c in output)
    assert output[0]["start_seconds"] <= 20
    assert output[0]["end_seconds"] >= 12


def test_silent_video_can_still_rank_visual_activity():
    visual = [0.002] * 21
    visual[10:] = [0.3] * 11
    clips = rank_intervals(visual, [0.0] * 21, clip_seconds=8)
    assert clips[0]["activity_score_0_100"] > 0
    assert clips[0]["start_seconds"] >= 8


def test_unrelated_videos_must_not_be_treated_as_calibrated_probabilities():
    quiet = rank_intervals([0.002] * 25, [0.0] * 25, clip_seconds=10)
    energetic = rank_intervals([0.2] * 25, [0.0] * 25, clip_seconds=10)
    assert all(0 <= x[0]["activity_score_0_100"] <= 100 for x in (quiet, energetic))
    # Both can have high relative scores; scores are not comparable across sources.
    assert energetic[0]["activity_score_0_100"] >= quiet[0]["activity_score_0_100"]


@pytest.mark.parametrize("kwargs", [
    {"clip_seconds": 5}, {"clip_seconds": 91}, {"max_clips": 0},
    {"max_clips": 11}, {"stride_seconds": 0},
])
def test_invalid_candidate_parameters_fail_closed(kwargs):
    with pytest.raises(ClipAnalysisError):
        rank_intervals([0.1] * 25, [0.2] * 25, **kwargs)


def test_alignment_failure_blocks():
    with pytest.raises(ClipAnalysisError, match="INVALID_SAMPLE_ALIGNMENT"):
        rank_intervals([0.1] * 20, [0.2] * 19)


def test_source_rejects_missing_media(tmp_path: Path):
    with pytest.raises(ClipAnalysisError, match="VIDEO_FILE_REQUIRED"):
        inspect_source(tmp_path / "missing.mp4")


def test_cli_never_exposes_success_for_missing_media(tmp_path: Path, capsys):
    assert main(["--video", str(tmp_path / "no-video.mp4")]) == 2
    assert "BLOCKED" in capsys.readouterr().err


def test_clip_candidates_bind_to_real_media_and_block_publication(tmp_path: Path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        if os.getenv("CINEFORGE_REQUIRE_AV_E2E") == "1":
            pytest.fail("Dedicated AV CI must provide FFmpeg and ffprobe")
        pytest.skip("FFmpeg unavailable in generic CI; dedicated AV CI makes this test mandatory")
    sample = tmp_path / "source.mp4"
    subprocess.run([
        "ffmpeg", "-nostdin", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc2=size=128x224:rate=10",
        "-f", "lavfi", "-i", "sine=frequency=400:sample_rate=8000",
        "-t", "7", "-c:v", "libx264", "-threads", "1", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", str(sample),
    ], check=True, timeout=30)
    result = analyze_local_video(sample, clip_seconds=6)
    assert result["source"]["sha256"]
    assert len(result["source"]["sha256"]) == 64
    assert result["source"]["has_audio"] is True
    assert 6 <= result["source"]["duration_seconds"] <= MAX_DURATION_SECONDS
    assert len(result["candidates"]) >= 1
    assert result["rights_verified"] is False
    assert result["publication_authorized"] is False
    assert result["production_ready"] is False
    assert "DOCUMENTED_ASSET_RIGHTS" in result["required_next_gates"]
    output = tmp_path / "result.json"
    assert main(["--video", str(sample), "--clip-seconds", "6", "--output", str(output)]) == 0
    assert json.loads(output.read_text())["publication_authorized"] is False
