#!/usr/bin/env python3
"""Two-stage, isolated, same-host SQLite durability probe for CineForge.

It creates a disposable dedicated probe DB and a JSON receipt in a private,
pre-existing directory. It NEVER opens or writes the live publication ledger.

Stage 1 before a *real* host reboot:
  python scripts/cineforge_ledger_reboot_probe.py prepare --root /path/to/private-probe

Stage 2 after a *real* host reboot:
  python scripts/cineforge_ledger_reboot_probe.py verify --root /path/to/private-probe --id <returned_id>

Even a PASS is partial evidence, NOT production/storage/backup/multihost certification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import sys

from meta_facebook_mcp_publisher.publish_ledger import intent_digest, reserve_publish_attempt


class StorageProbeError(ValueError):
    pass


IDENTIFIER = re.compile(r"^[a-f0-9]{32}$")
BOOT_ID = Path("/proc/sys/kernel/random/boot_id")


def boot_id() -> str:
    try:
        value = BOOT_ID.read_text(encoding="utf-8").strip()
        if not re.fullmatch(r"[a-f0-9-]{36}", value, re.I):
            raise ValueError()
        return value
    except (OSError, ValueError) as exc:
        raise StorageProbeError("OS_BOOT_ID_UNAVAILABLE") from exc


def safe_directory(root: Path) -> Path:
    if not root.is_absolute():
        raise StorageProbeError("ABSOLUTE_ROOT_REQUIRED")
    # Parent paths must not redirect operations outside the intended host location.
    if any(part == ".." for part in root.parts):
        raise StorageProbeError("TRAVERSAL_FORBIDDEN")
    root = Path(os.path.abspath(str(root)))
    for path in (root, *root.parents):
        if path.is_symlink():
            raise StorageProbeError("SYMLINK_PARENT_FORBIDDEN")
    if not root.is_dir():
        raise StorageProbeError("EXISTING_PROBE_DIRECTORY_REQUIRED")
    if (root.stat().st_mode & 0o077) or not stat.S_ISDIR(root.stat().st_mode):
        raise StorageProbeError("PRIVATE_PROBE_DIRECTORY_REQUIRED")
    if root.stat().st_uid != os.geteuid():
        raise StorageProbeError("PROBE_DIRECTORY_OWNER_MISMATCH")
    return root


def names(root: Path, identifier: str) -> tuple[Path, Path]:
    if not IDENTIFIER.fullmatch(identifier):
        raise StorageProbeError("INVALID_PROBE_IDENTIFIER")
    return root / f"probe-{identifier}.sqlite3", root / f"probe-{identifier}.json"


def start(root: Path) -> dict:
    root = safe_directory(root)
    current_boot = boot_id()
    identifier = secrets.token_hex(16)
    db, receipt = names(root, identifier)
    # Nonexistent random-named targets: never overwrite any prior probe files.
    if db.exists() or receipt.exists():
        raise StorageProbeError("PROBE_ALREADY_EXISTS")
    key = "cineforge-verify-" + identifier
    try:
        intent = reserve_publish_attempt(db, key, "probe_only", "local_verification",
                                         "0" * 64, "synthetic receipt, never publish")
        payload = {
            "schema_version": 1,
            "kind": "cineforge.same_host_reboot_probe",
            "id": identifier,
            "initial_boot_id": current_boot,
            "intent_sha256": intent,
            "publication_authorized": False,
            "production_certified": False,
            "backup_restore_certified": False,
            "multi_host_atomicity_certified": False
        }
        handle = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(handle, "w", encoding="utf-8") as sink:
            json.dump(payload, sink, indent=2, sort_keys=True)
            sink.write("\n")
            sink.flush()
            os.fsync(sink.fileno())
        return {"status": "PREPARED_FOR_REBOOT", "probe_id": identifier,
                "production_ready": False, "publication_authorized": False,
                "instruction": "Verify the exact same probe after an actual host reboot"}
    except Exception:
        # If receipt preparation fails, never alter a real ledger. The isolated DB can
        # be left for forensic review rather than confusing it with a live ledger.
        raise


def verify(root: Path, identifier: str) -> dict:
    root = safe_directory(root)
    db, receipt = names(root, identifier)
    if not db.is_file() or db.is_symlink() or not receipt.is_file() or receipt.is_symlink():
        raise StorageProbeError("PERSISTED_PROBE_NOT_FOUND")
    if any((f.stat().st_mode & 0o077) for f in (db, receipt)):
        raise StorageProbeError("PROBE_FILES_NOT_PRIVATE")
    try:
        payload = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StorageProbeError("PROBE_RECEIPT_INVALID") from exc
    if (payload.get("kind") != "cineforge.same_host_reboot_probe"
            or payload.get("schema_version") != 1
            or payload.get("id") != identifier
            or payload.get("publication_authorized") is not False
            or payload.get("production_certified") is not False
            or payload.get("initial_boot_id") == boot_id()):
        raise StorageProbeError("REBOOT_NOT_INDEPENDENTLY_OBSERVED_OR_RECEIPT_INVALID")
    expected = intent_digest("probe_only", "local_verification",
                             "0" * 64, "synthetic receipt, never publish")
    if payload.get("intent_sha256") != expected:
        raise StorageProbeError("PROBE_INTENT_DIGEST_INVALID")
    # Read-only inspection: verification cannot reserve a live publish intent.
    uri = db.as_uri() + "?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True, timeout=5) as con:
            integrity = con.execute("PRAGMA integrity_check").fetchone()
            rows = con.execute(
                "SELECT idempotency_key, intent_sha256, status FROM publish_attempts"
            ).fetchall()
        if integrity != ("ok",) or rows != [
            ("cineforge-verify-" + identifier, expected, "RESERVED_UNRECONCILED")
        ]:
            raise StorageProbeError("SQLITE_PROBE_INTEGRITY_FAILED")
    except sqlite3.Error as exc:
        raise StorageProbeError("SQLITE_PROBE_UNREADABLE_AFTER_REBOOT") from exc
    return {
        "status": "SAME_HOST_REBOOT_SURVIVAL_OBSERVED",
        "probe_id": identifier,
        "sqlite_integrity": True,
        "separate_process_reopen": True,
        "boot_id_changed": True,
        "storage_production_certified": False,
        "backup_restore_certified": False,
        "multi_host_atomicity_certified": False,
        "platform_remote_reconciliation_certified": False,
        "production_ready": False,
        "publication_authorized": False
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CineForge isolated, reboot-bound ledger proof")
    sub = parser.add_subparsers(dest="stage", required=True)
    for stage in ("prepare", "verify"):
        p = sub.add_parser(stage)
        p.add_argument("--root", type=Path, required=True)
        if stage == "verify":
            p.add_argument("--id", required=True)
    args = parser.parse_args(argv)
    try:
        result = start(args.root) if args.stage == "prepare" else verify(args.root, args.id)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (StorageProbeError, OSError, sqlite3.Error) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc), "production_ready": False}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
