#!/usr/bin/env python3
import json
import re
from pathlib import Path

path = Path("config/production-readiness.json")
data = json.loads(path.read_text(encoding="utf-8"))
gates = data.get("gates") or {}
blockers = data.get("blockers") or []
decision = data.get("decision")
evidence = data.get("evidence") or {}

if data.get("schema_version") != "1.1.0":
    raise SystemExit("READINESS=FAIL unsupported schema")
if not gates or any(type(v) is not bool for v in gates.values()):
    raise SystemExit("READINESS=FAIL gates must be non-empty booleans")
if decision not in {"BLOCKED", "CONDITIONAL", "PRODUCTION_READY"}:
    raise SystemExit("READINESS=FAIL invalid decision")
if decision == "PRODUCTION_READY" and (not all(gates.values()) or blockers):
    raise SystemExit("READINESS=FAIL unsafe production promotion")
if decision != "PRODUCTION_READY" and not blockers:
    raise SystemExit("READINESS=FAIL blockers required when not production ready")

video_record = Path(str(evidence.get("video_asset_record", "")))
video_hash = str(evidence.get("video_asset_sha256", ""))
if not video_record.is_file():
    raise SystemExit("READINESS=FAIL video evidence record missing")
if not re.fullmatch(r"[0-9a-f]{64}", video_hash):
    raise SystemExit("READINESS=FAIL invalid bound video sha256")
video = json.loads(video_record.read_text(encoding="utf-8"))
if (video.get("asset") or {}).get("sha256") != video_hash:
    raise SystemExit("READINESS=FAIL video evidence hash mismatch")

passed = sum(gates.values())
print(f"CINEFORGE_READINESS=PASS decision={decision} gates={passed}/{len(gates)} blockers={len(blockers)}")
