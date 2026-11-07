"""Offline quantitative clip discovery for CineForge.

This module proposes editing intervals. It DOES NOT establish media rights, originality,
platform eligibility, predicted reach or publishing authorization. Nothing is uploaded.
Only Python stdlib, ffprobe and ffmpeg are required.
"""
from __future__ import annotations

from array import array
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys


MAX_VIDEO_BYTES = 250 * 1024 * 1024
MAX_DURATION_SECONDS = 600
FRAME_EDGE = 64
AUDIO_SAMPLE_RATE = 2000


class ClipAnalysisError(ValueError):
    """Invalid, missing or unsafe-to-analyze local media."""


def _execute(args: list[str], timeout: int = 90) -> bytes:
    try:
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=timeout, check=True)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ClipAnalysisError("MEDIA_PROBE_OR_DECODE_FAILED") from exc
    return result.stdout


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_source(path: Path) -> dict:
    """Bound resource consumption before decoding untrusted media."""
    if not path.is_file() or path.suffix.lower() not in {".mp4", ".mov", ".webm"}:
        raise ClipAnalysisError("VIDEO_FILE_REQUIRED")
    size = path.stat().st_size
    if not 0 < size <= MAX_VIDEO_BYTES:
        raise ClipAnalysisError("VIDEO_SIZE_OUT_OF_RANGE")
    if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
        raise ClipAnalysisError("FFMPEG_AND_FFPROBE_REQUIRED")
    raw = _execute(["ffprobe", "-v", "error", "-show_streams", "-show_format",
                    "-of", "json", str(path)], timeout=25)
    try:
        data = json.loads(raw)
        video = next(s for s in data["streams"] if s.get("codec_type") == "video")
        seconds = float(data["format"]["duration"])
        width, height = int(video["width"]), int(video["height"])
        has_audio = any(s.get("codec_type") == "audio" for s in data["streams"])
        if not math.isfinite(seconds) or not 6 <= seconds <= MAX_DURATION_SECONDS:
            raise ClipAnalysisError("VIDEO_DURATION_OUT_OF_RANGE")
        if not 1 <= width <= 8192 or not 1 <= height <= 8192:
            raise ClipAnalysisError("VIDEO_DIMENSIONS_OUT_OF_RANGE")
    except (KeyError, ValueError, TypeError, StopIteration) as exc:
        if isinstance(exc, ClipAnalysisError):
            raise
        raise ClipAnalysisError("VIDEO_METADATA_INVALID") from exc
    return {"sha256": _sha256(path), "bytes": size, "duration_seconds": round(seconds, 3),
            "width": width, "height": height, "has_audio": has_audio,
            "source_name": path.name}


def _visual_deltas(path: Path, sample_count: int, seconds: float) -> list[float]:
    # Small, fixed-size gray frames prevent a large raw-video memory footprint.
    raw = _execute(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path),
                    "-t", str(seconds), "-vf", f"fps=1,scale={FRAME_EDGE}:{FRAME_EDGE},format=gray",
                    "-frames:v", str(sample_count), "-an", "-f", "rawvideo",
                    "-pix_fmt", "gray", "pipe:1"])
    frame_size = FRAME_EDGE * FRAME_EDGE
    if len(raw) % frame_size or not raw:
        raise ClipAnalysisError("VIDEO_FRAME_DECODE_INVALID")
    frames = [raw[i:i + frame_size] for i in range(0, len(raw), frame_size)]
    if len(frames) > sample_count:
        raise ClipAnalysisError("VIDEO_SAMPLE_COUNT_EXCEEDED")
    result = [0.0]
    for previous, current in zip(frames, frames[1:]):
        difference = sum(abs(a - b) for a, b in zip(previous, current))
        result.append(difference / (frame_size * 255))
    return result


def _audio_levels(path: Path, sample_count: int, seconds: float) -> list[float]:
    raw = _execute(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path),
                    "-t", str(seconds), "-map", "0:a:0", "-vn", "-ac", "1",
                    "-ar", str(AUDIO_SAMPLE_RATE), "-f", "s16le", "pipe:1"])
    if len(raw) % 2:
        raise ClipAnalysisError("AUDIO_SAMPLE_DECODE_INVALID")
    pcm = array("h")
    pcm.frombytes(raw)
    if sys.byteorder != "little":
        pcm.byteswap()
    levels = []
    for i in range(sample_count):
        start = i * AUDIO_SAMPLE_RATE
        samples = pcm[start:start + AUDIO_SAMPLE_RATE]
        rms = math.sqrt(sum(x * x for x in samples) / len(samples)) / 32768 if samples else 0
        levels.append(rms)
    return levels


def _p90(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(len(ordered) * 0.9) - 1)] if ordered else 0.0


def rank_intervals(visual: list[float], audio: list[float], *, clip_seconds: int = 20,
                   max_clips: int = 3, stride_seconds: int = 2) -> list[dict]:
    """Within-video *activity* ranking; scores do not predict engagement or income."""
    if not 6 <= clip_seconds <= 90 or not 1 <= max_clips <= 10 or not 1 <= stride_seconds <= 30:
        raise ClipAnalysisError("INVALID_RANKING_PARAMETERS")
    if not visual or len(audio) != len(visual):
        raise ClipAnalysisError("INVALID_SAMPLE_ALIGNMENT")
    window = min(clip_seconds, len(visual))
    if window < 6:
        raise ClipAnalysisError("INSUFFICIENT_VIDEO_SAMPLES")
    motion_ref = max(_p90(visual), 0.01)
    audio_present = max(audio, default=0.0) > 0.000001
    audio_ref = max(_p90(audio), 0.01)
    scores = []
    # Include the final possible interval, even when it is not a stride multiple.
    starts = sorted(set(range(0, len(visual) - window + 1, stride_seconds))
                    | {len(visual) - window})
    for start in starts:
        motion = sum(min(1.0, x / motion_ref) for x in visual[start:start + window]) / window
        sound = sum(min(1.0, x / audio_ref) for x in audio[start:start + window]) / window
        score = motion if not audio_present else 0.58 * motion + 0.42 * sound
        scores.append({"start_seconds": start, "end_seconds": start + window,
                       "activity_score_0_100": round(100 * score, 2),
                       "mean_visual_delta": round(sum(visual[start:start + window]) / window, 6),
                       "mean_audio_rms": round(sum(audio[start:start + window]) / window, 6)})
    chosen = []
    for candidate in sorted(scores, key=lambda x: (-x["activity_score_0_100"], x["start_seconds"])):
        if all(max(0, min(candidate["end_seconds"], prior["end_seconds"]) -
                      max(candidate["start_seconds"], prior["start_seconds"]))
               <= window * 0.35 for prior in chosen):
            chosen.append(candidate)
        if len(chosen) == max_clips:
            break
    return chosen


def analyze_local_video(video_path: str | Path, *, clip_seconds: int = 20,
                        max_clips: int = 3) -> dict:
    path = Path(video_path)
    source = inspect_source(path)
    count = math.ceil(source["duration_seconds"])
    visual = _visual_deltas(path, count, source["duration_seconds"])
    if len(visual) < 6:
        raise ClipAnalysisError("INSUFFICIENT_VIDEO_FRAMES")
    audio = (_audio_levels(path, len(visual), source["duration_seconds"])
             if source["has_audio"] else [0.0] * len(visual))
    intervals = rank_intervals(visual, audio, clip_seconds=clip_seconds, max_clips=max_clips)
    return {
        "schema_version": 1,
        "kind": "cineforge.offline_clip_candidates",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "measurements": {"visual_samples": len(visual), "sample_interval_seconds": 1,
                         "p90_visual_delta": round(_p90(visual), 6),
                         "p90_audio_rms": round(_p90(audio), 6)},
        "candidates": intervals,
        "interpretation": "relative audiovisual activity only; not predicted virality or revenue",
        "rights_verified": False,
        "originality_reviewed": False,
        "publication_authorized": False,
        "production_ready": False,
        "required_next_gates": ["DOCUMENTED_ASSET_RIGHTS", "EDITORIAL_AND_ORIGINALITY_REVIEW",
                                "CONTENT_BOUND_HUMAN_RELEASE", "PLATFORM_CONTRACT_GATES"],
    }
