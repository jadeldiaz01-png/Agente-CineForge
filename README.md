# Social Video MCP Publisher

Production-ready scaffold for connecting a premium video agent to Facebook,
YouTube, TikTok and X publishing APIs.

## Current Certification Status

Status: `NOT_PRODUCTION_READY`

Reason: credentials, platform review/audit, account permissions, and live API
dispatch must be verified per platform before publishing is enabled.

## Required Meta Capabilities

- Facebook Page access token.
- Page ID controlled by the authenticated user.
- Permission to create Page content.
- `pages_manage_posts` for Page post creation.
- Read permissions such as `pages_show_list` / `pages_read_engagement` for
  Page discovery and status checks, depending on the workflow.

Primary references:

- https://developers.facebook.com/documentation/video-api/guides/publishing
- https://developers.facebook.com/documentation/video-api/guides/reels-publishing
- https://developers.facebook.com/docs/graph-api/reference/page/videos/
- https://developers.facebook.com/docs/permissions/

## Required YouTube Capabilities

- Google OAuth 2.0 user authorization.
- YouTube Data API v3 enabled.
- Upload scope for the authenticated channel.
- Local quota guard for uploads.

Primary references:

- https://developers.google.com/youtube/v3/guides/uploading_a_video
- https://developers.google.com/youtube/v3/docs/videos/insert

## Required TikTok Capabilities

- TikTok developer app with Content Posting API product enabled.
- OAuth access token for the creator.
- Direct Post audit for public visibility. Unaudited clients may be restricted
  to private visibility.

Primary references:

- https://developers.tiktok.com/doc/content-posting-api-reference-direct-post
- https://developers.tiktok.com/doc/content-posting-api-get-started

## Required X Capabilities

- X user access token with write/media capability.
- Media upload flow for videos.
- Post creation endpoint access and rate-limit handling.

Primary references:

- https://docs.x.com/x-api/media/introduction
- https://docs.x.com/x-api/media/quickstart/media-upload-chunked
- https://docs.x.com/x-api/posts/create-post
- https://docs.x.com/x-api/fundamentals/rate-limits

## Publishing Gates

The publisher must fail closed unless all gates pass:

| Gate | Required Evidence |
| --- | --- |
| `ACCESS_TOKEN_PRESENT` | Platform access token configured |
| `ACCOUNT_ID_PRESENT` | Target Page/channel/account configured |
| `VIDEO_QC_PASSED` | MP4 validated by video QC pipeline |
| `ORIGINALITY_REVIEWED` | Copyright/originality review completed |
| `HUMAN_APPROVED` | User approved video, caption, thumbnail and platform |
| `RATE_LIMIT_ALLOWED` | Local quota allows the post |
| `IDEMPOTENCY_KEY_PRESENT` | Unique key attached to publish attempt |
| `PUBLIC_POSTING_AUDITED` | Platform review/audit allows public posting |

## Integration Flow

```text
CineForge/Premium Video Agent
  -> ffprobe + loudness + subtitle QC
  -> Compliance/Copyright review
  -> Human approval
  -> MultiPlatformPublisher.publish_many()
  -> status polling / reconciliation
  -> Evidence ledger
```

## Environment

Copy `.env.example` and configure secrets in your secret manager. Do not commit
real tokens.

```bash
META_GRAPH_VERSION=v26.0
META_PAGE_ID=1234567890
META_PAGE_ACCESS_TOKEN=stored-in-secret-manager
META_PUBLISHING_ENABLED=false
YOUTUBE_PUBLISHING_ENABLED=false
TIKTOK_PUBLISHING_ENABLED=false
X_PUBLISHING_ENABLED=false
```

Each platform publishing flag must remain `false` until live contract tests and
permissions are verified. Missing connectors are handled as degraded platform
states, not as global agent failure.

## GitHub Actions Execution

This package includes a manual workflow at:

```text
meta_facebook_mcp_publisher/.github/workflows/social-video-publisher.yml
```

When integrating into a repository, place that file at:

```text
.github/workflows/social-video-publisher.yml
```

The workflow uses GitHub Secrets for credentials and GitHub Variables for
production enable flags. See `docs/github_integration.md`.
