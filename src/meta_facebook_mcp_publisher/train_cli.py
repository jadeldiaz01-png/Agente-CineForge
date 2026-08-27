from __future__ import annotations

import argparse
import json
from pathlib import Path

from .data_governance import DataSource
from .dataset_registry import DatasetRegistry
from .training_pipeline import build_training_plan, training_layers


def run() -> int:
    parser = argparse.ArgumentParser(description="Register governed training data and build an offline training plan.")
    parser.add_argument("--registry", default="artifacts/dataset_registry.jsonl")
    parser.add_argument("--source-name")
    parser.add_argument("--source-url")
    parser.add_argument("--source-license")
    parser.add_argument("--intended-use", default="social video agent training and evaluation")
    parser.add_argument("--terms-reviewed", action="store_true")
    parser.add_argument("--robots-reviewed", action="store_true")
    parser.add_argument("--contains-personal-data", action="store_true")
    parser.add_argument("--print-layers", action="store_true")
    args = parser.parse_args()

    registry = DatasetRegistry(Path(args.registry))
    if args.source_name and args.source_url and args.source_license:
        registry.register(
            DataSource(
                name=args.source_name,
                url=args.source_url,
                license=args.source_license,
                intended_use=args.intended_use,
                terms_reviewed=args.terms_reviewed,
                robots_reviewed=args.robots_reviewed,
                contains_personal_data=args.contains_personal_data,
            )
        )

    records = registry.load_all()
    plan = build_training_plan(records)
    print(json.dumps(plan.__dict__, indent=2, sort_keys=True))
    if args.print_layers:
        print(json.dumps(training_layers(), indent=2, sort_keys=True))
    return 0 if plan.allowed else 2


if __name__ == "__main__":
    raise SystemExit(run())

