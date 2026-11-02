# -*- coding: utf-8 -*-
"""
FTP Upload script for 太平寰宇記 (Taiping Huanyuji Interactive Historical Atlas)
Target: ftp://ftp.aki-asahi.com/public_html/hobby/史書/太平寰宇記
"""

import os
import sys
import ftplib
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
REMOTE_BASE = "/public_html/hobby/史書/太平寰宇記"


def ensure_remote_dir(ftp: ftplib.FTP, remote_path: str):
    parts = [p for p in remote_path.strip("/").split("/") if p]
    curr = ""
    for p in parts:
        curr += "/" + p
        try:
            ftp.cwd(curr)
        except ftplib.error_perm:
            try:
                ftp.mkd(curr)
            except Exception as e:
                print(f"  [WARN] mkd {curr}: {e}")
            ftp.cwd(curr)


def upload_file(ftp: ftplib.FTP, local_file: Path, remote_dir: str):
    ftp.cwd(remote_dir)
    size_kb = local_file.stat().st_size / 1024.0
    print(f"  Uploading {local_file.name} ({size_kb:.1f} KB) -> {remote_dir}/{local_file.name}")
    with open(local_file, "rb") as f:
        ftp.storbinary(f"STOR {local_file.name}", f)


def main():
    host = os.environ.get("FTP_HOST")
    user = os.environ.get("FTP_USER")
    passwd = os.environ.get("FTP_PASS")
    port = int(os.environ.get("FTP_PORT", "21"))

    if not all([host, user, passwd]):
        print("Error: FTP_HOST, FTP_USER, or FTP_PASS is missing from environment variables.")
        sys.exit(1)

    print(f"Connecting to {host}:{port}...")
    ftp = ftplib.FTP()
    ftp.encoding = "utf-8"
    ftp.connect(host, port, timeout=60)
    ftp.login(user, passwd)
    print(f"Logged in. Server welcome: {ftp.getwelcome()}")

    ensure_remote_dir(ftp, REMOTE_BASE)

    # 1. Root index.html
    upload_file(ftp, ROOT_DIR / "index.html", REMOTE_BASE)

    # 2. Directories required by the web app & links in index.html
    # (Skip unused 17MB terrain_relief.png if terrain_relief.webp is present, and skip internal temp reference_geo.json)
    SKIP_FILES = {"terrain_relief.png", "reference_geo.json", "translation_cache_ja.json"}

    target_subdirs = [
        "css",
        "js",
        "assets",
        "geojson",
        "data",
        "notebooks",
        "scripts",
    ]

    total_files = 1
    total_bytes = (ROOT_DIR / "index.html").stat().st_size

    for subdir in target_subdirs:
        local_sub = ROOT_DIR / subdir
        if not local_sub.exists():
            continue
        remote_sub = f"{REMOTE_BASE}/{subdir}"
        ensure_remote_dir(ftp, remote_sub)
        for item in sorted(local_sub.iterdir()):
            if item.is_file():
                if item.name in SKIP_FILES:
                    print(f"  [SKIP] {item.name} (unused intermediate/raw file)")
                    continue
                upload_file(ftp, item, remote_sub)
                total_files += 1
                total_bytes += item.stat().st_size

    ftp.quit()
    print(f"\nFTP Upload Complete! Uploaded {total_files} files ({total_bytes / (1024*1024):.2f} MB) to {REMOTE_BASE}")


if __name__ == "__main__":
    main()

