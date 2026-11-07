"""Offline SHA-bound MP4 rendering from CineForge quantitative clip candidates.

Editorial previews only. Never communicates with platform APIs or enables live release.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from .clip_intelligence import ClipAnalysisError, inspect_source


class PreviewRenderDenied(ValueError):
    """Invalid, stale or unsafe preview render request."""


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as inp:
        for part in iter(lambda: inp.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def _check_candidate(data: dict, source: dict, index: int) -> tuple[float, float, dict]:
    if data.get("schema_version") != 1 or data.get("kind") != "cineforge.offline_clip_candidates":
        raise PreviewRenderDenied("CANDIDATE_SCHEMA_MISMATCH")
    evidence = data.get("source")
    if not isinstance(evidence, dict) or evidence.get("sha256") != source["sha256"]:
        raise PreviewRenderDenied("SOURCE_SHA256_MISMATCH")
    if data.get("publication_authorized") is not False:
        raise PreviewRenderDenied("CANDIDATE_PUBLICATION_STATE_INVALID")
    options = data.get("candidates")
    if not isinstance(options, list) or not (0 <= index < len(options)):
        raise PreviewRenderDenied("CANDIDATE_INDEX_INVALID")
    candidate = options[index]
    if not isinstance(candidate, dict):
        raise PreviewRenderDenied("CANDIDATE_INVALID")
    try:
        start = float(candidate["start_seconds"])
        end = float(candidate["end_seconds"])
        score = float(candidate["activity_score_0_100"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PreviewRenderDenied("CANDIDATE_NUMERIC_FIELDS_INVALID") from exc
    if (not all(math.isfinite(v) for v in (start, end, score))
            or not 0 <= score <= 100 or start < 0
            or end > source["duration_seconds"] + 1.05
            or not 3 <= end - start <= 90.01):
        raise PreviewRenderDenied("CANDIDATE_INTERVAL_INVALID")
    actual_end = min(end, source["duration_seconds"])
    if actual_end - start < 3:
        raise PreviewRenderDenied("CANDIDATE_INTERVAL_TOO_SHORT")
    return start, actual_end, candidate


def _probe_output(path: Path, expected_duration: float) -> dict:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
            capture_output=True, check=True, text=True, timeout=30,
        )
        data = json.loads(out.stdout)
        video = next(s for s in data["streams"] if s.get("codec_type") == "video")
        audio = next(s for s in data["streams"] if s.get("codec_type") == "audio")
        duration = float(data["format"]["duration"])
        numerator, denominator = [int(x) for x in video.get("avg_frame_rate", "0/0").split("/")]
        fps = numerator / denominator
        if (video.get("codec_name") != "h264" or video.get("pix_fmt") != "yuv420p"
                or (int(video["width"]), int(video["height"])) != (1080, 1920)
                or not 29.9 <= fps <= 30.1
                or audio.get("codec_name") != "aac"
                or not math.isfinite(duration) or abs(duration - expected_duration) > 0.5):
            raise PreviewRenderDenied("OUTPUT_QC_MISMATCH")
    except PreviewRenderDenied:
        raise
    except (OSError, subprocess.SubprocessError, KeyError, TypeError, ValueError,
            StopIteration, ZeroDivisionError, json.JSONDecodeError) as exc:
        raise PreviewRenderDenied("OUTPUT_FFPROBE_FAILED") from exc
    return {"codec": "h264", "width": 1080, "height": 1920,
            "fps": round(fps, 3), "pixel_format": "yuv420p", "audio_codec": "aac",
            "duration_seconds": round(duration, 3), "bytes": path.stat().st_size}


def render_preview(source_path: str | Path, candidates_json: str | Path,
                   output_path: str | Path, *, candidate_index: int = 0) -> dict:
    """Make an actual audiovisual local preview, never a platform-ready release."""
    path, evidence_path, target = Path(source_path), Path(candidates_json), Path(output_path)
    if target.suffix.lower() != ".mp4" or target.exists() or target.is_symlink():
        raise PreviewRenderDenied("OUTPUT_PATH_MUST_BE_NEW_MP4")
    sidecar = target.with_suffix(".mp4.render.json")
    if sidecar.exists() or sidecar.is_symlink():
        raise PreviewRenderDenied("OUTPUT_EVIDENCE_ALREADY_EXISTS")
    if not target.parent.is_dir():
        raise PreviewRenderDenied("OUTPUT_PARENT_MISSING")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise PreviewRenderDenied("FFMPEG_FFPROBE_REQUIRED")
    try:
        source = inspect_source(path)
        content = json.loads(evidence_path.read_text(encoding="utf-8"))
        start, end, candidate = _check_candidate(content, source, candidate_index)
    except (ClipAnalysisError, OSError, json.JSONDecodeError) as exc:
        raise PreviewRenderDenied("SOURCE_OR_CANDIDATE_EVIDENCE_INVALID") from exc
    span = end - start
    with tempfile.NamedTemporaryFile(prefix=".cineforge-preview-", suffix=".mp4", dir=target.parent,
                                     delete=False) as temp:
        temp_path = Path(temp.name)
    try:
        cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-y",
               "-ss", f"{start:.3f}", "-i", str(path)]
        if not source["has_audio"]:
            cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        cmd += ["-t", f"{span:.3f}", "-map", "0:v:0",
                "-map", "0:a:0" if source["has_audio"] else "1:a:0",
                "-vf", "fps=30,scale=1080:1920:force_original_aspect_ratio=decrease,"
                        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p",
                "-threads", "2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
                "-pix_fmt", "yuv420p", "-r", "30", "-af", "apad", "-c:a", "aac",
                "-b:a", "128k", "-ar", "48000", "-ac", "2",
                "-movflags", "+faststart", "-f", "mp4", str(temp_path)]
        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=150)
        except (OSError, subprocess.SubprocessError) as exc:
            raise PreviewRenderDenied("RENDER_FAILED") from exc
        output_qc = _probe_output(temp_path, span)
        if temp_path.stat().st_size > 250 * 1024 * 1024:
            raise PreviewRenderDenied("OUTPUT_SIZE_LIMIT")
        record = {
            "schema_version": 1, "kind": "cineforge.offline_editorial_preview",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "input_video_sha256": source["sha256"],
            "input_source_name": source["source_name"],
            "candidate_evidence_sha256": _digest(evidence_path),
            "candidate_index": candidate_index,
            "candidate_activity_score_0_100": candidate["activity_score_0_100"],
            "selected_start_seconds": round(start, 3), "selected_end_seconds": round(end, 3),
            "output_sha256": _digest(temp_path), "output_media": output_qc,
            "audio_source": "input_track" if source["has_audio"] else "generated_silence",
            "source_native_fhd_vertical": (source["width"] >= 1080 and
                                           source["height"] >= 1920 and
                                           source["height"] > source["width"]),
            "output_upscaled_or_padded": (source["width"] < 1080 or source["height"] < 1920 or
                                         source["width"] / source["height"] != 9 / 16),
            "model_generated": False, "generation_quality_certified": False,
            "asset_rights_verified": False, "originality_reviewed": False,
            "human_release_approved": False, "publication_authorized": False,
            "production_ready": False, "external_cash_cost_usd": 0.0,
            "next_steps": ["VERIFY_INPUT_MEDIA_LICENSE", "EDITORIAL_ORIGINALITY_REVIEW",
                           "CONTENT_BOUND_HUMAN_APPROVAL", "PLATFORM_CONTRACT_VERIFICATION"],
        }
        sidecar.write_text(json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
        os.replace(temp_path, target)
        return record
    except Exception:
        sidecar.unlink(missing_ok=True)
        raise
    finally:
        temp_path.unlink(missing_ok=True)
