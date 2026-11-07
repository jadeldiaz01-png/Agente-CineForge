"""Real FFmpeg audiovisual E2E plus adversarial release-denial tests."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from meta_facebook_mcp_publisher.clip_intelligence import analyze_local_video
from meta_facebook_mcp_publisher.clip_render import (
    PreviewRenderDenied, _check_candidate, render_preview,
)
from meta_facebook_mcp_publisher.clip_render_cli import main as render_cli


@pytest.fixture
def codecs_available():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        if os.environ.get("CINEFORGE_REQUIRE_AV_E2E") == "1":
            pytest.fail("Dedicated audiovisual CI must install ffmpeg + ffprobe")
        pytest.skip("FFmpeg unavailable in generic CI")


def make_source(tmp_path: Path, *, sound: bool) -> Path:
    path = tmp_path / ("with-sound.mp4" if sound else "silent.mp4")
    cmd = [
        "ffmpeg", "-nostdin", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc2=size=128x224:rate=10",
    ]
    if sound:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=400:sample_rate=8000"]
    cmd += ["-t", "7", "-c:v", "libx264", "-threads", "1", "-pix_fmt", "yuv420p"]
    if sound:
        cmd += ["-c:a", "aac", "-shortest"]
    else:
        cmd += ["-an"]
    cmd.append(str(path))
    subprocess.run(cmd, check=True, timeout=30)
    return path


@pytest.mark.parametrize("sound", [True, False])
def test_synthetic_audiovisual_pipeline_is_real_but_not_approved(tmp_path, codecs_available, sound):
    source = make_source(tmp_path, sound=sound)
    analysis = analyze_local_video(source, clip_seconds=6, max_clips=1)
    evidence_path = tmp_path / "candidate.json"
    evidence_path.write_text(json.dumps(analysis), encoding="utf-8")
    output = tmp_path / "preview.mp4"
    assert render_cli(["--video", str(source), "--analysis", str(evidence_path),
                       "--output", str(output)]) == 0
    record_path = output.with_suffix(".mp4.render.json")
    assert output.is_file() and output.stat().st_size > 1000
    assert record_path.is_file()
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["output_media"]["codec"] == "h264"
    assert record["output_media"]["audio_codec"] == "aac"
    assert record["output_media"]["width"] == 1080
    assert record["output_media"]["height"] == 1920
    assert record["output_media"]["fps"] == pytest.approx(30)
    assert record["audio_source"] == ("input_track" if sound else "generated_silence")
    assert record["output_upscaled_or_padded"] is True
    assert record["model_generated"] is False
    assert record["asset_rights_verified"] is False
    assert record["publication_authorized"] is False
    assert record["human_release_approved"] is False
    assert record["production_ready"] is False
    assert record["generation_quality_certified"] is False
    assert record["input_video_sha256"] == analysis["source"]["sha256"]


def test_changed_input_sha_blocks_and_never_creates_output(tmp_path, codecs_available):
    source = make_source(tmp_path, sound=False)
    analysis = analyze_local_video(source, clip_seconds=6, max_clips=1)
    analysis["source"]["sha256"] = "0" * 64
    evidence = tmp_path / "analysis.json"
    evidence.write_text(json.dumps(analysis), encoding="utf-8")
    output = tmp_path / "preview.mp4"
    with pytest.raises(PreviewRenderDenied, match="SOURCE_SHA256_MISMATCH"):
        render_preview(source, evidence, output)
    assert not output.exists()


def test_explicit_publish_true_is_rejected():
    data = {"schema_version": 1, "kind": "cineforge.offline_clip_candidates",
            "publication_authorized": True, "source": {"sha256": "a" * 64},
            "candidates": [{"start_seconds": 0, "end_seconds": 6,
                            "activity_score_0_100": 50}]}
    with pytest.raises(PreviewRenderDenied, match="CANDIDATE_PUBLICATION_STATE_INVALID"):
        _check_candidate(data, {"sha256": "a" * 64, "duration_seconds": 8}, 0)


@pytest.mark.parametrize("score,start,end", [
    (101, 0, 6), (-1, 0, 6), (10, -1, 6), (10, 0, 1000),
    ("nan", 0, 6), (10, 3, 4),
])
def test_malformed_intervals_never_render(score, start, end):
    data = {"schema_version": 1, "kind": "cineforge.offline_clip_candidates",
            "publication_authorized": False, "source": {"sha256": "a" * 64},
            "candidates": [{"start_seconds": start, "end_seconds": end,
                            "activity_score_0_100": score}]}
    with pytest.raises(PreviewRenderDenied):
        _check_candidate(data, {"sha256": "a" * 64, "duration_seconds": 8}, 0)


def test_existing_output_is_never_overwritten(tmp_path):
    output = tmp_path / "preview.mp4"
    output.write_bytes(b"PREVIOUS_ASSET")
    with pytest.raises(PreviewRenderDenied, match="OUTPUT_PATH_MUST_BE_NEW_MP4"):
        render_preview(tmp_path / "no.mp4", tmp_path / "no.json", output)
    assert output.read_bytes() == b"PREVIOUS_ASSET"
