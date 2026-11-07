"""Offline CineForge editing preview command; never posts to social media."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .clip_render import PreviewRenderDenied, render_preview


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a SHA-bound CineForge editorial MP4 preview")
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--analysis", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--candidate-index", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        result = render_preview(args.video, args.analysis, args.output,
                                candidate_index=args.candidate_index)
    except (PreviewRenderDenied, OSError, ValueError) as exc:
        print("CINEFORGE_PREVIEW_BLOCKED=" + str(exc), file=sys.stderr)
        return 2
    print("CINEFORGE_PREVIEW_CREATED_SHA256=" + result["output_sha256"])
    print("CINEFORGE_PUBLICATION_AUTHORIZED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
