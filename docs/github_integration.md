# GitHub Integration Guide

## Repository Files To Add

Copy this package into the target repository:

- `meta_facebook_mcp_publisher/`
- `meta_facebook_mcp_publisher/.github/workflows/social-video-publisher.yml`

If the repository already has a `.github/workflows/` directory, move the
workflow file to:

```text
.github/workflows/social-video-publisher.yml
```

and keep the Python package at:

```text
meta_facebook_mcp_publisher/
```

## Required GitHub Secrets

Create these under repository or environment secrets:

| Secret | Platform | Purpose |
| --- | --- | --- |
| `META_PAGE_ID` | Facebook | Target Page ID |
| `META_PAGE_ACCESS_TOKEN` | Facebook | Page publishing token |
| `YOUTUBE_CHANNEL_ID` | YouTube | Target channel ID |
| `YOUTUBE_OAUTH_ACCESS_TOKEN` | YouTube | OAuth user token with upload scope |
| `TIKTOK_ACCOUNT_ID` | TikTok | Creator/account identifier |
| `TIKTOK_ACCESS_TOKEN` | TikTok | OAuth access token |
| `X_ACCOUNT_ID` | X | Target user/account ID |
| `X_USER_ACCESS_TOKEN` | X | User access token with post/media permissions |

## Required GitHub Variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `META_PUBLISHING_ENABLED` | `false` | Enable live Meta dispatch |
| `YOUTUBE_PUBLISHING_ENABLED` | `false` | Enable live YouTube dispatch |
| `TIKTOK_PUBLISHING_ENABLED` | `false` | Enable live TikTok dispatch |
| `TIKTOK_PUBLIC_POSTING_AUDITED` | `false` | Confirms TikTok audit for public posts |
| `X_PUBLISHING_ENABLED` | `false` | Enable live X dispatch |
| `META_REELS_DAILY_LIMIT` | `30` | Meta Reels local limit |
| `YOUTUBE_DAILY_UPLOAD_LIMIT` | `6` | Conservative YouTube local upload limit |
| `TIKTOK_DAILY_POST_LIMIT` | `30` | Local TikTok limit |
| `X_DAILY_POST_LIMIT` | `17` | Conservative X local post limit |

## Production Rule

Do not store tokens in files. Use GitHub Actions secrets. GitHub documents that
secrets are encrypted variables for workflows, and workflows access them through
the `secrets` context.

## Manual Execution

Run the workflow from GitHub Actions:

1. Open the repository.
2. Go to `Actions`.
3. Select `social-video-publisher`.
4. Click `Run workflow`.
5. Start with `dry_run=true`.
6. After all gates and credentials are verified, set `dry_run=false` and
   `human_approved=true`.

## Production Degraded Mode

The workflow can run even if one platform is missing. Connected and verified
platforms may publish; missing platforms return degraded status and do not block
the full agent.

