"""CineForge offline video analysis CLI. No render/upload/publish operations."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .clip_intelligence import ClipAnalysisError, analyze_local_video


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Find quantitative video clip candidates offline")
    parser.add_argument("--video", required=True, type=Path, help="Local video file under your control")
    parser.add_argument("--output", type=Path, help="Optional local JSON output (never uploads)")
    parser.add_argument("--clip-seconds", type=int, default=20)
    parser.add_argument("--max-clips", type=int, default=3)
    args = parser.parse_args(argv)
    try:
        result = analyze_local_video(args.video, clip_seconds=args.clip_seconds,
                                     max_clips=args.max_clips)
    except (ClipAnalysisError, OSError) as exc:
        print("CINEFORGE_CLIP_ANALYSIS_BLOCKED: " + str(exc), file=sys.stderr)
        return 2
    output = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
