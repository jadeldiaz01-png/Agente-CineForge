# CineForge / ChatGPT · YouTube read-only MCP integration

**State: PREPARE_ONLY · NO AUTH, NO DEPLOY, NO YOUTUBE PUBLISHING.**

## Existing route to connect ChatGPT immediately

Windsor.ai is already installed in ChatGPT but its YouTube connector has **no connected account** (checked 2026-11-09). Open the onboarding link provided in ChatGPT and sign in to Google. **Select the Brand Account with the actual channel name**, not a personal account without a channel. Authorize only after reading Google's permissions screen. Windsor's own connection is independent of this repository and does not grant tokens to CineForge.

After consent, re-check Windsor \`get_connectors\` for an actual YouTube account, then read approved channel analytics through the connector. Do not claim the channel is connected until an account is returned.

## CineForge local MCP, separate from Windsor

Modules:
- \`youtube_readonly.py\`: allowlisted HTTPS **GET-only** calls to YouTube Data API v3 and YouTube Analytics reports.
- \`youtube_readonly_mcp.py\`: MCP v2 stdio tools: \`youtube_my_channel\`, \`youtube_my_recent_videos\`, \`youtube_my_analytics\`.
- \`tests/test_youtube_readonly.py\`: offline/no-token/error-negative tests.

Google OAuth scopes required for a distinct, **read-only** connection:

- \`https://www.googleapis.com/auth/youtube.readonly\`
- \`https://www.googleapis.com/auth/yt-analytics.readonly\`

The integration requests no publishing or financial scopes and returns no revenue unless an independently approved future read-only monetary-scope change is reviewed. Google OAuth consent should be completed in an authorized browser by the channel owner. A secure OAuth broker and encrypted token storage are **not** implemented by this PR.

### Local setup, only after a Google OAuth connection has been granted

\`\`\`bash
python -m pip install '.[youtube-mcp]'
python -m unittest discover -s tests -p 'test_youtube_readonly.py'
# Set YOUTUBE_READONLY_ACCESS_TOKEN via an approved private secret store,
# never a committed .env, a chat message, or pasted shell history.
python -m meta_facebook_mcp_publisher.youtube_readonly_mcp
\`\`\`

This starts a **local stdio** MCP process, not a public web endpoint and **not automatically a ChatGPT connector**. For remote ChatGPT MCP use, deploy a separate HTTPS Streamable HTTP server with OAuth 2.0 token exchange, resource/audience validation, rate limiting and secret storage; obtain independent security review first. Do not expose this stdio process with an unauthenticated tunnel.

## Workflow after connect

1. Read \`mine=true\` channel identity, confirm desired Brand Account and channel ID.
2. Retrieve owned recent video titles and publish dates from uploads playlist.
3. Query up to 90 days of non-financial YouTube Analytics: views, watch minutes, subscribers gained.
4. Map insights to **CineForge's existing** trend research and human-reviewed creative briefs, while verifying creative rights and content quality.
5. Prepare scripts/storyboards/MP4 drafts offline; **do not publish** automatically. Existing publisher flags remain off.
6. Seek human approval and independent production certification before any upload scope or public post.

## Operating and cost controls

- No API key or access token is committed, exposed in responses or stored by this module.
- Only fixed Google HTTPS API hosts and GET calls; 12-second outbound timeout.
- No video creation, payment, publication, channel mutation or background loop.
- \`YOUTUBE_READONLY_ACCESS_TOKEN\` is intentionally distinct from legacy \`YOUTUBE_OAUTH_ACCESS_TOKEN\` used by the publishing scaffold.
- Quotas are enforced by Google; no automated calls are scheduled in this PR.
- Calls may fail with \`NOT_CONNECTED\`, \`403\` or \`401\` until user consent, API activation and channel permissions are complete.
- YouTube Analytics and AdSense for content are separate; monetization requires YouTube Partner Program eligibility.

## Evidence and gates

- [ ] Account connection confirmed through the connector's connected-account result.
- [ ] API authorization limited to exact read-only scopes, channel identity checked.
- [ ] Offline tests and GitHub PR CI green for exact SHA.
- [ ] Authorized test invocation on VPS with no tokens printed.
- [ ] Consent revocation and token expiry response verified.
- [ ] Rate limits and secure token broker evaluated before remote production deployment.
- [ ] Independent approval before any publishing, ordering, spending or writes.

Official references:
- https://developers.google.com/identity/protocols/oauth2/scopes
- https://developers.google.com/youtube/analytics/reference/reports/query
- https://py.sdk.modelcontextprotocol.io/
