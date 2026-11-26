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

## Social Trend Intelligence

CineForge now includes a production-gated trend intelligence layer that ranks
video opportunities before the agent writes or renders a premium video.

Required information layers:

- Platform API connector.
- Trend signal ingestion.
- Metric normalization.
- Velocity and freshness scoring.
- Cross-platform fit scoring.
- Audience and category mapping.
- Rights and originality review.
- Policy and safety review.
- Premium video quality specification.
- Creative brief generation.
- Human approval gate.
- Evidence and lineage ledger.
- Post-publish metrics feedback.

The module is implemented in:

```text
src/meta_facebook_mcp_publisher/trend_intelligence.py
src/meta_facebook_mcp_publisher/trend_cli.py
tests/test_trend_intelligence.py
docs/social_trend_intelligence.md
.github/workflows/social-trend-intelligence.yml
```

The agent blocks a trend even when metrics are strong if rights are not verified,
policy risk is too high, or there is not enough evidence. Missing platform trend
connectors become a degraded trend signal state rather than a global production
failure.

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

## YouTube MCP server

Install the project and run the local stdio MCP server:

```bash
python -m pip install .
python -m meta_facebook_mcp_publisher.youtube_mcp_server
```

The server can load the OAuth variables from a local file outside the
repository. Configure the MCP host to pass the file path and keep publishing
disabled during verification:

```json
{
  "command": "python",
  "args": ["-m", "meta_facebook_mcp_publisher.youtube_mcp_server"],
  "env": {
    "YOUTUBE_ENV_FILE": "C:/Users/<your-user>/.jadeltechrd/secrets/youtube.env",
    "YOUTUBE_PUBLISHING_ENABLED": "false"
  }
}
```

The file must define `YOUTUBE_CHANNEL_ID`, `YOUTUBE_OAUTH_CLIENT_ID`,
`YOUTUBE_OAUTH_CLIENT_SECRET`, and `YOUTUBE_OAUTH_REFRESH_TOKEN`. Existing
process environment variables take precedence. Keep the file outside Git and
restrict access to your Windows user account.

It exposes `youtube_channel_info` and `upload_youtube_video`. The upload tool
only accepts MP4 files under `YOUTUBE_ALLOWED_VIDEO_DIR` (default
`artifacts/`), uses resumable uploads, checks that OAuth identifies the
configured channel, and records attempts in a local SQLite ledger to reject
duplicate idempotency keys and enforce the local 24-hour limit. Unknown upload
outcomes stay reserved; reconcile them before attempting another upload.

Configure the YouTube OAuth refresh token, OAuth client ID and client secret
outside the repository. The consent must include the YouTube upload and
read-only channel scopes. Keep `YOUTUBE_PUBLISHING_ENABLED=false` until the
credentials and account are verified. The upload tool also requires explicit
approval, successful QC and originality review. Public uploads additionally
require `YOUTUBE_PUBLIC_POSTING_AUDITED=true`; visibility defaults to private.
This stdio server is for local MCP hosts. It does not expose a remote endpoint.

## Remote read-only YouTube MCP endpoint

A separate Streamable HTTP entry point is available for a private, read-only
channel check. It registers only `youtube_channel_info`; it never exposes
`upload_youtube_video`. It binds to `127.0.0.1` and defaults to port `8766`.

Enable it explicitly in the service environment:

```text
YOUTUBE_MCP_HTTP_ENABLED=true
YOUTUBE_MCP_HTTP_PORT=8766
YOUTUBE_MCP_HTTP_ALLOWED_HOSTS=127.0.0.1:8766,localhost:8766,[::1]:8766
YOUTUBE_MCP_HTTP_ALLOWED_ORIGINS=http://127.0.0.1:8766,http://localhost:8766,http://[::1]:8766
```

Run `cineforge-youtube-mcp-http` (or
`python -m meta_facebook_mcp_publisher.youtube_mcp_http_server`). The MCP
endpoint is `http://127.0.0.1:8766/mcp`. Keep the process bound to loopback;
a Cloudflare Tunnel route on the same host should target
`http://127.0.0.1:8766`.

Before using a public hostname, add that exact hostname to
`YOUTUBE_MCP_HTTP_ALLOWED_HOSTS` (including the port form if the proxy sends
one) and its HTTPS origin to `YOUTUBE_MCP_HTTP_ALLOWED_ORIGINS`. The SDK
continues to validate Host and Origin headers. These allowlists are not
authentication: put Cloudflare Access in front of any public route and verify
that the intended MCP client can complete its authentication flow. Do not
disable Access or publish the route while that check is pending. This HTTP
entry point remains read-only even if YouTube upload flags are enabled.

## Credentials

Do not commit real credentials. Add them through GitHub Actions Secrets or
environment secrets.

Required secrets:

```text
META_PAGE_ID
META_PAGE_ACCESS_TOKEN
YOUTUBE_CHANNEL_ID
YOUTUBE_OAUTH_ACCESS_TOKEN
YOUTUBE_OAUTH_REFRESH_TOKEN
YOUTUBE_OAUTH_CLIENT_ID
YOUTUBE_OAUTH_CLIENT_SECRET
TIKTOK_ACCOUNT_ID
TIKTOK_ACCESS_TOKEN
X_ACCOUNT_ID
X_USER_ACCESS_TOKEN
```

Required production variables start as `false`:

```text
META_PUBLISHING_ENABLED
YOUTUBE_PUBLISHING_ENABLED
YOUTUBE_PUBLIC_POSTING_AUDITED
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
