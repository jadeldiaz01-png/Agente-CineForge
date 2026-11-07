# CineForge — repository instructions for Codex

## Code Review Rules

### Reject unsafe publication and false approvals (P0)
- Any path that calls a social platform API or can cause external posting must deny publication unless permissions, owner consent, account identity, platform review, video QC, originality/license evidence, an exact-sha human release and durable idempotency have been independently verified.
- Do not treat GitHub passing tests, a Codex review comment, an emoji reaction, an OAuth token being present, uploaded-media acknowledgment, or a `mergeable` flag as authorization to publish or deploy.
- Never set `publication_authorized`, `production_ready`, model rights, platform permissions, or external ledger durability to true based on synthetic tests, mocked API replies, comments, or missing evidence.

### Preserve exact-artifact provenance and deduplication (P0/P1)
- Report P0/P1 if the code can approve a different media SHA-256, caption or destination than the signed release, allow untrusted media paths or URLs, or retry a possibly completed external post without remote reconciliation.
- Persistent ledger tests in CI, including a synthetic boot ID change, are only tests of logic; they are not evidence that the user's VPS has durable storage, backup recovery or multi-node atomicity.

### Video analysis and rendering truthfulness (P1)
- All generated previews and clip suggestions must remain local and unauthorized for publishing by default. A heuristic activity score is not a predicted view count, viral probability or revenue.
- FFmpeg-composed or upscaled video must not be described as a model-generated, native-Full-HD output or a certified generative benchmark. Protect untrusted media input with bounded decode, timeouts, output QC and SHA-256 checks.

### Review outcome and automation policy
- Focus findings on actionable P0/P1 security, data integrity, authorization and production correctness regressions. Explicitly identify any blocker, the changed lines, and what would fix it.
- The repository owner asks for automatic **Codex** review as the only AI-review signal. Do not claim a formal GitHub `APPROVED` event unless GitHub actually recorded that review state on the current PR head. A `COMMENTED` review or a thumbs-up is not equivalent to GitHub branch-protection approval.
- Codex code reviews are not substitutes for platform account permissions, documented media rights, model benchmarks, external deployment evidence, CI, or other independently enforced gates. Never merge or enable production merely because no P0/P1 findings were posted.
