from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path

from .trend_intelligence import TrendDecisionStatus, list_required_trend_layers, load_candidates_jsonl, rank_creative_briefs


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate social video trends and produce premium creative briefs.")
    parser.add_argument("--candidates", type=Path, help="JSONL file with normalized trend candidates.")
    parser.add_argument("--list-layers", action="store_true", help="Print required social intelligence production layers.")
    parser.add_argument("--minimum-score", type=float, default=0.45)
    args = parser.parse_args()

    if args.list_layers:
        print(json.dumps({"required_layers": list(list_required_trend_layers())}, indent=2, sort_keys=True))

    if not args.candidates:
        return 0 if args.list_layers else 2

    briefs = rank_creative_briefs(load_candidates_jsonl(args.candidates))
    payload = {"briefs": [_to_jsonable(asdict(brief)) for brief in briefs]}
    print(json.dumps(payload, indent=2, sort_keys=True))

    approved = [brief for brief in briefs if brief.trend_score.status == TrendDecisionStatus.APPROVED_FOR_BRIEF and brief.trend_score.score >= args.minimum_score]
    return 0 if approved else 3


def _to_jsonable(value):
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value


if __name__ == "__main__":
    raise SystemExit(main())
