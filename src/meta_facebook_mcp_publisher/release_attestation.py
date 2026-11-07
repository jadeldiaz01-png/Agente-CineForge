"""Inspect real media and verify a separately signed, content-bound release decision."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import hmac
import json
import subprocess

class ReleaseDenied(ValueError):
    pass

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for block in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def inspect_mp4(path: Path) -> dict:
    if not path.is_file() or path.suffix.lower() != ".mp4":
        raise ReleaseDenied("VIDEO_FILE_REQUIRED")
    size = path.stat().st_size
    if size <= 0 or size > 250 * 1024 * 1024:
        raise ReleaseDenied("VIDEO_SIZE_OUT_OF_RANGE")
    try:
        output = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                                check=True, capture_output=True, text=True, timeout=25)
        probe = json.loads(output.stdout)
        stream = next(s for s in probe["streams"] if s.get("codec_type") == "video")
        width, height, codec = int(stream["width"]), int(stream["height"]), stream["codec_name"]
        seconds = float(probe["format"]["duration"])
        if width < 720 or height < 1280 or abs(width / height - 9 / 16) > .02:
            raise ReleaseDenied("VIDEO_VERTICAL_9_16_REQUIRED")
        if codec != "h264" or not 1 <= seconds <= 90:
            raise ReleaseDenied("VIDEO_CODEC_OR_DURATION_INVALID")
        return {"sha256": sha256_file(path), "width": width, "height": height,
                "codec": codec, "duration": seconds, "bytes": size}
    except ReleaseDenied:
        raise
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired,
            KeyError, ValueError, StopIteration, json.JSONDecodeError) as exc:
        raise ReleaseDenied("FFPROBE_QC_FAILED") from exc

def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

def verify_release(path: Path, media: dict, caption: str, platforms: list[str], key: str) -> dict:
    if len(key) < 32:
        raise ReleaseDenied("APPROVAL_SIGNING_KEY_MISSING")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        payload, signature = data["payload"], data["signature"]
        expected = hmac.new(key.encode(), canonical(payload), hashlib.sha256).hexdigest()
        if not isinstance(signature, str) or not hmac.compare_digest(signature, expected):
            raise ReleaseDenied("APPROVAL_SIGNATURE_INVALID")
        expire = datetime.fromisoformat(payload["expires_at"].replace("Z", "+00:00"))
        if not expire.tzinfo or expire <= datetime.now(timezone.utc):
            raise ReleaseDenied("APPROVAL_EXPIRED")
        if (payload.get("version") != 1 or payload.get("video_sha256") != media["sha256"]
                or payload.get("caption") != caption or payload.get("platforms") != sorted(set(platforms))):
            raise ReleaseDenied("APPROVAL_BINDING_MISMATCH")
        if not (payload.get("human_approved") is True
                and payload.get("video_qc_passed") is True
                and payload.get("originality_reviewed") is True
                and isinstance(payload.get("approved_by"), str)
                and payload["approved_by"].strip()):
            raise ReleaseDenied("APPROVAL_GATES_MISSING")
        return payload
    except ReleaseDenied:
        raise
    except (OSError, KeyError, ValueError, AttributeError, TypeError) as exc:
        raise ReleaseDenied("APPROVAL_FILE_INVALID") from exc
