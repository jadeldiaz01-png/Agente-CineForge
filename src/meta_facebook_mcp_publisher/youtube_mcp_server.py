from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .gates import evaluate_platform_publish_gates
from .models import Platform, PlatformPublishRequest
from .platform_clients import YouTubeClient

server = FastMCP("cineforge-youtube")
_env_file_loaded = False


def _load_secret_file() -> None:
    """Load a user-supplied local env file; process env values take precedence."""
    global _env_file_loaded
    if _env_file_loaded:
        return
    env_file = os.getenv("YOUTUBE_ENV_FILE", "").strip()
    if env_file:
        path = Path(env_file).expanduser()
        if not path.is_file():
            raise FileNotFoundError("YOUTUBE_ENV_FILE does not point to a readable file.")
        try:
            from dotenv import load_dotenv
        except ImportError as exc:
            raise RuntimeError("Install the project with python-dotenv to load YOUTUBE_ENV_FILE.") from exc
        if not load_dotenv(dotenv_path=path, override=False):
            raise RuntimeError("The configured YOUTUBE_ENV_FILE could not be loaded.")
    _env_file_loaded = True


def _configured_client() -> tuple[YouTubeClient, str, str]:
    _load_secret_file()
    channel_id = os.getenv("YOUTUBE_CHANNEL_ID", "").strip()
    access_token = os.getenv("YOUTUBE_OAUTH_ACCESS_TOKEN", "").strip()
    refresh_token = os.getenv("YOUTUBE_OAUTH_REFRESH_TOKEN", "").strip()
    if not channel_id:
        raise ValueError("YOUTUBE_CHANNEL_ID is not configured.")
    if not (access_token or refresh_token):
        raise ValueError("Configure YouTube OAuth credentials before using this server.")
    return YouTubeClient(), channel_id, access_token


def _video_path(value: str) -> Path:
    root = Path(os.getenv("YOUTUBE_ALLOWED_VIDEO_DIR", "artifacts")).expanduser().resolve()
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("The video must be inside YOUTUBE_ALLOWED_VIDEO_DIR.")
    if not candidate.is_file() or candidate.suffix.lower() != ".mp4":
        raise ValueError("The video must be an existing MP4 file inside the allowed directory.")
    return candidate


def _ledger_path() -> Path:
    configured = os.getenv("YOUTUBE_LEDGER_PATH", "").strip()
    path = Path(configured).expanduser() if configured else Path.home() / ".local/state/cineforge/youtube.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass
    return path


def _reserve_attempt(key: str, channel_id: str, limit: int) -> None:
    if not key.strip():
        raise ValueError("An idempotency_key is required.")
    db = sqlite3.connect(_ledger_path(), timeout=10, isolation_level=None)
    try:
        db.execute("PRAGMA busy_timeout=10000")
        db.execute(
            "CREATE TABLE IF NOT EXISTS youtube_uploads ("
            "idempotency_key TEXT PRIMARY KEY, channel_id TEXT NOT NULL, "
            "created_at TEXT NOT NULL, status TEXT NOT NULL, video_id TEXT)"
        )
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT 1 FROM youtube_uploads WHERE idempotency_key=?", (key,)).fetchone():
            db.rollback()
            raise ValueError("This idempotency_key was already used; reconcile the prior attempt before retrying.")
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        count = db.execute(
            "SELECT COUNT(*) FROM youtube_uploads WHERE channel_id=? AND created_at>=?",
            (channel_id, cutoff),
        ).fetchone()[0]
        if count >= limit:
            db.rollback()
            raise ValueError("The local 24-hour YouTube upload limit has been reached.")
        db.execute(
            "INSERT INTO youtube_uploads VALUES (?, ?, ?, 'IN_PROGRESS', NULL)",
            (key, channel_id, datetime.now(timezone.utc).isoformat()),
        )
        db.commit()
    finally:
        db.close()


def _finish_attempt(key: str, status: str, video_id: str | None) -> None:
    db = sqlite3.connect(_ledger_path(), timeout=10)
    try:
        db.execute(
            "UPDATE youtube_uploads SET status=?, video_id=? WHERE idempotency_key=?",
            (status, video_id, key),
        )
        db.commit()
    finally:
        db.close()


@server.tool()
def youtube_channel_info() -> dict:
    """Return the channel ID and title associated with the configured OAuth credentials."""
    client, channel_id, access_token = _configured_client()
    return client.get_channel_info(access_token, channel_id)


@server.tool()
def upload_youtube_video(
    video_path: str,
    title: str,
    description: str,
    made_for_kids: bool,
    human_approved: bool = False,
    video_qc_passed: bool = False,
    originality_reviewed: bool = False,
    privacy_status: str = "private",
    tags: list[str] | None = None,
    category_id: str = "22",
    idempotency_key: str = "",
) -> dict:
    """Upload an approved MP4. Uploading requires the server publish flag and explicit approval."""
    if os.getenv("YOUTUBE_PUBLISHING_ENABLED", "").lower() not in {"1", "true", "yes", "on"}:
        raise ValueError("YOUTUBE_PUBLISHING_ENABLED is off; upload blocked.")
    client, channel_id, access_token = _configured_client()
    if not 1 <= len(title) <= 100:
        raise ValueError("title must contain 1 to 100 characters.")
    if len(description) > 5000:
        raise ValueError("description exceeds YouTube's 5000-character limit.")
    if privacy_status not in {"private", "unlisted", "public"}:
        raise ValueError("privacy_status must be private, unlisted, or public.")
    if privacy_status == "public" and os.getenv("YOUTUBE_PUBLIC_POSTING_AUDITED", "").lower() not in {"1", "true", "yes", "on"}:
        raise ValueError("Public upload is blocked until YOUTUBE_PUBLIC_POSTING_AUDITED is enabled.")
    path = _video_path(video_path)
    limit = max(1, int(os.getenv("YOUTUBE_DAILY_UPLOAD_LIMIT", "6")))
    request = PlatformPublishRequest(
        platform=Platform.YOUTUBE,
        video_path=path,
        caption=description,
        idempotency_key=idempotency_key,
        human_approved=human_approved,
        video_qc_passed=video_qc_passed,
        originality_reviewed=originality_reviewed,
        publishing_enabled=True,
        access_token=access_token,
        account_id=channel_id,
        daily_limit=limit,
        public_posting_audited=privacy_status != "public" or os.getenv("YOUTUBE_PUBLIC_POSTING_AUDITED", "").lower() in {"1", "true", "yes", "on"},
        metadata={
            "title": title,
            "tags": ",".join(tags or []),
            "category_id": category_id,
            "privacy_status": privacy_status,
            "made_for_kids": str(made_for_kids).lower(),
        },
    )
    decision = evaluate_platform_publish_gates(request)
    if not decision.allowed:
        return {"ok": False, "status": "BLOCKED_BY_POLICY", "failed_gates": list(decision.failed_gates)}
    _reserve_attempt(idempotency_key, channel_id, limit)
    result = client.publish_video(request)
    _finish_attempt(idempotency_key, result.status, result.remote_id)
    return {
        "ok": result.ok,
        "status": result.status,
        "channel_id": channel_id,
        "video_id": result.remote_id,
        "video_url": f"https://www.youtube.com/watch?v={result.remote_id}" if result.remote_id else None,
        "error": result.error,
    }


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
