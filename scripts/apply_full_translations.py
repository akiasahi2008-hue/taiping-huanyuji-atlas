import sys
sys.stdout.reconfigure(encoding='utf-8')
import json
import re
import subprocess
from pathlib import Path

ROOT_DIR = Path(".")
DATA_DIR = ROOT_DIR / "data"

# 1. Load Caches and Manual mappings
cache = json.loads((DATA_DIR / "translation_cache_ja.json").read_text(encoding="utf-8"))

# Load County Manual
from manual_county_ja import COUNTY_JA_MANUAL

# Load Recovered Landmark Cache from Git history
print("Recovering landmark cache from git history...")
try:
    old_json_str = subprocess.check_output(
        ["git", "show", "4f32788:data/taiping_huanyuji_landmarks.json"],
        text=True, encoding="utf-8"
    )
    old_lms = json.loads(old_json_str)
except Exception as e:
    print(f"Error reading old landmarks: {e}")
    old_lms = []

lm_recovered_by_desc = {}
lm_recovered_by_name = {}
for idx, lm in enumerate(old_lms):
    k = f"lm_desc:{idx}"
    if k in cache:
        ja = cache[k]
        desc = lm.get("desc", "").strip()
        cname = lm.get("county", "").strip()
        pname = lm.get("prefecture", "").strip()
        lmname = lm.get("name", "").strip()
        if desc:
            lm_recovered_by_desc[desc] = ja
        lm_recovered_by_name[(pname, cname, lmname)] = ja

print(f"Recovered {len(lm_recovered_by_desc)} landmark translations from cache.")

# Siyi cache by name
siyi_cache_hist = {}
siyi_cache_cust = {}
siyi_cache_sizhi = {}
for k, v in cache.items():
    if k.startswith("siyi_hist:"):
        parts = k.split(":", 2)
        if len(parts) >= 3:
            siyi_cache_hist[parts[2]] = v
    elif k.startswith("siyi_cust:"):
        parts = k.split(":", 2)
        if len(parts) >= 3:
            siyi_cache_cust[parts[2]] = v
    elif k.startswith("siyi_sizhi:"):
        parts = k.split(":", 2)
        if len(parts) >= 3:
            siyi_cache_sizhi[parts[2]] = v

# County cache by pref_county or county
cnty_cache = {}
for k, v in cache.items():
    if k.startswith("cnty_intro:"):
        parts = k.split(":", 2)
        if len(parts) >= 3:
            pref_c = parts[2]
            cnty_cache[pref_c] = v
            if "_" in pref_c:
                cnty_cache[pref_c.split("_")[1]] = v

# Classical Chinese to Japanese rule engine for missing entries
import importlib.util
spec = importlib.util.spec_from_file_location("trans_mod", "scripts/04_translate_to_japanese.py")
trans_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trans_mod)

def translate_landmark_enhanced(lm: dict) -> str:
    desc = lm.get("desc", "").strip()
    name = lm.get("name", "").strip()
    county = lm.get("county", "").strip()
    pref = lm.get("prefecture", "").strip()
    cat = lm.get("category", "古跡")
    dir_str = lm.get("direction", "")
    li = lm.get("distance_li")

    if not desc:
        loc = f"県の{dir_str}{li}里" if (dir_str and li) else f"{pref}{county}域内"
        return f"【{cat}】{name}は{loc}に位置する。"

    s = desc
    if s.startswith(name):
        s = s[len(name):].strip()

    loc_header = ""
    m_loc = re.match(r"^在(?:縣|州|城|府|軍)?(東南|東北|西南|西北|東|西|南|北)?([一二三四五六七八九十百千〇零]+里|郭下|城内|城外)?", s)
    if m_loc and m_loc.group(0):
        d_str = m_loc.group(1) or ""
        l_str = m_loc.group(2) or ""
        if l_str in ("郭下", "城内"):
            loc_header = f"{name}は県の城内（郭下）にある。"
        elif d_str and l_str:
            loc_header = f"{name}は県の{d_str}{l_str}にある。"
        elif d_str:
            loc_header = f"{name}は県の{d_str}にある。"
        s = s[len(m_loc.group(0)):].strip()
    elif dir_str and li:
        loc_header = f"{name}は県の{dir_str}{li}里にある。"
    else:
        loc_header = f"{name}は{pref}{county}にある{cat}。"

    if not s:
        return loc_header

    # Enhanced translation phrases
    s = trans_mod.translate_classical_clauses(s)
    # Further clean up Classical markers
    s = re.sub(r"有([^\s。、]{1,10}山)", r"\1があり、", s)
    s = re.sub(r"有([^\s。、]{1,10}水)", r"\1が流れ、", s)
    s = re.sub(r"出銀鉛鑛砂", r"銀や鉛の鉱砂を産出する。", s)
    s = re.sub(r"出茶", r"茶を産出する。", s)
    s = re.sub(r"皆郡界之山水", r"いずれも郡境の山水である。", s)
    s = re.sub(r"上有自然石室", r"山上に自然の石室があり、", s)
    s = re.sub(r"有石室戶牖", r"自然の石室や戸口・窓があり、", s)
    s = re.sub(r"上有青玉壇", r"上には青玉壇がある。", s)
    s = re.sub(r"屈原所溺処", r"屈原が身を投げて溺死した地である。", s)

    return f"{loc_header}{s}"


# =========================================================================
# 2. Update Counties (taiping_huanyuji_counties.json)
# =========================================================================
print("\nUpdating counties...")
counties_path = DATA_DIR / "taiping_huanyuji_counties.json"
counties = json.loads(counties_path.read_text(encoding="utf-8"))

for c in counties:
    pref_c = f"{c['prefecture']}_{c['name']}"
    cname = c["name"]
    cname_no_x = cname.replace("縣", "")

    # Priority 1: Manual translation
    if pref_c in COUNTY_JA_MANUAL:
        c["intro_ja"] = COUNTY_JA_MANUAL[pref_c]
    # Priority 2: Cache match
    elif pref_c in cnty_cache:
        c["intro_ja"] = cnty_cache[pref_c]
    elif cname in cnty_cache:
        c["intro_ja"] = cnty_cache[cname]
    elif f"{c['prefecture']}_{cname_no_x}" in cnty_cache:
        c["intro_ja"] = cnty_cache[f"{c['prefecture']}_{cname_no_x}"]
    elif cname_no_x in cnty_cache:
        c["intro_ja"] = cnty_cache[cname_no_x]
    # Priority 3: Rule engine fallback
    else:
        raw_intro = c.get("intro", "")
        if raw_intro:
            c["intro_ja"] = trans_mod.translate_classical_clauses(raw_intro)
        else:
            c["intro_ja"] = f"{c['prefecture']}管轄の県。"

counties_path.write_text(json.dumps(counties, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Updated {len(counties)} counties with Japanese translations!")


# =========================================================================
# 3. Update Landmarks (taiping_huanyuji_landmarks.json)
# =========================================================================
print("\nUpdating landmarks...")
landmarks_path = DATA_DIR / "taiping_huanyuji_landmarks.json"
landmarks = json.loads(landmarks_path.read_text(encoding="utf-8"))

matched_lm_count = 0
generated_lm_count = 0
for lm in landmarks:
    desc = lm.get("desc", "").strip()
    key_name = (lm.get("prefecture", "").strip(), lm.get("county", "").strip(), lm.get("name", "").strip())

    ja = lm_recovered_by_desc.get(desc) or lm_recovered_by_name.get(key_name)
    if ja:
        lm["desc_ja"] = ja
        matched_lm_count += 1
    else:
        lm["desc_ja"] = translate_landmark_enhanced(lm)
        generated_lm_count += 1

landmarks_path.write_text(json.dumps(landmarks, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Updated {len(landmarks)} landmarks! (Recovered: {matched_lm_count}, Generated: {generated_lm_count})")


# =========================================================================
# 4. Update Si-Yi States (taiping_huanyuji_siyi.json)
# =========================================================================
print("\nUpdating Si-Yi states...")
siyi_path = DATA_DIR / "taiping_huanyuji_siyi.json"
siyi = json.loads(siyi_path.read_text(encoding="utf-8"))

for s in siyi:
    sname = s["name"]
    # history_ja
    if sname in siyi_cache_hist:
        s["history_ja"] = siyi_cache_hist[sname]
    elif s.get("history"):
        s["history_ja"] = trans_mod.translate_classical_clauses(s["history"])

    # customs_ja
    if sname in siyi_cache_cust:
        s["customs_ja"] = siyi_cache_cust[sname]
    elif s.get("customs"):
        s["customs_ja"] = trans_mod.translate_classical_clauses(s["customs"])

    # sizhi_ja
    if sname in siyi_cache_sizhi:
        s["sizhi_ja"] = siyi_cache_sizhi[sname]
    elif s.get("sizhi"):
        s["sizhi_ja"] = trans_mod.translate_classical_clauses(s["sizhi"])

siyi_path.write_text(json.dumps(siyi, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Updated {len(siyi)} Si-Yi states with Japanese translations!")


# =========================================================================
# 5. Annotate Era Years (scripts/05_annotate_era_years.py)
# =========================================================================
print("\nAnnotating era years with Western calendar...")
subprocess.run([sys.executable, "scripts/05_annotate_era_years.py"], check=True)


# =========================================================================
# 6. Rebuild GeoJSON and Text Bundles (scripts/03_spatial_trilateration_and_geojson.py)
# =========================================================================
print("\nRebuilding js/taiping_atlas_data.js and js/taiping_atlas_texts.js...")
subprocess.run([sys.executable, "scripts/03_spatial_trilateration_and_geojson.py"], check=True)

print("\nAll translations successfully applied and rebuilt!")
