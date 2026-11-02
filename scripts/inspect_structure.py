#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "原文"
SKCHAR_PATH = Path(__file__).resolve().parent / "skchars.json"

if not SKCHAR_PATH.exists():
    url = (
        "https://zh.wikisource.org/w/index.php?title="
        + urllib.parse.quote("Module:SKchar")
        + "&action=raw"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    lua_txt = urllib.request.urlopen(req, timeout=15).read().decode("utf-8")
    sk_map = {}
    for m in re.finditer(r"\['(\d+)'\]\s*=\s*\{([^}]+)\}", lua_txt):
        code = m.group(1)
        body = m.group(2)
        strs = re.findall(r'"([^"]+)"', body)
        if strs:
            sk_map[code] = strs[0]
    # Readability overrides for taboo/archaic variants in Siku Quanshu
    overrides = {
        "3800": "開",
        "2592": "弘",
        "1452": "隸",
        "3892": "類",
        "2862": "心",
        "3307": "括",
    }
    sk_map.update(overrides)
    SKCHAR_PATH.write_text(json.dumps(sk_map, ensure_ascii=False, indent=2), encoding="utf-8")
else:
    sk_map = json.loads(SKCHAR_PATH.read_text(encoding="utf-8"))

print(f"Loaded {len(sk_map)} SKchar mappings.")

# Let's check Dao anchors and Prefecture lines across all volumes
dao_summary = []
for fpath in sorted(RAW_DIR.glob("卷*.txt")):
    txt = fpath.read_text(encoding="utf-8")
    anchors = re.findall(r"\{\{SK anchor\|([^}]+)\}\}", txt)
    dao_anchors = [
        a
        for a in anchors
        if any(k in a for k in ["道", "四夷", "東夷", "南蠻", "西戎", "北狄"])
    ]
    dao_summary.append((fpath.stem, dao_anchors, anchors[:8]))

for stem, daos, first_anchors in dao_summary[:40]:
    print(f"{stem}: daos={daos} | anchors={first_anchors}")
print("...")
for stem, daos, first_anchors in dao_summary[165:]:
    print(f"{stem}: daos={daos} | anchors={first_anchors}")

