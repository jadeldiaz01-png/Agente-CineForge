# P0 verified media/release gate — 2026-10-26

This work hardens CineForge without authorizing LIVE publishing or spending. Source state remains NOT_PRODUCTION_READY.

- Dry-run requires an **existing MP4** with independent ffprobe checks (H.264, vertical 9:16, >=720x1280, 1–90 seconds, <=250 MiB). The dry run reports DRY_RUN_VALIDATED and the SHA-256; never a fabricated remote post id.
- LIVE CLI requires CINEFORGE_LIVE_PUBLISH_AUTHORIZED=true and an independently signed JSON attestation supplied by --approval-evidence. It binds SHA-256 of exact video, caption, sorted platform names, expiry, approving human identity and separate positive QC/originality checks. The signature is HMAC-SHA256 using CINEFORGE_APPROVAL_HMAC_KEY (>=32 chars) available only as a production secret. UI checkbox alone is insufficient. A separate authenticated human signing process is still required before LIVE use.
- YouTube resumable upload does not count session initialization as completion. Transfer bytes with final PUT and require returned video id. UPLOAD_CONFIRMED is not proof of public visibility.
- TikTok sends a single <=64MiB binary chunk to an allowlisted upload host but returns DISPATCHED_UNVERIFIED until remote status and public post link can be reconciled. Larger uploads remain blocked.
- Meta receives dispatch ID but returns DISPATCHED_UNVERIFIED; X is BLOCKED_BY_POLICY until documented full chunk transfer, status reconciliation and contract tests exist.
- External platform credentials and formal permissions are not part of this PR. The branch and its CI are preparation-only; no live tests, public posts, captures or expenditures are authorized.
- Security boundary: the CLI AND direct connector gate now validate the content-bound attestation independently. No ungoverned calls allowed without a signed release. Production hardening still requires persistent idempotency and account-level rate-limit reconciliation.
- Reference promotional sample is original 24-second vector motion graphics with synthesized audio, not a generative video model's output. Separate MP4, storyboard and QC/visual review artifacts are delivered in the conversation; they do not themselves authorize release.
- Production GO/NO-GO remains NO-GO until human/platform gates in config/production-readiness.json and external status checks are satisfied.

## P0 durable-at-most-once protection

The live publish connector gate now atomically reserves a unique idempotency key **and** content+account+platform SHA-256 in a SQLite WAL ledger *before* any external call. A duplicate or uncertain prior attempt stays blocked for human reconciliation. No autonomous retry or re-use of the same video/caption/target is permitted.

Use only a previously provisioned, backed-up, permission-restricted **persistent** volume at `/var/lib/cineforge/`; set `CINEFORGE_PUBLISH_LEDGER_PATH` and `CINEFORGE_DURABLE_LEDGER_CERTIFIED=true` only after a separate human storage certification. GitHub-hosted Actions is ephemeral and cannot satisfy that condition. For multiple replicas or hosts, this local SQLite ledger is NOT a global transactional authority: use a shared transactional datastore before LIVE. SQLite tests certify atomicity only; production persistence and external platform reconciliation remain unverified.

## CI provenance and corrected production scope

CI now produces an evidence TAR archive, a Sigstore provenance attestation and a GitHub CLI verification receipt, following a pinned `actions/attest` release. The standalone CI attestation is **not** permission to promote a video/publisher. The production readiness declaration remains `BLOCKED` until supported, independently verified evidence is attached for protected main, signatures, remote publication reconciliation, storage persistence and actual generative quality. Static documentation assertions cannot satisfy those external gates.

TikTok status semantics follow the official August 2026 status API; `SEND_TO_USER_INBOX` and `PROCESSING_UPLOAD` are not public posts, and `PUBLISH_COMPLETE` needs a matching publicly available post ID for public visibility verification. Repeated dispatches remain prohibited while prior outcome is unknown.
