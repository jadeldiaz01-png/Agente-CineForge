#!/usr/bin/env python3
"""Read-only CineForge VPS preflight; observations NEVER certify production."""
import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess


def command_output(args):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=8)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def storage_report(directory: Path):
    d = {"path": str(directory), "exists": False, "is_directory": False,
         "is_symlink": False, "owner_only_permissions": False,
         "production_certified": False, "reboot_durability": "UNVERIFIED",
         "backup_restore": "UNVERIFIED", "multi_host_atomicity": "UNVERIFIED"}
    try:
        st = directory.lstat()
        d.update(exists=True, is_directory=stat.S_ISDIR(st.st_mode),
                 is_symlink=stat.S_ISLNK(st.st_mode),
                 owner_only_permissions=(stat.S_IMODE(st.st_mode) & 0o077) == 0,
                 permissions=oct(stat.S_IMODE(st.st_mode)), owner_uid=st.st_uid)
        if d["is_directory"] and not d["is_symlink"]:
            fs = os.statvfs(directory)
            d["available_bytes"] = fs.f_bavail * fs.f_frsize
    except OSError:
        pass
    return d


def gpu_report():
    available = bool(shutil.which("nvidia-smi"))
    result = {"nvidia_smi_available": available, "gpus": [],
              "wan22_5b_memory_candidate": False,
              "model_inference_certified": False}
    if not available:
        return result
    out = command_output(["nvidia-smi", "--query-gpu=name,memory.total",
                          "--format=csv,noheader,nounits"])
    for line in out.splitlines():
        try:
            name, memory = line.rsplit(",", 1)
            result["gpus"].append({"name": name.strip()[:100], "vram_mib": int(float(memory.strip()))})
        except (ValueError, IndexError):
            continue
    result["wan22_5b_memory_candidate"] = any(g["vram_mib"] >= 24576 for g in result["gpus"])
    return result


def report(directory: Path):
    ffmpeg = bool(shutil.which("ffmpeg"))
    ffprobe = bool(shutil.which("ffprobe"))
    return {"schema_version": 1, "mode": "READ_ONLY",
            "status": "OBSERVATIONS_NOT_CERTIFICATION", "production_ready": False,
            "storage": storage_report(directory),
            "media": {"ffmpeg_available": ffmpeg, "ffprobe_available": ffprobe},
            "gpu": gpu_report(),
            "external_evidence_missing": [
                "effective protected main ruleset",
                "service identity and persistent volume proof",
                "backup and reboot restore test",
                "platform consent, permissions and app reviews",
                "signed end-to-end sandbox post and remote status proof",
                "licensed GPU video generation and blind comparison"
            ]}


def main():
    parser = argparse.ArgumentParser(description="CineForge read-only VPS inventory")
    parser.add_argument("--ledger-dir", type=Path, default=Path("/var/lib/cineforge"))
    args = parser.parse_args()
    if not args.ledger_dir.is_absolute():
        parser.error("absolute --ledger-dir required")
    print(json.dumps(report(args.ledger_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
