# CineForge — Zero-cost video production research and operating standard (2026)

## Scope

This subsystem defines **zero external cash cost**, not “zero resource consumption.” Local generation may consume GPU time, electricity, storage, and operator time. The invariant is that CineForge cannot autonomously create a charge, buy credits, or switch to a paid service.

## Production architecture

The preferred real-video path is: trend brief → keyless Wikimedia Commons search or free Pexels/Pixabay API → per-asset rights/provenance gate → native-source-resolution gate → local FFmpeg edit/transcode → ffprobe QC → originality/context review → human release approval → separate publication action.

Wikimedia Commons is keyless, but licensing is per asset. The implementation auto-allows a narrow set (CC0/Public Domain/CC BY) and rejects “license review needed.” CC BY-SA is supported only with explicit opt-in because derivatives/distribution can carry ShareAlike obligations. The MediaWiki Action API exposes `imageinfo`, including URL, size, MIME and extended metadata, so license and source dimensions are captured before download.

Pexels and Pixabay remain useful redundant sources. Their free APIs require credentials and have rate limits, so API responses should be cached and normalized into the same provenance schema. A source must be at least 1080×1920 portrait to be labeled **native Full-HD vertical**; transcoding or upscaling never changes that source fact.

## Local generative route

Wan2.2 is the preferred current open local candidate because the official repository is Apache-2.0 and integrates with ComfyUI/Diffusers. Its official open T2V/I2V models support 480P/720P and TI2V-5B supports 720P at 24fps. Therefore CineForge authorizes it only as a native-720p source; any 1080p delivery is recorded as an upscale. High-end A14B inference can require very large VRAM, so actual runtime authorization requires hardware evidence, checkpoint digest pinning and QC.

ComfyUI is cataloged as the local workflow orchestrator. It is not itself a model license grant: each checkpoint remains separately gated. Conditional-license models such as LTX-2.x and Hunyuan remain disabled for autonomous commercial routing until explicit legal/territorial attestation.

## Local audio and editorial stack

OpenAI Whisper is an MIT-licensed local ASR option for transcription/caption QC. Kokoro-82M is an Apache-2.0 local TTS option. FFmpeg is the canonical automated compositor; its exact build configuration must be recorded because optional GPL components can change distribution obligations. Kdenlive, Blender and OpenShot are manual zero-cash editorial fallbacks.

## Security and supply chain

Provider downloads are HTTPS-only and must match provider-specific host allowlists. Redirects are revalidated. Downloads are size-capped, SHA-256 hashed, and accompanied by provenance sidecars. Catalog and manifest are packaged with the wheel and validated in CI outside the repository checkout. CI scans for obvious provider-secret patterns and uploads only JSON evidence, not third-party fixture media.

Benchmark evidence is JSON, not a toggle. Native-resolution attestations require provider ID, dimensions, a real SHA-256, `passed=true`, and `upscaled=false`. This prevents an operator from certifying native Full HD by setting a boolean.

## SRE / FinOps gates

Proposed service objectives for the real-footage production route: at least two independent source strategies in the catalog; hard external-cash debit tolerance of **$0.00**; ≥98% technical master-QC pass rate after a candidate is selected; no public post without human release approval; and deterministic fail-closed behavior when source, rights, runtime, or resolution evidence is missing.

## Current authorization boundaries

Architecture and CI for the real-footage zero-cost route may be authorized independently of public publication. Local AI generation is not live-authorized until a connected GPU runtime is benchmarked. Native-1080 AI generation is specifically **not** authorized via Wan2.2 because its official open checkpoints are at most 720P. Publication remains human-approved even when generation and QC pass.

## Primary evidence registry

- Wikimedia Commons reuse guidance and MediaWiki `imageinfo` API documentation.
- Pexels license and API documentation.
- Pixabay Content License and API documentation.
- Wan2.2 official GitHub repository and Apache-2.0 license.
- ComfyUI official repository/API documentation.
- OpenAI Whisper official repository/license.
- Kokoro-82M Apache-2.0 model card.
- FFmpeg legal/licensing documentation.
- Kdenlive, Blender and OpenShot official project/license pages.
