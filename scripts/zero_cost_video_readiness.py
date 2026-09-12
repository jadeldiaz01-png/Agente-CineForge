#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from meta_facebook_mcp_publisher.free_video import readiness_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate CineForge zero-cost video readiness")
    parser.add_argument(
        "--require-real-footage-ready",
        action="store_true",
        help="Exit non-zero unless the real-footage $0 route is currently executable.",
    )
    parser.add_argument(
        "--require-generated-ready",
        action="store_true",
        help="Exit non-zero unless a local/generated $0 route is currently executable.",
    )
    args = parser.parse_args()

    manifest = readiness_manifest()
    print(json.dumps(manifest, indent=2, sort_keys=True))

    if args.require_real_footage_ready and not manifest["real_footage_route"]["authorized"]:
        return 2
    if args.require_generated_ready and not manifest["generated_video_route"]["authorized"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
