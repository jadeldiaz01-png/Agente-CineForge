"""One-time, operator-issued YouTube upload approvals.

The approval is a random bearer capability stored only as a SHA-256 digest.
It is bound to the video bytes and all upload-affecting metadata, expires
quickly, and is consumed in the same SQLite transaction as upload reservation.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def upload_approval_digest(
    video_path: Path,
    channel_id: str,
    title: str,
    description: str,
    made_for_kids: bool,
    privacy_status: str,
    tags: list[str],
    category_id: str,
) -> str:
    file_hash = hashlib.sha256()
    with video_path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            file_hash.update(block)
    bound = {
        "video_sha256": file_hash.hexdigest(),
        "channel_id": channel_id,
        "title": title,
        "description": description,
        "made_for_kids": bool(made_for_kids),
        "privacy_status": privacy_status,
        "tags": list(tags),
        "category_id": category_id,
    }
    canonical = json.dumps(bound, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _schema(db: sqlite3.Connection) -> None:
    db.execute(
        "CREATE TABLE IF NOT EXISTS youtube_upload_approvals ("
        "token_hash TEXT PRIMARY KEY, digest TEXT NOT NULL, "
        "expires_at TEXT NOT NULL, used_at TEXT)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS youtube_uploads ("
        "idempotency_key TEXT PRIMARY KEY, channel_id TEXT NOT NULL, "
        "created_at TEXT NOT NULL, status TEXT NOT NULL, video_id TEXT)"
    )


def issue_upload_approval(database: Path, digest: str, ttl_minutes: int = 10) -> str:
    if len(digest) != 64:
        raise ValueError("Invalid approval digest.")
    if not 1 <= ttl_minutes <= 15:
        raise ValueError("Approval lifetime must be between 1 and 15 minutes.")
    token = secrets.token_urlsafe(32)
    now = _utcnow()
    with sqlite3.connect(database, timeout=10) as db:
        db.execute("PRAGMA busy_timeout=10000")
        _schema(db)
        db.execute(
            "INSERT INTO youtube_upload_approvals(token_hash,digest,expires_at,used_at) "
            "VALUES(?,?,?,NULL)",
            (hashlib.sha256(token.encode("utf-8")).hexdigest(), digest,
             (now + timedelta(minutes=ttl_minutes)).isoformat()),
        )
    return token


def reserve_approved_attempt(
    database: Path,
    token: str,
    digest: str,
    idempotency_key: str,
    channel_id: str,
    limit: int,
) -> None:
    if not token.strip():
        raise ValueError("A one-time operator approval token is required.")
    if not idempotency_key.strip():
        raise ValueError("An idempotency_key is required.")
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = _utcnow()
    with sqlite3.connect(database, timeout=10, isolation_level=None) as db:
        db.execute("PRAGMA busy_timeout=10000")
        _schema(db)
        db.execute("BEGIN IMMEDIATE")
        approval = db.execute(
            "SELECT digest, expires_at, used_at FROM youtube_upload_approvals WHERE token_hash=?",
            (token_hash,),
        ).fetchone()
        if (approval is None or approval[0] != digest or approval[2] is not None
                or datetime.fromisoformat(approval[1]) <= now):
            db.rollback()
            raise ValueError("No valid, unused operator approval matches this exact video and metadata.")
        if db.execute(
            "SELECT 1 FROM youtube_uploads WHERE idempotency_key=?", (idempotency_key,)
        ).fetchone():
            db.rollback()
            raise ValueError("This idempotency_key was already used; reconcile the prior attempt before retrying.")
        cutoff = (now - timedelta(hours=24)).isoformat()
        count = db.execute(
            "SELECT COUNT(*) FROM youtube_uploads WHERE channel_id=? AND created_at>=?",
            (channel_id, cutoff),
        ).fetchone()[0]
        if count >= max(1, limit):
            db.rollback()
            raise ValueError("The local 24-hour YouTube upload limit has been reached.")
        db.execute(
            "INSERT INTO youtube_uploads VALUES (?, ?, ?, 'IN_PROGRESS', NULL)",
            (idempotency_key, channel_id, now.isoformat()),
        )
        db.execute(
            "UPDATE youtube_upload_approvals SET used_at=? WHERE token_hash=? AND used_at IS NULL",
            (now.isoformat(), token_hash),
        )
        if db.execute("SELECT changes()").fetchone()[0] != 1:
            db.rollback()
            raise ValueError("The operator approval was already consumed.")
        db.commit()
