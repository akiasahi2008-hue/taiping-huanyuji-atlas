import os
import sys
import ftplib
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

def upload():
    host = os.environ.get('FTP_HOST')
    user = os.environ.get('FTP_USER')
    passwd = os.environ.get('FTP_PASS')
    port = int(os.environ.get('FTP_PORT', 21))

    if not all([host, user, passwd]):
        print("Error: FTP_HOST, FTP_USER, or FTP_PASS is missing.", flush=True)
        sys.exit(1)

    remote_root = "/public_html/hobby/史書/太平寰宇記"

    print(f"Connecting to {host}:{port}...", flush=True)
    ftp = ftplib.FTP()
    ftp.connect(host, port, timeout=60)
    ftp.login(user, passwd)
    ftp.encoding = "utf-8"
    ftp.set_pasv(True)
    print("Logged in successfully.", flush=True)

    files_to_upload = [
        ("index.html", f"{remote_root}/index.html"),
        ("js/app.js", f"{remote_root}/js/app.js"),
        ("js/taiping_atlas_data.js", f"{remote_root}/js/taiping_atlas_data.js"),
        ("js/taiping_atlas_texts.js", f"{remote_root}/js/taiping_atlas_texts.js"),
        ("data/taiping_huanyuji_distances.json", f"{remote_root}/data/taiping_huanyuji_distances.json"),
        ("data/taiping_huanyuji_distances.csv", f"{remote_root}/data/taiping_huanyuji_distances.csv"),
        ("data/taiping_huanyuji_prefectures.json", f"{remote_root}/data/taiping_huanyuji_prefectures.json"),
        ("data/taiping_huanyuji_prefectures_geo.json", f"{remote_root}/data/taiping_huanyuji_prefectures_geo.json"),
        ("geojson/distance_network.geojson", f"{remote_root}/geojson/distance_network.geojson"),
        ("geojson/prefectures.geojson", f"{remote_root}/geojson/prefectures.geojson"),
        ("原文/卷142.txt", f"{remote_root}/原文/卷142.txt"),
        ("原文/卷145.txt", f"{remote_root}/原文/卷145.txt"),
    ]

    total_files = len(files_to_upload)
    for idx, (local_path, remote_path) in enumerate(files_to_upload, 1):
        p = Path(local_path)
        if not p.exists():
            print(f"[{idx}/{total_files}] SKIP (not found): {local_path}", flush=True)
            continue
        size_kb = p.stat().st_size / 1024.0
        print(f"[{idx}/{total_files}] Uploading {local_path} ({size_kb:.1f} KB)...", end=" ", flush=True)
        with open(p, "rb") as f:
            ftp.storbinary(f"STOR {remote_path}", f)
        print("OK", flush=True)

    ftp.quit()
    print("\nAll files uploaded successfully!", flush=True)

if __name__ == "__main__":
    upload()
