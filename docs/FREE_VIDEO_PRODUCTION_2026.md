# CineForge Zero-Cost Video Production Architecture — 2026

Status date: 2026-09-11

## Objective

Produce Facebook-ready vertical video while enforcing a hard external cash cost of **USD 0.00**. The system must never buy credits, upgrade a plan, or silently fall back to a paid provider.

This document distinguishes **cash-free** from **resource-free**. Local models have zero API spend but still consume GPU time, electricity, storage, bandwidth, and operator time.

## Production order

### Tier 1 — real licensed footage + deterministic local composition

Preferred production route when the requirement is "real video" rather than synthetic footage:

1. Search Pexels API or Pixabay API.
2. Select only source assets with physical dimensions of at least **1080 x 1920** and portrait orientation.
3. Download the asset over HTTPS.
4. Persist source URL, creator, license URL, retrieval time and SHA-256 in a provenance sidecar.
5. Compose locally with FFmpeg.
6. Run technical QC.
7. Run originality/context/rights review.
8. Require human release approval.
9. Publication is a separate operation.

Pexels states that photos/videos can be used for free, modified, and shared on social media; its API is free and defaults to 200 requests/hour and 20,000/month. Pixabay permits free use and adaptation under its Content License, and its API exposes video search with a default 100 requests/60 seconds per API key.

Evidence:
- https://www.pexels.com/license/
- https://www.pexels.com/api/documentation/
- https://help.pexels.com/hc/en-us/articles/47677890260761-Is-the-Pexels-API-free-to-use
- https://pixabay.com/service/license-summary/
- https://pixabay.com/api/docs/

### Tier 2 — local open models

For synthetic/AI footage, local inference is preferred over paid APIs only after hardware and license gates pass.

#### Wan2.2 — preferred local candidate

Wan2.2 is the preferred local candidate because the official repository states that the models are Apache-2.0 licensed and that the project claims no rights over generated content. It supports text/video model variants and has ComfyUI/Diffusers integration.

Production gates:
- CUDA-capable runtime available.
- Exact model/checkpoint pinned by digest.
- Local installation reproducible.
- Native-output benchmark completed.
- Full-HD vertical QC passed without pretending an upscale is native generation.
- Content safety and rights review passed.

Evidence: https://github.com/Wan-Video/Wan2.2

#### LTX-2.x — conditional, not auto-enabled

LTX-2.x is open-access but its August 2026 community license is not an unconditional commercial-use grant. The license includes revenue thresholds and other commercial restrictions. Therefore CineForge requires an explicit license attestation before this route can enter production.

Evidence: https://github.com/Lightricks/LTX-2/blob/main/LICENSE-2_x

#### HunyuanVideo 1.5 — conditional, not auto-enabled

Hunyuan uses a community license with territorial/use restrictions. It must not be auto-enabled without legal and territorial review.

Evidence: https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5/blob/main/LICENSE

#### CogVideoX / CogKit

CogKit is Apache-2.0 tooling, but the exact selected video checkpoint can carry its own license. The checkpoint license, not only the inference code license, must pass the gate.

Evidence: https://github.com/THUDM/CogKit

### Tier 3 — free/freemium cloud tools

These are convenience fallbacks, not production dependencies.

#### Krea Free

Krea advertises a $0 plan with 100 compute units/day and limited video access. The same pricing page lists a commercial license as a Basic-plan addition. Therefore the Free tier is **not auto-authorized for commercial/public production**; quota and rights must be verified per use.

Evidence: https://www.krea.ai/features/ai-video-generator

#### Runway Free

Runway documents a one-time Free-plan allocation and changing model availability. A provider whose free quota can be permanently exhausted cannot satisfy an unattended zero-cost SLO, so it is never an automatic fallback.

Evidence: https://help.runwayml.com/hc/en-us/articles/50404627334547-Free-plan-details

#### Canva Free / CapCut free editing subset

Useful for manual editing, captions and assembly when operators prefer a GUI. They are not part of the autonomous provider router because feature entitlements/assets can change and are harder to certify reproducibly than local FFmpeg.

Evidence:
- https://www.canva.com/video-editor/desktop-download/
- https://www.capcut.com/features/free-ai-video-editor

## Free local editors

- **FFmpeg** — primary deterministic automation/composition/transcoding layer.
- **Kdenlive** — GPL editor with no subscription/premium unlocks; manual editorial fallback.
- **Blender VSE** — GPL software, free for any purpose, with a capable Video Sequence Editor and compositor.

Evidence:
- https://ffmpeg.org/legal.html
- https://kdenlive.org/about/
- https://www.blender.org/about/license/
- https://www.blender.org/features/video-editing/

## Resolution policy

A 1080x1920 container is not enough to claim "real Full HD". CineForge records both:

- `source_width/source_height`
- `master_width/master_height`
- whether the source was natively at least 1080x1920
- whether any upscaling occurred

For the **real-footage route**, a source below 1080x1920 is rejected when native Full-HD vertical is required.

For an **AI local generator**, native Full-HD authorization requires a runtime benchmark. Upscaling a 720x1280 generation to 1080x1920 can be a valid delivery master, but it must be labeled `upscaled=true`; it does not satisfy the native-resolution gate.

## Fail-closed FinOps policy

Hard invariants:

- `max_external_cash_cost_usd = 0.0`
- `autonomous_purchase_allowed = false`
- paid fallback = false
- free-quota services are not auto-selected
- no credit purchase, subscription upgrade or billing action may be initiated by the agent
- local compute is tracked separately as an infrastructure cost even when API spend is zero

## Rights and provenance

Every downloaded stock clip must retain:

- provider and asset id
- page URL
- contributor name when supplied
- direct source URL
- source dimensions
- license URL
- retrieval timestamp
- SHA-256

Recognizable people, property, trademarks, logos and sensitive contexts still require contextual rights review. A stock license does not erase privacy, publicity, trademark or misleading-endorsement risks.

## Release gates

A Facebook Reel is eligible for release only when all of these pass:

1. zero-cash-cost source gate
2. source-resolution gate
3. provenance gate
4. license/rights gate
5. malware/file-safety gate
6. codec/container gate
7. 9:16 framing/safe-zone gate
8. audio/loudness gate
9. originality/context gate
10. human approval gate

Publication remains separate from generation and approval.

## Runtime readiness

Use:

```bash
PYTHONPATH=src python scripts/zero_cost_video_readiness.py
```

To require an immediately executable real-footage route:

```bash
PYTHONPATH=src python scripts/zero_cost_video_readiness.py --require-real-footage-ready
```

A real-footage route becomes executable when:

- FFmpeg is installed; and
- either `PEXELS_API_KEY` or `PIXABAY_API_KEY` is securely configured.

Both API keys are free to obtain. Do not commit them to Git.

A generated-video route additionally requires a certified local GPU/model runtime and a native-resolution benchmark.
