#!/usr/bin/env python3
import json
import re
from pathlib import Path

EVIDENCE_DIR = Path("evidence/video")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

files = sorted(EVIDENCE_DIR.glob("*.json"))
if not files:
    raise SystemExit("VIDEO_EVIDENCE=FAIL no evidence records")

for path in files:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "1.0.0":
        raise SystemExit(f"VIDEO_EVIDENCE=FAIL unsupported schema: {path}")
    if data.get("evidence_type") != "video_asset_intake":
        raise SystemExit(f"VIDEO_EVIDENCE=FAIL invalid evidence_type: {path}")
    asset = data.get("asset") or {}
    if not SHA256_RE.fullmatch(str(asset.get("sha256", ""))):
        raise SystemExit(f"VIDEO_EVIDENCE=FAIL invalid sha256: {path}")
    if int(asset.get("size_bytes") or 0) <= 0:
        raise SystemExit(f"VIDEO_EVIDENCE=FAIL invalid size: {path}")
    video = asset.get("video") or {}
    if video.get("aspect_ratio") != "9:16":
        raise SystemExit(f"VIDEO_EVIDENCE=FAIL non-vertical asset: {path}")
    review = data.get("content_review") or {}
    blockers = review.get("publication_blockers") or []
    authorization = data.get("authorization") or {}
    if blockers and authorization.get("production_publication_allowed") is True:
        raise SystemExit(f"VIDEO_EVIDENCE=FAIL unsafe publication authorization: {path}")
    if authorization.get("autonomous_publication_authorized") is True:
        raise SystemExit(f"VIDEO_EVIDENCE=FAIL autonomous public posting prohibited: {path}")

print(f"VIDEO_EVIDENCE=PASS records={len(files)}")
