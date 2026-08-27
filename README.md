# Agente CineForge

Production scaffold for a premium social video publishing agent.

This repository contains a fail-closed multi-platform publisher for approved MP4
videos. It supports Facebook/Meta, YouTube, TikTok and X through platform-specific
connectors and a shared governance layer.

## Current Certification Status

Status: `NOT_PRODUCTION_READY`

The code is ready for dry-run validation, but live publishing remains disabled
until credentials, platform reviews, account permissions and live contract tests
are verified per platform.

## Supported Platforms

| Platform | Connector | Production Behavior |
| --- | --- | --- |
| Facebook/Meta | Page Video API | Publishes only with Page token, QC and human approval |
| YouTube | YouTube Data API upload | Publishes only with OAuth upload credentials |
| TikTok | Content Posting API | Public posting requires TikTok audit/review |
| X | X API media + post endpoints | Publishes only with user token and media/post permissions |

## Publishing Gates

The publisher fails closed unless all required gates pass:

| Gate | Required Evidence |
| --- | --- |
| `ACCESS_TOKEN_PRESENT` | Platform access token configured |
| `ACCOUNT_ID_PRESENT` | Target Page/channel/account configured |
| `VIDEO_QC_PASSED` | MP4 validated by the video QC pipeline |
| `ORIGINALITY_REVIEWED` | Copyright/originality review completed |
| `HUMAN_APPROVED` | User approved video, caption, thumbnail and platform |
| `RATE_LIMIT_ALLOWED` | Local quota allows the post |
| `IDEMPOTENCY_KEY_PRESENT` | Unique key attached to publish attempt |
| `PUBLIC_POSTING_AUDITED` | Platform review/audit allows public posting |

## Local Dry Run

```bash
python -m pip install .
python -m meta_facebook_mcp_publisher.cli \
  --video artifacts/approved-video.mp4 \
  --caption "Approved caption" \
  --platforms facebook,youtube,tiktok,x \
  --idempotency-key local-dry-run-1 \
  --dry-run \
  --human-approved \
  --video-qc-passed \
  --originality-reviewed
```

## GitHub Actions

The workflow lives at:

```text
.github/workflows/social-video-publisher.yml
```

Run it manually from GitHub Actions with `dry_run=true` first. GitHub Actions
`workflow_dispatch` only appears when the workflow file is on the default
branch.

## Credentials

Do not commit real credentials. Add them through GitHub Actions Secrets or
environment secrets.

Required secrets:

```text
META_PAGE_ID
META_PAGE_ACCESS_TOKEN
YOUTUBE_CHANNEL_ID
YOUTUBE_OAUTH_ACCESS_TOKEN
TIKTOK_ACCOUNT_ID
TIKTOK_ACCESS_TOKEN
X_ACCOUNT_ID
X_USER_ACCESS_TOKEN
```

Required production variables start as `false`:

```text
META_PUBLISHING_ENABLED
YOUTUBE_PUBLISHING_ENABLED
TIKTOK_PUBLISHING_ENABLED
TIKTOK_PUBLIC_POSTING_AUDITED
X_PUBLISHING_ENABLED
```

## References

- https://developers.facebook.com/documentation/video-api/guides/publishing
- https://developers.google.com/youtube/v3/guides/uploading_a_video
- https://developers.tiktok.com/doc/content-posting-api-reference-direct-post
- https://docs.x.com/x-api/media/introduction

## ML/DL/LLM Governance

The repository includes an offline training-governance layer for future
machine-learning improvements. It registers approved sources, records license
and lineage evidence, builds a training plan, and blocks production training
when a source lacks review.

Run locally:

```bash
python -m meta_facebook_mcp_publisher.train_cli --print-layers
```

GitHub Actions workflow:

```text
.github/workflows/ml-training-governance.yml
```

Training mode is intentionally fail-closed. Internet data must have source URL,
license, terms review, collection/robots review, and personal-data review before
it can be used for training or fine-tuning.

## AI Provider Gateway

The agent now includes an AI provider gateway for production inference and
fallback routing.

| Provider | Default Model | Role |
| --- | --- | --- |
| NVIDIA NIM | `nvidia/nemotron-3-ultra-550b-a55b` | Primary heavy reasoning/planning provider |
| Groq | `llama-3.3-70b-versatile` | Fast free-tier/OpenAI-compatible fallback |
| Hugging Face | `meta-llama/Llama-3.1-8B-Instruct` | Open-model serverless fallback |
| Gemini | `gemini-2.5-flash` | Low-cost/free-tier long-context fallback |

Run locally:

```bash
python -m meta_facebook_mcp_publisher.ai_cli \
  --prompt "Create a production-safe video plan" \
  --dry-run
```

GitHub Actions workflow:

```text
.github/workflows/ai-provider-gateway.yml
```

Required AI secrets:

```text
NVIDIA_NIM_API_KEY
GROQ_API_KEY
HF_TOKEN
GEMINI_API_KEY
```

Required AI variables start disabled:

```text
NVIDIA_NIM_ENABLED=false
GROQ_ENABLED=false
HF_INFERENCE_ENABLED=false
GEMINI_ENABLED=false
```
