import os
import sys
import ftplib
from pathlib import Path

def upload():
    host = os.environ.get('FTP_HOST')
    user = os.environ.get('FTP_USER')
    passwd = os.environ.get('FTP_PASS')
    port = int(os.environ.get('FTP_PORT', 21))

    remote_root = "/public_html/hobby/史書/太平寰宇記"

    ftp = ftplib.FTP()
    ftp.connect(host, port, timeout=30)
    ftp.login(user, passwd)
    ftp.encoding = "utf-8"

    # Files to upload
    files_to_upload = [
        ("index.html", f"{remote_root}/index.html"),
        ("js/app.js", f"{remote_root}/js/app.js"),
        ("js/taiping_atlas_data.js", f"{remote_root}/js/taiping_atlas_data.js"),
        ("js/taiping_atlas_texts.js", f"{remote_root}/js/taiping_atlas_texts.js"),
    ]

    for local_path, remote_path in files_to_upload:
        p = Path(local_path)
        if not p.exists():
            print(f"Error: {local_path} not found")
            continue
        print(f"Uploading {local_path} -> {remote_path} ({p.stat().st_size:,} bytes)...")
        with open(p, "rb") as f:
            ftp.storbinary(f"STOR {remote_path}", f)
        print(f"Uploaded {local_path} successfully.")

    ftp.quit()
    print("All uploads completed successfully.")

if __name__ == "__main__":
    upload()

