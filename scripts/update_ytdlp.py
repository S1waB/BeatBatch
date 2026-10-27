#!/usr/bin/env python3
"""
BeatBatch - yt-dlp Upgrade Utility

Why is this necessary?
----------------------
YouTube frequently changes its internal player APIs, obfuscation algorithms,
n-signature tokens, and anti-bot validation logic. When YouTube updates their
infrastructure, existing yt-dlp versions may fail with HTTP 403 Forbidden,
'Sign in to confirm you're not a bot', or extraction errors.

Running this script upgrades yt-dlp to the latest upstream release.
"""

import sys
import subprocess
import re
from pathlib import Path

def get_installed_ytdlp_version():
    """Retrieve the currently installed yt-dlp version."""
    try:
        import yt_dlp.version
        return yt_dlp.version.__version__
    except ImportError:
        return None

def upgrade_ytdlp():
    print("=" * 60)
    print("           BeatBatch - yt-dlp Auto-Upgrader")
    print("=" * 60)
    print("YouTube frequently adjusts signature ciphers and streaming APIs.")
    print("Keeping yt-dlp updated prevents extraction and 403 errors.\n")

    current_ver = get_installed_ytdlp_version()
    if current_ver:
        print(f"[*] Current yt-dlp version: {current_ver}")
    else:
        print("[!] yt-dlp is not currently installed in this environment.")

    print(f"[*] Upgrading yt-dlp using interpreter: {sys.executable} ...")
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"]

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("[+] pip output:")
        for line in result.stdout.strip().splitlines()[-5:]:
            print(f"    {line}")
    except subprocess.CalledProcessError as exc:
        print(f"[-] Upgrade failed with exit code {exc.returncode}:")
        print(exc.stderr)
        sys.exit(1)

    # Re-check updated version via a fresh subprocess to bypass module cache
    try:
        ver_check = subprocess.run(
            [sys.executable, "-c", "import yt_dlp.version; print(yt_dlp.version.__version__)"],
            check=True,
            capture_output=True,
            text=True
        )
        new_ver = ver_check.stdout.strip()
        print(f"\n[OK] Upgrade successful! New yt-dlp version: {new_ver}")
    except Exception as exc:
        print(f"[!] Could not verify new version: {exc}")
        new_ver = None

    # Check if backend/requirements.txt exists and sync it
    repo_root = Path(__file__).resolve().parent.parent
    req_file = repo_root / "backend" / "requirements.txt"
    if req_file.exists() and new_ver:
        try:
            content = req_file.read_text(encoding="utf-8")
            if re.search(r"yt-dlp[=>~]+[\w\.]+", content):
                new_content = re.sub(r"yt-dlp[=>~]+[\w\.]+", f"yt-dlp>={new_ver}", content)
                req_file.write_text(new_content, encoding="utf-8")
                print(f"[OK] Updated {req_file.name} to yt-dlp>={new_ver}")
        except Exception as e:
            print(f"[!] Note: Could not update requirements.txt automatically: {e}")

    print("\n[i] If running the backend service, restart it now to load the new version.")
    print("=" * 60)

if __name__ == "__main__":
    upgrade_ytdlp()
