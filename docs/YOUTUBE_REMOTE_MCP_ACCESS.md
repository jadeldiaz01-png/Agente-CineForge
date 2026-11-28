# Remote CineForge YouTube MCP — gated upload rollout

Status: upload tool can be exposed, but publishing remains disabled by default. This runbook does not authorize a particular video upload.
Existing local service on 127.0.0.1:8766 must remain unchanged. The existing
tunnel route is intended to reach 127.0.0.1:8765; do not point it at 8766.

## Prerequisites

- Exact reviewed commit, passing CI, and owner authorization for deployment.
- Cloudflare Access self-hosted application covering the entire hostname
  youtube-mcp.jadeltechrd.com, including all MCP paths. No Bypass, Everyone,
  or service-token policy. Allow exactly the owner's Google identity.
- Enable Managed OAuth; DCR only for the exact callback URI shown by ChatGPT
  in its MCP setup UI. Do not wildcard ChatGPT callbacks. Allow loopback
  redirects only if deliberately testing a trusted CLI client. Use short
  access-token lifetime (15m) and grant session (24h).
- Verify the resource metadata and authorization server metadata at the edge,
  authorization code + PKCE S256, registration mode, resource/audience,
  and actual callback. Do not assume ChatGPT plan eligibility or compatibility.
- Obtain the team domain and this app's AUD from Cloudflare Access, not
  from a token provided by a caller. Origin accepts Cloudflare signed
  Cf-Access-Jwt-Assertion, not the opaque client access token.
- Existing YouTube env file remains outside Git. The remote server exposes
  `youtube_channel_info` and the gated `upload_youtube_video` tool.
- The upload tool accepts a path to an MP4 already present on the VPS inside
  `YOUTUBE_ALLOWED_VIDEO_DIR`; it does not transfer a ChatGPT attachment.
- Upload approval is issued locally by an operator, not asserted by MCP boolean
  arguments. A one-time token is bound to the exact file SHA-256, channel,
  title, description, child-directed flag, privacy, tags, and category; it
  expires after 10 minutes and is consumed atomically with the idempotency
  reservation. The raw token is never stored in SQLite.
- Keep `YOUTUBE_PUBLISHING_ENABLED=false` and
  `YOUTUBE_PUBLIC_POSTING_AUDITED=false` until an approved asset, metadata,
  privacy level, and private-upload reconciliation procedure are in place.

## Prepare independent runtime

After exact-SHA approval, install reviewed source in a new directory, not
the currently running local checkout. Example: set REVIEWED_SHA to the
approved commit, then run:

```bash
test -n "${REVIEWED_SHA:-}" || exit 1
git clone --no-checkout https://github.com/jadeldiaz01-png/Agente-CineForge.git "$HOME/cineforge-remote"
cd "$HOME/cineforge-remote"
git checkout --detach "$REVIEWED_SHA"
test "$(git rev-parse HEAD)" = "$REVIEWED_SHA" || exit 1
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/python -m pip check
```

If GitHub authentication is needed use existing approved credential helper.
Record exact dependency versions and evaluate vulnerabilities before release.
Create configuration without echoing credentials:

```bash
umask 077
install -d -m 700 "$HOME/.jadeltechrd/secrets"
touch "$HOME/.jadeltechrd/secrets/cloudflare-mcp.env"
chmod 600 "$HOME/.jadeltechrd/secrets/cloudflare-mcp.env"
nano "$HOME/.jadeltechrd/secrets/cloudflare-mcp.env"
```

Set the real values locally (never commit the file):
```dotenv
CF_ACCESS_TEAM_DOMAIN=YOUR-TEAM.cloudflareaccess.com
CF_ACCESS_AUD=YOUR-APPLICATION-AUDIENCE-TAG
CF_ACCESS_OWNER_EMAIL=YOUR-OWNER-EMAIL
```

Use a dedicated systemd unit only after configuring the Access edge policy:
```ini
[Unit]
Description=CineForge protected remote YouTube MCP
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/cineforge-remote
EnvironmentFile=/home/ubuntu/.jadeltechrd/secrets/cloudflare-mcp.env
Environment=YOUTUBE_ENV_FILE=/home/ubuntu/.jadeltechrd/secrets/youtube.env
Environment=YOUTUBE_PUBLISHING_ENABLED=false
Environment=YOUTUBE_PUBLIC_POSTING_AUDITED=false
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/home/ubuntu/cineforge-remote/.venv/bin/python -m meta_facebook_mcp_publisher.youtube_remote_access
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
UMask=0077

[Install]
WantedBy=multi-user.target
```

Save as /etc/systemd/system/cineforge-mcp-remote.service. Start only after
review and ensuring port 8765 is free. Do not open a firewall port.
Keep the original local service active.
```bash
sudo systemctl daemon-reload
sudo systemctl start cineforge-mcp-remote
sudo systemctl is-active cineforge-mcp-remote
sudo ss -lntp | grep ':8765'
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8765/mcp
curl -sS -o /dev/null -w '%{http_code}\n' -H 'Cf-Access-Jwt-Assertion: invalid' http://127.0.0.1:8765/mcp
```
Both direct requests must return 401; never send real JWTs in terminal logs.
At the public URL, a non-browser request must trigger an OAuth challenge,
not 200/502 or a generic login page. Edge metadata must be valid HTTPS JSON.
Use a real MCP client, authenticate with the owner, and assert both
youtube_channel_info and upload_youtube_video are listed. Make 3 channel-info
calls and compare channel ID. With publishing disabled, call upload and assert
it fails closed before OAuth or YouTube access. To authorize one specific test
upload, run `python -m meta_facebook_mcp_publisher.youtube_approval_cli` locally
as the service account, review the exact asset and metadata, and pass its
short-lived token only to that exact MCP call. Confirm a missing, invalid,
expired, reused, or metadata-mismatched approval fails without calling YouTube.
denied account and revoked/expired token behavior. Check restart and repeat
authenticated calls. Record sanitized evidence, commit SHA, dependency
versions, app policy/AUD (no tokens), timestamps, and client identity.
Enable autostart only after the agreed gates pass. The service may be enabled
for boot while publishing remains disabled.

## Rollback

Stop and disable only cineforge-mcp-remote. Keep Access policy in place;
disable/remove the published route if necessary. Verify the existing local
service on 8766 still works. Never reroute to the unauthenticated local port.
No upload, no production claim without actual authenticated external test.

## References

- https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/managed-oauth/
- https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/
- https://developers.openai.com/plugins/build/auth
- https://developers.openai.com/api/docs/guides/custom-mcp-server
