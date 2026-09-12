# ADR-004 — Zero-external-cash video production

**Status:** Accepted, 2026-09-12

## Decision

CineForge enforces `max_external_cash_cost_usd = 0.0`, `autonomous_purchase_allowed = false`, and `paid_fallback_allowed = false`. Automated production uses a deterministic router, not an LLM decision, to choose only providers whose current policy and runtime evidence satisfy the zero-cost contract.

The preferred real-footage route is Wikimedia Commons (keyless, per-asset license gate), then Pexels/Pixabay when free API credentials are available. FFmpeg is the canonical automated compositor. Local generative models are a separate route because “no API bill” still consumes hardware/electricity and model licenses differ.

## Resolution truth

Native resolution and delivery resolution are distinct facts. A 720p model output scaled to 1080p is recorded as an upscale and never certified as native Full HD. Wan2.2 is therefore eligible only for the native-720p local-generation route unless a future official checkpoint genuinely supports native Full HD.

## Rights and publication

Each external asset requires provenance and license evidence. ShareAlike assets are excluded from default automatic selection and require explicit job opt-in. Public release is always a separate human-approved action.

## Failure behavior

If no eligible zero-cost source, FFmpeg runtime, rights evidence, or required hardware is available, the workflow fails closed. It cannot buy credits, enable a paid provider, or silently lower rights/resolution requirements.
