from pathlib import Path
import sqlite3

import pytest

from meta_facebook_mcp_publisher.youtube_approval import (
    issue_upload_approval,
    reserve_approved_attempt,
    upload_approval_digest,
)


def _digest(path: Path, **overrides):
    values = {
        "channel_id": "UC-test",
        "title": "Approved title",
        "description": "Approved description",
        "made_for_kids": False,
        "privacy_status": "private",
        "tags": ["one", "two"],
        "category_id": "22",
    }
    values.update(overrides)
    return upload_approval_digest(path, **values)


def _reserve(db, token, digest, key="upload-1"):
    reserve_approved_attempt(db, token, digest, key, "UC-test", 6)


def test_operator_token_is_bound_to_video_and_metadata_and_one_time(tmp_path):
    video = tmp_path / "approved.mp4"
    video.write_bytes(b"original-video")
    db = tmp_path / "state.sqlite3"
    digest = _digest(video)
    token = issue_upload_approval(db, digest)

    video.write_bytes(b"changed-video")
    with pytest.raises(ValueError, match="No valid"):
        _reserve(db, token, _digest(video), "wrong-asset")
    video.write_bytes(b"original-video")

    changed_metadata = _digest(video, title="Different title")
    with pytest.raises(ValueError, match="No valid"):
        _reserve(db, token, changed_metadata, "wrong-metadata")

    _reserve(db, token, digest)
    with pytest.raises(ValueError, match="No valid"):
        _reserve(db, token, digest, "retry")

    with sqlite3.connect(db) as conn:
        rows = conn.execute("SELECT token_hash, used_at FROM youtube_upload_approvals").fetchall()
        assert len(rows) == 1
        assert rows[0][1] is not None
        assert token not in db.read_bytes().decode("latin1", errors="ignore")


def test_expired_approval_is_rejected(tmp_path):
    video = tmp_path / "approved.mp4"
    video.write_bytes(b"original-video")
    db = tmp_path / "state.sqlite3"
    digest = _digest(video)
    token = issue_upload_approval(db, digest)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "UPDATE youtube_upload_approvals SET expires_at='2000-01-01T00:00:00+00:00'"
        )
    with pytest.raises(ValueError, match="No valid"):
        _reserve(db, token, digest)


def test_missing_approval_and_duplicate_idempotency_fail(tmp_path):
    video = tmp_path / "approved.mp4"
    video.write_bytes(b"original-video")
    db = tmp_path / "state.sqlite3"
    digest = _digest(video)
    with pytest.raises(ValueError, match="one-time"):
        _reserve(db, "", digest)

    token = issue_upload_approval(db, digest)
    _reserve(db, token, digest, "same-key")
    second = issue_upload_approval(db, digest)
    with pytest.raises(ValueError, match="idempotency_key was already used"):
        _reserve(db, second, digest, "same-key")
