import sys
sys.stdout.reconfigure(encoding='utf-8')
import json
import subprocess
from pathlib import Path

ROOT_DIR = Path(".")
DATA_DIR = ROOT_DIR / "data"

cache_path = DATA_DIR / "translation_cache_ja.json"
cache = json.loads(cache_path.read_text(encoding="utf-8"))

prefs_path = DATA_DIR / "taiping_huanyuji_prefectures.json"
prefs_raw = json.loads(prefs_path.read_text(encoding="utf-8"))

prefs_geo_path = DATA_DIR / "taiping_huanyuji_prefectures_geo.json"
prefs_geo = json.loads(prefs_geo_path.read_text(encoding="utf-8")) if prefs_geo_path.exists() else []

counties_path = DATA_DIR / "taiping_huanyuji_counties.json"
counties = json.loads(counties_path.read_text(encoding="utf-8"))

# prefectures_geo に prefectures.json の最新全州（389州）を同期
geo_by_id = {p["id"]: p for p in prefs_geo}
for p in prefs_raw:
    pid = p["id"]
    hist_ja = cache.get(f"pref_hist:{pid}") or p.get("history_ja", "")
    cust_ja = cache.get(f"pref_cust:{pid}") or p.get("customs_ja", "")
    if hist_ja:
        p["history_ja"] = hist_ja
    if cust_ja:
        p["customs_ja"] = cust_ja

    if pid in geo_by_id:
        gp = geo_by_id[pid]
        gp.update({k: v for k, v in p.items() if k not in ("coord", "geometry")})
    else:
        prefs_geo.append(dict(p))

prefs_path.write_text(json.dumps(prefs_raw, ensure_ascii=False, indent=2), encoding="utf-8")
prefs_geo_path.write_text(json.dumps(prefs_geo, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Applied translation cache to {len(prefs_raw)} prefectures.")

# 05_annotate_era_years.py
subprocess.run([sys.executable, "scripts/05_annotate_era_years.py"], check=True)

# 03_spatial_trilateration_and_geojson.py
subprocess.run([sys.executable, "scripts/03_spatial_trilateration_and_geojson.py"], check=True)

print("Rebuilding complete!")

