"""Atomic, fail-closed at-most-once reservation for governed publishing.

This ledger must reside on a separately certified persistent filesystem in LIVE.
Reserved/unknown outcomes are *never* retried without remote reconciliation.
SQLite proves serialization on one durable volume, NOT distributed idempotency.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sqlite3


class PublishReservationDenied(ValueError):
    pass


def intent_digest(platform: str, account_id: str, video_sha256: str, caption: str) -> str:
    if not all((platform, account_id, video_sha256, caption)):
        raise PublishReservationDenied("INCOMPLETE_PUBLISH_INTENT")
    payload = json.dumps([platform, account_id, video_sha256, caption],
                         ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def reserve_publish_attempt(database: Path, key: str, platform: str,
                            account_id: str, video_sha256: str, caption: str) -> str:
    """Reserve an intention BEFORE an external API call; duplicates raise, including unknowns."""
    if not isinstance(key, str) or not key.strip() or len(key) > 256:
        raise PublishReservationDenied("IDEMPOTENCY_KEY_INVALID")
    if not database.is_absolute() or not database.parent.is_dir() or database.is_symlink():
        raise PublishReservationDenied("PERSISTENT_LEDGER_PATH_INVALID")
    digest = intent_digest(platform, account_id, video_sha256, caption)
    connection = None
    try:
        connection = sqlite3.connect(str(database), timeout=5, isolation_level=None)
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("""CREATE TABLE IF NOT EXISTS publish_attempts (
            idempotency_key TEXT PRIMARY KEY,
            intent_sha256 TEXT NOT NULL UNIQUE,
            platform TEXT NOT NULL,
            created_utc TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status = 'RESERVED_UNRECONCILED')
        )""")
        connection.execute("""INSERT INTO publish_attempts
            (idempotency_key, intent_sha256, platform, created_utc, status)
            VALUES (?, ?, ?, ?, 'RESERVED_UNRECONCILED')""",
            (key, digest, platform, datetime.now(timezone.utc).isoformat()))
        connection.execute("COMMIT")
        return digest
    except sqlite3.IntegrityError as exc:
        if connection and connection.in_transaction:
            connection.execute("ROLLBACK")
        raise PublishReservationDenied("DUPLICATE_OR_UNRECONCILED_PUBLISH") from exc
    except sqlite3.Error as exc:
        if connection and connection.in_transaction:
            connection.execute("ROLLBACK")
        raise PublishReservationDenied("PUBLISH_LEDGER_UNAVAILABLE") from exc
    finally:
        if connection:
            connection.close()
