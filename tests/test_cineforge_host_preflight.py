import json
from pathlib import Path
import subprocess
import sys

PROBE = Path(__file__).resolve().parents[1] / "scripts" / "cineforge_host_preflight_readonly.py"


def run_preflight(path):
    r = subprocess.run([sys.executable, str(PROBE), "--ledger-dir", str(path)],
                       check=True, capture_output=True, text=True, timeout=15)
    return json.loads(r.stdout)


def test_missing_storage_remains_blocked(tmp_path):
    d = run_preflight(tmp_path / "absent")
    assert d["mode"] == "READ_ONLY" and not d["production_ready"]
    assert not d["storage"]["exists"] and not d["storage"]["production_certified"]


def test_existing_private_folder_is_not_proof_of_persistence(tmp_path):
    folder = tmp_path / "private"
    folder.mkdir(mode=0o700)
    d = run_preflight(folder)
    assert d["storage"]["exists"] and d["storage"]["owner_only_permissions"]
    assert d["storage"]["reboot_durability"] == "UNVERIFIED"
    assert not d["storage"]["production_certified"]


def test_world_writable_and_symlink_never_certify(tmp_path):
    exposed = tmp_path / "exposed"
    exposed.mkdir()
    exposed.chmod(0o777)
    d = run_preflight(exposed)
    assert not d["storage"]["owner_only_permissions"]
    link = tmp_path / "link"
    link.symlink_to(exposed, target_is_directory=True)
    d = run_preflight(link)
    assert d["storage"]["is_symlink"] and not d["storage"]["production_certified"]
    assert list(exposed.iterdir()) == []
