#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from meta_facebook_mcp_publisher.free_video import (
    load_resolution_attestations,
    readiness_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate CineForge zero-cost video readiness")
    parser.add_argument("--require-real-footage-ready", action="store_true")
    parser.add_argument("--require-generated-ready", action="store_true", help="Require native Full-HD generated-video readiness.")
    parser.add_argument("--require-generated-720p-ready", action="store_true", help="Require a zero-cash local generated-video route at its certified <=720p native resolution.")
    parser.add_argument("--benchmark-attestation", action="append", default=[], metavar="PATH", help="JSON benchmark evidence. Bare booleans are intentionally not accepted.")
    parser.add_argument("--license-attested", action="append", default=[], metavar="PROVIDER_ID")
    parser.add_argument("--verified-free-quota", action="append", default=[], metavar="PROVIDER_ID")
    args = parser.parse_args()

    resolutions = load_resolution_attestations(args.benchmark_attestation)
    manifest = readiness_manifest(
        resolution_attested=resolutions,
        license_attested=args.license_attested,
        verified_free_quota=args.verified_free_quota,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))

    if args.require_real_footage_ready and not manifest["real_footage_route"]["authorized"]:
        return 2
    if args.require_generated_ready and not manifest["generated_video_native_fhd_route"]["authorized"]:
        return 3
    if args.require_generated_720p_ready and not manifest["generated_video_720p_route"]["authorized"]:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
