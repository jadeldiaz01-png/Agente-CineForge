# CineForge Clip Intelligence — integration from Jadel Video AI PoC

**Scope:** quantitative offline interval discovery. **State:** PREPARE_ONLY.
This change is independent of CineForge's P0 fail-closed publisher PR #5,
so it can be reviewed without including that PR's unmerged changes. It does not modify social publishing connectors, their credentials, payment flows,
the website, or production configuration.

## Why this architecture

Keep CineForge as source of truth for trend research, evidence ledger,
approved sources, FFmpeg pipeline, media quality and per-platform contracts.
Absorb the previous PoC's *relative visual/audio activity ranking* as a
new planning input, instead of deploying a second independently privileged agent.

This is a deterministic feature analyzer, **not an LLM or a viral prediction model**.
It selects candidate intervals from a supplied local video; downstream editors
must produce original, reviewed work. Original footage can still fail rights or
platform originality rules. Do not use two viral tutorial videos as publishing
assets without independently verified reuse rights.

## Run

Python 3.11+, FFmpeg/ffprobe available on PATH; no Python runtime dependencies:

    python -m pip install .
    python -m meta_facebook_mcp_publisher.clip_cli \
      --video /absolute/path/owned-video.mp4 \
      --output artifacts/clip-candidates.json \
      --clip-seconds 20 --max-clips 3

The result includes SHA-256 of the exact input and candidate timestamps.
Files over 250 MiB or longer than 600 seconds are rejected in v1.
The sampled image signal is one 64×64 grayscale frame per second;
audio is mono, 2 kHz. Scores are normalized **within the video**, so
the numbers cannot be used as probability of virality or as cross-video
performance benchmarks. This step does not transcribe or classify meaning.

## Safety contract

- Analysis has no connector, network calls, upload, stock download, video
  generation, auto-render, model spend, or publication side effects.
- All outputs declare rights_verified, originality_reviewed,
  publication_authorized and production_ready as **false**.
- A clip candidate is NOT a release approval. Downstream code must keep
  using CineForge's existing content-bound HMAC release and durable ledger.
- Human review must independently verify asset rights, derivative permission,
  likeness and soundtrack rights, original value, platform policies, caption,
  exact final MP4 hash and approved destination.
- An authenticated platform test and per-platform remote confirmation must be
  evidenced before considering LIVE promotion. GitHub green checks alone
  cannot certify production.

## Validation

    python -m pytest -q tests/test_clip_intelligence.py
    python -m pytest -q

Promotion depends additionally on all open PR #5 blockers:
protected main, audited durable storage, platform OAuth/reviews,
contract tests and verified generation hardware/quality benchmark.

Official policies:
- YouTube: https://support.google.com/youtube/answer/1311392
- Meta: https://about.fb.com/news/2026/03/rewarding-original-creators-on-facebook/
