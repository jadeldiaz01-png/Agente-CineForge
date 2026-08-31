#!/usr/bin/env python3
import json
from pathlib import Path

path = Path("config/production-readiness.json")
data = json.loads(path.read_text(encoding="utf-8"))
gates = data.get("gates") or {}
blockers = data.get("blockers") or []
decision = data.get("decision")

if data.get("schema_version") != "1.0.0":
    raise SystemExit("READINESS=FAIL unsupported schema")
if not gates or any(type(v) is not bool for v in gates.values()):
    raise SystemExit("READINESS=FAIL gates must be non-empty booleans")
if decision not in {"BLOCKED", "CONDITIONAL", "PRODUCTION_READY"}:
    raise SystemExit("READINESS=FAIL invalid decision")
if decision == "PRODUCTION_READY" and (not all(gates.values()) or blockers):
    raise SystemExit("READINESS=FAIL unsafe production promotion")
if decision != "PRODUCTION_READY" and not blockers:
    raise SystemExit("READINESS=FAIL blockers required when not production ready")

passed = sum(gates.values())
print(f"CINEFORGE_READINESS=PASS decision={decision} gates={passed}/{len(gates)}")
