# Production Readiness Matrix

| Area | Required For Production | Current Scaffold |
| --- | --- | --- |
| Meta credentials | Page token from approved Meta app | Environment placeholders only |
| YouTube credentials | OAuth token with upload scope | Environment placeholders only |
| TikTok credentials | OAuth token and Content Posting API product | Environment placeholders only |
| X credentials | User token with post/media permissions | Environment placeholders only |
| Permissions | Platform review/audit for public posting | Documented, not verified |
| Human approval | Required before external publication | Enforced in gates |
| Video QC | ffprobe/loudness/subtitle/originality checks | Contract placeholder |
| Idempotency | Stable publish attempt key | Required by model |
| Rate limit | Per-platform local quota guard | Enforced as configurable gate |
| Evidence | Store request, response, approval, asset hash | Planned integration point |
| Reconciliation | Poll remote status and compare post ID/link | Planned integration point |
| Secrets | Secret manager, no committed tokens | `.env.example` only |
| CI | Unit, contract, policy and secret scanning | Unit tests included |

## Production GO/NO-GO

Do not enable platform publishing flags until:

1. Meta app is in Live mode with approved Page publishing permissions.
2. Page access token is generated through the approved app.
3. A sandbox Page contract test publishes one approved test video.
4. Reconciliation stores the remote post/video ID.
5. Human approval audit record is linked to the publish attempt.
6. Rate limit counters are persisted, not only in memory.
7. Secrets are loaded from a secret manager.

## Degraded Production Mode

The agent can run in production when at least one platform connector is verified.
Unverified platforms must return `DEGRADED_NOT_CONNECTED` or
`DEGRADED_NOT_PRODUCTION_READY`; they must not block creation, QC, approval,
or publishing to verified platforms.
