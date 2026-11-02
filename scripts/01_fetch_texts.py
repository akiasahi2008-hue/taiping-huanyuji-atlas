#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wikisource から『太平寰宇記 (四庫全書本)』の全巻（序 + 巻001〜巻200、巻172上下含む）を
MediaWiki API 経由で一括取得し、原文/ フォルダに保存するスクリプト。
"""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "原文"
RAW_DIR.mkdir(parents=True, exist_ok=True)

API_URL = "https://zh.wikisource.org/w/api.php"
BOOK_PREFIX = "太平寰宇記 (四庫全書本)"


def get_page_list() -> list[tuple[str, str]]:
    """取得対象となる (サブページ名, 保存ファイル名) のリストを返す。"""
    pages = [("", "序.txt")]
    for i in range(1, 201):
        if i == 172:
            pages.append(("卷172上", "卷172上.txt"))
            pages.append(("卷172下", "卷172下.txt"))
        else:
            pages.append((f"卷{i:03d}", f"卷{i:03d}.txt"))
    return pages


def fetch_batch(titles: list[str]) -> dict[str, str]:
    """最大50件のページタイトルを MediaWiki API で一括取得する。"""
    params = {
        "action": "query",
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "format": "json",
        "titles": "|".join(titles),
    }
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "User-Agent": "TaipingHuanyujiGIS/1.0 (Historical Atlas Research; Python urllib)"
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        res = json.loads(resp.read().decode("utf-8"))

    out = {}
    pages = res.get("query", {}).get("pages", {})
    for pid, pdata in pages.items():
        if int(pid) < 0:
            continue
        title = pdata.get("title", "")
        revs = pdata.get("revisions", [])
        if revs:
            slots = revs[0].get("slots", {})
            content = slots.get("main", {}).get("*", "")
            if not content and "*" in revs[0]:
                content = revs[0]["*"]
            out[title] = content
    return out


def main():
    pages = get_page_list()
    to_fetch = []
    for sub, fname in pages:
        fpath = RAW_DIR / fname
        if fpath.exists() and fpath.stat().st_size > 100:
            continue
        full_title = f"{BOOK_PREFIX}/{sub}" if sub else BOOK_PREFIX
        to_fetch.append((full_title, fname))

    print(f"Total pages: {len(pages)}, need to fetch: {len(to_fetch)}")
    batch_size = 40
    fetched_count = 0

    for i in range(0, len(to_fetch), batch_size):
        batch = to_fetch[i : i + batch_size]
        titles = [t[0] for t in batch]
        print(f"Fetching batch {i // batch_size + 1} ({len(titles)} pages)...")
        results = fetch_batch(titles)
        for full_title, fname in batch:
            content = results.get(full_title, "")
            if content:
                (RAW_DIR / fname).write_text(content, encoding="utf-8")
                fetched_count += 1
            else:
                print(f"  [WARN] Missing or empty: {full_title}")
        time.sleep(0.5)

    existing = list(RAW_DIR.glob("*.txt"))
    print(f"Done! Newly fetched: {fetched_count}, Total files in 原文/: {len(existing)}")


if __name__ == "__main__":
    main()

