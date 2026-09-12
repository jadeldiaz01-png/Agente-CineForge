#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from meta_facebook_mcp_publisher.free_stock import (
    download_with_provenance,
    lookup_wikimedia_commons_file,
)

FIXTURE_TITLE = "File:Entrada S.A. Ushno Osqollo, Cusco.ogg"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise SystemExit("FFmpeg/ffprobe required")

    artifacts = Path("artifacts")
    artifacts.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cineforge-e2e-") as td:
        td = Path(td)
        raw = td / "source.ogg"
        master = td / "master.mp4"

        candidate = lookup_wikimedia_commons_file(FIXTURE_TITLE, allow_share_alike=True)
        if not candidate.is_native_full_hd_vertical:
            raise SystemExit("fixture is no longer native Full-HD vertical")
        if candidate.license_name != "CC BY-SA 4.0":
            raise SystemExit(f"unexpected fixture license: {candidate.license_name}")

        provenance = download_with_provenance(candidate, raw, max_bytes=32 * 1024 * 1024)
        subprocess.run(
            [
                ffmpeg, "-y", "-v", "error", "-t", "3", "-i", str(raw),
                "-vf", "scale=1080:1920:flags=lanczos,fps=30",
                "-an", "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(master),
            ],
            check=True,
        )
        probe = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=codec_name,width,height,r_frame_rate,pix_fmt:format=duration", "-of", "json", str(master)],
            check=True, capture_output=True, text=True,
        )
        probe_json = json.loads(probe.stdout)
        stream = probe_json["streams"][0]
        assert stream["width"] == 1080 and stream["height"] == 1920
        assert stream["r_frame_rate"] == "30/1"
        assert stream["codec_name"] == "h264"
        assert float(probe_json["format"]["duration"]) > 0

        evidence = {
            "schema_version": 1,
            "purpose": "technical-ci-only",
            "production_asset": False,
            "external_cash_cost_usd": 0.0,
            "source": {
                "provider": candidate.provider,
                "asset_id": candidate.asset_id,
                "page_url": candidate.page_url,
                "contributor": candidate.contributor,
                "license_name": candidate.license_name,
                "license_url": candidate.license_url,
                "native_width": candidate.width,
                "native_height": candidate.height,
                "share_alike": candidate.share_alike,
                "input_sha256": provenance["sha256"],
            },
            "output": {
                "sha256": sha256(master),
                "probe": probe_json,
                "upscaled": False,
            },
            "publication_authorized": False,
        }
        (artifacts / "e2e-real-video-evidence.json").write_text(
            json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8"
        )
        print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
