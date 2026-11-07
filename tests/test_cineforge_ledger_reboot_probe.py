"""Reboot proof stays partial and isolated; CI uses simulated boot IDs, never claims host evidence."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "cineforge_ledger_reboot_probe.py"
spec = importlib.util.spec_from_file_location("cineforge_reboot_probe", SCRIPT)
probe = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(probe)


def private_root(tmp_path: Path) -> Path:
    root = tmp_path / "isolated-ledger-probe"
    root.mkdir(mode=0o700)
    return root


def test_probe_rejects_same_boot_and_never_certifies_production(monkeypatch, tmp_path):
    root = private_root(tmp_path)
    monkeypatch.setattr(probe, "boot_id", lambda: "a" * 36)
    prep = probe.start(root)
    assert prep["status"] == "PREPARED_FOR_REBOOT"
    assert prep["production_ready"] is False
    assert prep["publication_authorized"] is False
    with pytest.raises(probe.StorageProbeError, match="REBOOT_NOT_INDEPENDENTLY_OBSERVED"):
        probe.verify(root, prep["probe_id"])
    # Simulated boot change validates code only. This is NEVER real reboot proof.
    monkeypatch.setattr(probe, "boot_id", lambda: "b" * 36)
    result = probe.verify(root, prep["probe_id"])
    assert result["status"] == "SAME_HOST_REBOOT_SURVIVAL_OBSERVED"
    assert result["production_ready"] is False
    assert result["storage_production_certified"] is False
    assert result["backup_restore_certified"] is False
    assert result["multi_host_atomicity_certified"] is False
    assert result["platform_remote_reconciliation_certified"] is False
    assert result["publication_authorized"] is False
    db, receipt = probe.names(root, prep["probe_id"])
    assert db.stat().st_mode & 0o077 == 0
    assert receipt.stat().st_mode & 0o077 == 0


def test_missing_receipt_blocks_and_no_live_ledger_written(tmp_path, monkeypatch):
    root = private_root(tmp_path)
    monkeypatch.setattr(probe, "boot_id", lambda: "a" * 36)
    with pytest.raises(probe.StorageProbeError, match="PERSISTED_PROBE_NOT_FOUND"):
        probe.verify(root, "0" * 32)
    assert list(root.iterdir()) == []


def test_invalid_root_permissions_never_write(tmp_path, monkeypatch):
    root = tmp_path / "public"
    root.mkdir(mode=0o700)
    root.chmod(0o777)
    monkeypatch.setattr(probe, "boot_id", lambda: "a" * 36)
    with pytest.raises(probe.StorageProbeError, match="PRIVATE_PROBE_DIRECTORY_REQUIRED"):
        probe.start(root)
    assert list(root.iterdir()) == []


def test_symlink_and_traversal_rejected(tmp_path, monkeypatch):
    root = private_root(tmp_path)
    alias = tmp_path / "link"
    alias.symlink_to(root, target_is_directory=True)
    monkeypatch.setattr(probe, "boot_id", lambda: "a" * 36)
    with pytest.raises(probe.StorageProbeError, match="SYMLINK_PARENT_FORBIDDEN"):
        probe.start(alias)
    with pytest.raises(probe.StorageProbeError, match="TRAVERSAL_FORBIDDEN"):
        probe.start(root / ".." / "isolated-ledger-probe")
    assert list(root.iterdir()) == []


def test_receipt_tampering_fail_closed(tmp_path, monkeypatch):
    root = private_root(tmp_path)
    monkeypatch.setattr(probe, "boot_id", lambda: "a" * 36)
    prepared = probe.start(root)
    db, path = probe.names(root, prepared["probe_id"])
    receipt = json.loads(path.read_text(encoding="utf-8"))
    receipt["intent_sha256"] = "f" * 64
    path.write_text(json.dumps(receipt), encoding="utf-8")
    path.chmod(0o600)
    monkeypatch.setattr(probe, "boot_id", lambda: "b" * 36)
    with pytest.raises(probe.StorageProbeError, match="PROBE_INTENT_DIGEST_INVALID"):
        probe.verify(root, prepared["probe_id"])


def test_cli_invalid_identifier_is_blocked_without_writes(tmp_path):
    root = private_root(tmp_path)
    result = probe.main(["verify", "--root", str(root), "--id", "../ledger"])
    assert result == 2
    assert list(root.iterdir()) == []
