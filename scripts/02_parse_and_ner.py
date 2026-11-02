#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 2: 『太平寰宇記』全200巻のテキスト構造化・固有表現抽出（NER）スクリプト（高精度版）
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "原文"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

SKCHAR_PATH = Path(__file__).resolve().parent / "skchars.json"
SK_MAP = (
    json.loads(SKCHAR_PATH.read_text(encoding="utf-8"))
    if SKCHAR_PATH.exists()
    else {}
)


def get_dao_by_vol(vol_num: int, sub: str = "") -> tuple[str, str]:
    """(道ID, 道名) を返す"""
    if 1 <= vol_num <= 24:
        return ("henan", "河南道")
    if 25 <= vol_num <= 39:
        return ("guanxi", "關西道")
    if 40 <= vol_num <= 51:
        return ("hedong", "河東道")
    if 52 <= vol_num <= 71:
        return ("hebei", "河北道")
    if 72 <= vol_num <= 81:
        return ("jiannan_w", "劍南西道")
    if 82 <= vol_num <= 88:
        return ("jiannan_e", "劍南東道")
    if 89 <= vol_num <= 102:
        return ("jiangnan_e", "江南東道")
    if 103 <= vol_num <= 122:
        return ("jiangnan_w", "江南西道")
    if 123 <= vol_num <= 132:
        return ("huainan", "淮南道")
    if 133 <= vol_num <= 141:
        return ("shannan_w", "山南西道")
    if 142 <= vol_num <= 149:
        return ("shannan_e", "山南東道")
    if 150 <= vol_num <= 156:
        return ("longyou", "隴右道")
    if 157 <= vol_num <= 171:
        return ("lingnan", "嶺南道")
    if 172 <= vol_num <= 175:
        return ("siyi_dongyi", "四夷・東夷")
    if 176 <= vol_num <= 179:
        return ("siyi_nanman", "四夷・南蠻")
    if 180 <= vol_num <= 188:
        return ("siyi_xirong", "四夷・西戎")
    return ("siyi_beidi", "四夷・北狄")


CN_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "兩": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
CN_UNITS = {"十": 10, "百": 100, "千": 1000, "萬": 10000}


def parse_cn_num(s: str) -> int | None:
    if not s:
        return None
    s = s.strip()
    if s.isdigit():
        return int(s)

    def _parse_under_wan(part: str) -> int:
        total = 0
        curr = 0
        for ch in part:
            if ch in CN_DIGITS:
                curr = CN_DIGITS[ch]
            elif ch in CN_UNITS and ch != "萬":
                unit = CN_UNITS[ch]
                if curr == 0:
                    curr = 1
                total += curr * unit
                curr = 0
        total += curr
        return total

    if "萬" in s:
        wan_part, rem_part = s.split("萬", 1)
        wan_val = _parse_under_wan(wan_part) if wan_part else 1
        rem_val = _parse_under_wan(rem_part) if rem_part else 0
        return wan_val * 10000 + rem_val
    val = _parse_under_wan(s)
    return val if val > 0 else None


def clean_wiki_text(raw: str) -> str:
    def _repl_skchar(m):
        code = m.group(1)
        return SK_MAP.get(code, "")

    s = re.sub(r"\{\{SKchar\|(\d+)(?:\|[^}]*)?\}\}", _repl_skchar, raw)
    s = re.sub(r"\{\{YL\|([^}]+)\}\}", r"\1", s)
    s = re.sub(r"\{\{SK notes\|註\}\}", "", s)
    s = re.sub(r"\{\{SK notes\|([^}]+)\}\}", r"（\1）", s)
    return s


VARIANT_NORM = str.maketrans(
    {
        "陜": "陝",
        "闗": "關",
        "劒": "劍",
        "劔": "劍",
        "宻": "密",
        "鳯": "鳳",
        "冨": "富",
        "寜": "寧",
        "頴": "潁",
        "蘓": "蘇",
        "亷": "廉",
        "眞": "真",
        "髙": "高",
        "兖": "兗",
        "户": "戶",
        "戸": "戶",
        "羙": "美",
        "夀": "壽",
        "熈": "熙",
        "㑹": "會",
        "㳂": "沿",
        "厯": "歷",
        "隂": "陰",
        "鄊": "鄉",
        "邱": "丘",
        "䕶": "護",
        "綘": "絳",
        "寳": "寶",
        "𡊮": "袁",
        "𤓰": "瓜",
        "䝉": "蒙",
        "寕": "寧",
        "懐": "懷",
        "籐": "藤",
        "𤣥": "玄",
        "𡰥": "崇",
        "賔": "賓",
        "𠑽": "獎",
        "桞": "柳",
        "逺": "遠",
        "徳": "德",
    }
)


def norm_name(s: str) -> str:
    return s.translate(VARIANT_NORM).strip()


DIR_AZIMUTH = {
    "東": 90.0,
    "正東": 90.0,
    "西": 270.0,
    "正西": 270.0,
    "南": 180.0,
    "正南": 180.0,
    "北": 0.0,
    "正北": 0.0,
    "東南": 135.0,
    "東北": 45.0,
    "西南": 225.0,
    "西北": 315.0,
    "正東微北": 75.0,
    "正東微南": 105.0,
    "正西微北": 285.0,
    "正西微南": 255.0,
    "正南微東": 165.0,
    "正南微西": 195.0,
    "正北微東": 15.0,
    "正北微西": 345.0,
}

CLASSICAL_SOURCES = [
    "史記",
    "漢書",
    "後漢書",
    "三國志",
    "晉書",
    "宋書",
    "南齊書",
    "梁書",
    "陳書",
    "魏書",
    "北齊書",
    "周書",
    "隋書",
    "唐書",
    "水經注",
    "水經",
    "括地志",
    "元和郡縣志",
    "十道志",
    "十道記",
    "輿地志",
    "輿地記",
    "寰宇記",
    "左傳",
    "春秋",
    "爾雅",
    "山海經",
    "禹貢",
    "周禮",
    "毛詩",
    "戰國策",
    "九州要記",
    "帝王世紀",
    "風俗通",
    "述異記",
    "搜神記",
    "荊州記",
    "華陽國志",
    "三秦記",
    "關中記",
    "齊記",
    "郡國志",
    "舊圖經",
    "圖經",
]


def classify_landmark(name: str, desc: str) -> str:
    if any(
        name.endswith(k)
        for k in ["山", "嶺", "峰", "峯", "巖", "岩", "岡", "坂", "坡", "谷", "洞", "穴", "原", "石", "崖", "障"]
    ):
        return "山岳"
    if any(
        name.endswith(k)
        for k in ["水", "河", "江", "川", "溪", "谿", "澗", "渠", "溝", "池", "湖", "澤", "沢", "陂", "潭", "泉", "井", "津", "渡", "浦", "洲", "海", "湾"]
    ):
        return "水系"
    if any(name.endswith(k) for k in ["城", "壘", "壁", "砦", "寨", "鎮", "戍", "柵"]):
        return "故城"
    if any(name.endswith(k) for k in ["關", "関", "塞", "隘", "門", "橋"]):
        return "関津"
    if any(name.endswith(k) for k in ["墓", "塚", "冢", "陵", "墳"]):
        return "陵墓"
    if any(name.endswith(k) for k in ["廟", "祠", "寺", "觀", "観", "宮", "壇"]):
        return "祠廟"
    if any(name.endswith(k) for k in ["臺", "台", "樓", "楼", "亭", "閣", "館", "堂", "園", "苑", "堤", "隄"]):
        return "亭台"
    if "山" in name:
        return "山岳"
    if "水" in name or "河" in name or "池" in name:
        return "水系"
    if "城" in name:
        return "故城"
    return "古跡"


def extract_distances(text: str, source_pref: str, vol_id: str, dao_name: str) -> list[dict]:
    edges = []
    clean = re.sub(r"\{\{[^}]+\}\}", "", text)
    pat = re.compile(
        r"(正?[東西南北]{1,2}(?:微[東西南北])?)"
        r"(?:[至到]|取[^至到\s　]{1,10}[至到])"
        r"([^\s　一二三四五六七八九十百千萬兩0-9]{1,14}?)"
        r"(?:水路|陸路|沂沿相兼|沿沂相兼|水陸相兼)*"
        r"([一二三四五六七八九十百千萬兩]+)\s*里"
    )
    for m in pat.finditer(clean):
        direction = m.group(1)
        raw_target = m.group(2).strip()
        li_str = m.group(3)
        li_val = parse_cn_num(li_str)
        if not li_val or li_val <= 0 or li_val > 30000:
            continue

        target_clean = re.sub(r"(?:界|水路.*|陸路.*|自.*|取.*)$", "", raw_target)
        m_pref = re.match(
            r"^(東京|西京|長安|上都|東都|河南府|開封府|大名府|京兆府|鳳翔府|江陵府|成都府|興元府|太原府|河中府|應天府|[^\s縣界]{1,4}(?:州|府|軍|監|國|郡|鎮|城|海))",
            target_clean,
        )
        target_pref = norm_name(m_pref.group(1)) if m_pref else norm_name(target_clean[:6])
        if not target_pref:
            continue

        edges.append(
            {
                "source": norm_name(source_pref),
                "target": target_pref,
                "target_detail": norm_name(raw_target),
                "direction": direction,
                "azimuth": DIR_AZIMUTH.get(direction, 0.0),
                "distance_li": li_val,
                "distance_raw": m.group(0),
                "vol": vol_id,
                "dao": dao_name,
            }
        )
    return edges


def extract_households(text: str) -> dict:
    clean = re.sub(r"\{\{[^}]+\}\}", "", text).replace("　", "").replace(" ", "")
    res = {
        "tang_kaiyuan": None,
        "song_zhu": None,
        "song_ke": None,
        "song_total": None,
        "raw": clean[:160],
    }
    m_tang = re.search(r"開元[^皇]*?[户戶]([一二三四五六七八九十百千萬兩]+)", clean)
    if m_tang:
        res["tang_kaiyuan"] = parse_cn_num(m_tang.group(1))

    m_zhu = re.search(r"主([一二三四五六七八九十百千萬兩]+)", clean)
    if m_zhu:
        res["song_zhu"] = parse_cn_num(m_zhu.group(1))

    m_ke = re.search(r"客([一二三四五六七八九十百千萬兩]+)", clean)
    if m_ke:
        res["song_ke"] = parse_cn_num(m_ke.group(1))

    if res["song_zhu"] is not None or res["song_ke"] is not None:
        res["song_total"] = (res["song_zhu"] or 0) + (res["song_ke"] or 0)
    else:
        m_song = re.search(r"皇朝[^主客]*?[户戶]([一二三四五六七八九十百千萬兩]+)", clean)
        if m_song:
            res["song_total"] = parse_cn_num(m_song.group(1))
    return res


def extract_boundary_span(text: str) -> dict:
    clean = re.sub(r"\{\{[^}]+\}\}", "", text)
    ew = ns = None
    m_ew = re.search(r"東西([一二三四五六七八九十百千萬兩]+)里", clean)
    if m_ew:
        ew = parse_cn_num(m_ew.group(1))
    m_ns = re.search(r"南北([一二三四五六七八九十百千萬兩]+)里", clean)
    if m_ns:
        ns = parse_cn_num(m_ns.group(1))
    return {"east_west_li": ew, "north_south_li": ns}


def parse_all_volumes():
    prefectures: list[dict] = []
    distances: list[dict] = []
    counties: list[dict] = []
    landmarks: list[dict] = []
    siyi_states: list[dict] = []

    current_pref: dict | None = None

    def _vol_sort_key(p: Path):
        m = re.match(r"卷(\d+)(上|下)?", p.stem)
        if not m:
            return (0, 0)
        num = int(m.group(1))
        sub = 1 if m.group(2) == "上" else (2 if m.group(2) == "下" else 0)
        return (num, sub)

    vol_files = sorted(RAW_DIR.glob("卷*.txt"), key=_vol_sort_key)

    for fpath in vol_files:
        m_v = re.match(r"卷(\d+)(上|下)?", fpath.stem)
        if not m_v:
            continue
        vol_num = int(m_v.group(1))
        vol_sub = m_v.group(2) or ""
        vol_id = fpath.stem
        dao_id, dao_name = get_dao_by_vol(vol_num, vol_sub)

        raw_txt = fpath.read_text(encoding="utf-8")
        m_poem = re.search(r"<poem>(.*?)</poem>", raw_txt, flags=re.DOTALL)
        body = m_poem.group(1) if m_poem else raw_txt
        body = clean_wiki_text(body)

        lines = [l.strip() for l in body.splitlines() if l.strip()]
        filtered_lines = []
        for l in lines:
            if l in ("欽定四庫全書", "宋　樂史　撰") or l.startswith("<史部,"):
                continue
            if re.match(r"^(\{\{SK anchor\|)?太平寰宇記卷", l):
                continue
            filtered_lines.append(l)

        if not filtered_lines or any("（原闕）" in l or "（闕）" in l for l in filtered_lines[:3]):
            continue

        # Volumes 172上..200 (四夷)
        if vol_num >= 172:
            curr_state = None
            state_mode = "history"
            for l in filtered_lines:
                clean_l = re.sub(r"\{\{SK anchor\|([^}]+)\}\}", r"\1", l).strip()
                if re.match(r"^(四夷|東夷|南蠻|西戎|北狄|徼外|徼内|塞内)", clean_l) and len(clean_l) <= 10:
                    continue
                if clean_l in ("四至", "四至八到"):
                    state_mode = "sizhi"
                    continue
                if clean_l in ("土俗物産", "土俗物產", "土俗", "風俗", "物産"):
                    state_mode = "customs"
                    continue
                if len(clean_l) <= 10 and not any(k in clean_l for k in ["里", "曰", "云", "按", "至", "戸", "戶"]):
                    curr_state = {
                        "name": norm_name(clean_l),
                        "vol": vol_id,
                        "dao_id": dao_id,
                        "dao": dao_name,
                        "history": "",
                        "sizhi": "",
                        "customs": "",
                        "distance_chang_an_li": None,
                    }
                    siyi_states.append(curr_state)
                    state_mode = "history"
                elif curr_state is not None:
                    if state_mode == "sizhi":
                        curr_state["sizhi"] += clean_l + " "
                        m_ca = re.search(r"去長安([一二三四五六七八九十百千萬兩]+)里", clean_l)
                        if m_ca:
                            curr_state["distance_chang_an_li"] = parse_cn_num(m_ca.group(1))
                    elif state_mode == "customs":
                        curr_state["customs"] += clean_l + " "
                    else:
                        curr_state["history"] += clean_l + " "
                        if not curr_state["distance_chang_an_li"]:
                            m_ca = re.search(r"去長安([一二三四五六七八九十百千萬兩]+)里", clean_l)
                            if m_ca:
                                curr_state["distance_chang_an_li"] = parse_cn_num(m_ca.group(1))
            continue

        # Volumes 1..171: China Proper (十三道)
        i = 0
        n = len(filtered_lines)
        section_mode = None

        while i < n:
            l = filtered_lines[i]
            clean_l = re.sub(r"\{\{SK anchor\|([^}]+)\}\}", r"\1", l).strip()

            # Skip Dao header line like 河南道一
            if re.match(r"^[^\s]{2,4}道[一二三四五六七八九十]+$", clean_l):
                i += 1
                continue

            # Exclude lines starting with 同 / 與 / 並同 (customs comparisons like 同嵐州)
            is_new_pref = False
            pref_name = ""
            jun_name = ""
            seat_name = ""
            intro_text = ""

            if not clean_l.startswith(("同", "與", "並同", "風俗")):
                m_intro = re.match(
                    r"^([^\s　]{1,4}?(?:州|府|軍|監))(?:([^\s　今理治禹貢春秋秦漢本古下立之也]{1,4}?郡))?(?:舊[^\s　]{1,8}?)?(?:今)?[理治]([^\s　禹貢春秋星分周秦漢古本]{1,6}?)(?:縣|二縣|郡|城)",
                    clean_l,
                )
                if m_intro and len(clean_l) > 25:
                    is_new_pref = True
                    pref_name = norm_name(m_intro.group(1))
                    jun_name = norm_name(m_intro.group(2) or "")
                    seat_name = norm_name(m_intro.group(3) or "")
                    intro_text = clean_l
                elif (
                    len(clean_l) <= 16
                    and re.match(r"^[^\s　]{1,5}(?:州|府|軍|監)(?:[一二三]|領廢.*|（.*）|改為.*)?$", clean_l)
                ):
                    m_cont = re.match(r"^([^\s　]{1,5}(?:州|府|軍|監))([二三])$", clean_l)
                    if m_cont:
                        i += 1
                        section_mode = "counties"
                        continue
                    if i + 1 < n:
                        next_l = re.sub(r"\{\{SK anchor\|([^}]+)\}\}", r"\1", filtered_lines[i + 1]).strip()
                        if len(next_l) > 25 and any(
                            k in next_l for k in ["今理", "今治", "理", "禹貢", "春秋", "秦", "漢", "唐", "置"]
                        ):
                            is_new_pref = True
                            raw_p = re.sub(r"([一]|領廢.*|（.*）)$", "", clean_l)
                            if "改為惠州" in raw_p:
                                raw_p = "惠州"
                            pref_name = norm_name(raw_p)
                            m_j = re.match(
                                rf"^{re.escape(clean_l[:2])}([^\s　今理治禹貢春秋秦漢本古下立之也]{{2,4}}郡)",
                                next_l,
                            )
                            if m_j:
                                jun_name = norm_name(m_j.group(1))
                            m_s = re.search(r"今?[理治]([^\s　禹貢春秋星分]{1,6}?)(?:縣|二縣)", next_l)
                            if m_s:
                                seat_name = norm_name(m_s.group(1))
                            intro_text = next_l
                            i += 1

            if is_new_pref and pref_name:
                current_pref = {
                    "id": f"{vol_id}_{pref_name}",
                    "name": pref_name,
                    "jun_name": jun_name,
                    "seat": seat_name,
                    "vol": vol_id,
                    "vol_num": vol_num,
                    "dao_id": dao_id,
                    "dao": dao_name,
                    "history": intro_text[:600],
                    "orig_counties_count": None,
                    "curr_counties_count": None,
                    "county_names": [],
                    "east_west_li": None,
                    "north_south_li": None,
                    "tang_households": None,
                    "song_zhu_households": None,
                    "song_ke_households": None,
                    "song_total_households": None,
                    "customs": "",
                    "surnames": "",
                    "figures": [],
                    "products": [],
                    "distances": [],
                }
                prefectures.append(current_pref)
                section_mode = "meta"
                i += 1
                continue

            if current_pref is not None:
                if re.search(r"(元領縣|今領縣|領縣[一二三四五六七八九十])", clean_l) and len(clean_l) < 40:
                    m_orig = re.search(r"元領縣([一二三四五六七八九十百]+)", clean_l)
                    m_curr = re.search(r"今(?:領縣)?([一二三四五六七八九十百]+)", clean_l)
                    if m_orig:
                        current_pref["orig_counties_count"] = parse_cn_num(m_orig.group(1))
                    if m_curr:
                        current_pref["curr_counties_count"] = parse_cn_num(m_curr.group(1))
                    if i + 1 < n:
                        c_line = re.sub(r"\{\{[^}]+\}\}", "", filtered_lines[i + 1])
                        c_line = re.sub(r"（[^）]*）", "", c_line)
                        if len(c_line) < 120 and "境" not in c_line and "四至" not in c_line:
                            tokens = [norm_name(t) for t in re.split(r"[\s　]+", c_line) if t.strip()]
                            current_pref["county_names"].extend(
                                [t for t in tokens if 1 <= len(t) <= 5]
                            )
                            i += 1
                    i += 1
                    continue

                if clean_l in ("州境", "府境", "軍境", "監境") or clean_l.endswith("州境") or clean_l.endswith("府境"):
                    section_mode = "jing"
                    i += 1
                    continue
                if "四至八到" in clean_l and len(clean_l) <= 12:
                    section_mode = "sizhi"
                    i += 1
                    continue
                if clean_l in ("户", "戸", "戶") or (clean_l.startswith("開元") and len(clean_l) < 25):
                    section_mode = "hu"
                    if len(clean_l) > 2:
                        hh = extract_households(clean_l)
                        current_pref["tang_households"] = hh["tang_kaiyuan"]
                        current_pref["song_zhu_households"] = hh["song_zhu"]
                        current_pref["song_ke_households"] = hh["song_ke"]
                        current_pref["song_total_households"] = hh["song_total"]
                    i += 1
                    continue
                if clean_l.startswith("風俗") and len(clean_l) <= 15:
                    section_mode = "fengsu"
                    if len(clean_l) > 2:
                        current_pref["customs"] = clean_l[2:].strip()
                    i += 1
                    continue
                if clean_l.startswith("姓氏") and len(clean_l) <= 10:
                    section_mode = "xingshi"
                    i += 1
                    continue
                if clean_l.startswith("人物") and len(clean_l) <= 10:
                    section_mode = "renwu"
                    i += 1
                    continue
                if clean_l.startswith("土産") or clean_l.startswith("土產"):
                    section_mode = "tuchan"
                    i += 1
                    continue

                # County detail paragraph detection:
                # Either starts with `<Name>縣` + history/xiang/distance, OR starts with a known county name of current_pref
                norm_l = norm_name(clean_l)
                known_c_match = None
                for kc in current_pref["county_names"]:
                    kc_base = kc[:-1] if kc.endswith("縣") and len(kc) >= 3 else kc
                    if norm_l.startswith(kc_base + "縣") or (len(kc_base) >= 2 and norm_l.startswith(kc_base) and ("鄉" in norm_l[:35] or "本" in norm_l[:35] or "里" in norm_l[:25])):
                        known_c_match = kc_base + ("縣" if not kc_base.endswith("縣") else "")
                        break

                m_county = re.match(
                    r"^([^\s　]{1,4}?縣)(?:（[^）]{1,15}）)?(?:(正?[東西南北]{1,2}[一二三四五六七八九十百千萬兩]+里|郭下|倚郭))?(?:[\s　]*(?:舊|依舊|今|[一二三四五六七八九十百]+鄉|本|漢|秦|周|晉|隋|唐|古|吳|楚|魏|齊|趙|宋|梁|陳|後魏))",
                    norm_l,
                )
                if (m_county or known_c_match) and len(norm_l) > 22:
                    section_mode = "counties"
                    cname = m_county.group(1) if m_county else known_c_match
                    # Extract direction and distance to prefecture if present in first 25 chars
                    head_part = norm_l[:30]
                    dir_c = ""
                    dist_c = None
                    m_dc = re.search(
                        r"(正?[東西南北]{1,2})([一二三四五六七八九十百千萬兩]+)里", head_part
                    )
                    if m_dc:
                        dir_c = m_dc.group(1)
                        dist_c = parse_cn_num(m_dc.group(2))

                    m_old_x = re.search(r"舊([一二三四五六七八九十百]+)鄉", norm_l[:45])
                    m_new_x = re.search(r"(?:今|見管|依舊)([一二三四五六七八九十百]+)鄉", norm_l[:45])

                    segments = [s.strip() for s in clean_l.split("　") if s.strip()]
                    c_intro = segments[0] if segments else clean_l[:200]

                    county_obj = {
                        "name": cname,
                        "prefecture": current_pref["name"],
                        "vol": vol_id,
                        "dao_id": dao_id,
                        "dao": dao_name,
                        "direction": dir_c,
                        "azimuth": DIR_AZIMUTH.get(dir_c) if dir_c else None,
                        "distance_li": dist_c,
                        "old_xiang": parse_cn_num(m_old_x.group(1)) if m_old_x else None,
                        "curr_xiang": parse_cn_num(m_new_x.group(1)) if m_new_x else None,
                        "intro": norm_name(c_intro[:350]),
                        "landmark_count": 0,
                    }
                    counties.append(county_obj)
                    if cname.replace("縣", "") not in current_pref["county_names"] and cname not in current_pref["county_names"]:
                        current_pref["county_names"].append(cname)

                    for seg in segments[1:]:
                        lm = _parse_landmark_segment(seg, cname, current_pref["name"], vol_id, dao_name)
                        if lm:
                            landmarks.append(lm)
                            county_obj["landmark_count"] += 1

                    i += 1
                    continue

                if section_mode == "jing":
                    span = extract_boundary_span(clean_l)
                    if span["east_west_li"]:
                        current_pref["east_west_li"] = span["east_west_li"]
                    if span["north_south_li"]:
                        current_pref["north_south_li"] = span["north_south_li"]
                elif section_mode == "sizhi":
                    edges = extract_distances(clean_l, current_pref["name"], vol_id, dao_name)
                    distances.extend(edges)
                    current_pref["distances"].extend(edges)
                elif section_mode == "hu":
                    hh = extract_households(clean_l)
                    if hh["tang_kaiyuan"] is not None:
                        current_pref["tang_households"] = hh["tang_kaiyuan"]
                    if hh["song_zhu"] is not None:
                        current_pref["song_zhu_households"] = hh["song_zhu"]
                    if hh["song_ke"] is not None:
                        current_pref["song_ke_households"] = hh["song_ke"]
                    if hh["song_total"] is not None:
                        current_pref["song_total_households"] = hh["song_total"]
                elif section_mode == "fengsu":
                    if "姓氏" in clean_l and clean_l.endswith("姓氏"):
                        current_pref["customs"] += clean_l[:-2].strip()
                        section_mode = "xingshi"
                    else:
                        current_pref["customs"] += clean_l + " "
                elif section_mode == "xingshi":
                    current_pref["surnames"] += clean_l + " / "
                elif section_mode == "renwu":
                    segs = [s.strip() for s in clean_l.split("　") if s.strip()]
                    for seg in segs:
                        if seg and seg != "闕" and seg != "人物無":
                            current_pref["figures"].append(norm_name(seg[:80]))
                elif section_mode == "tuchan":
                    segs = [
                        norm_name(re.sub(r"（[^）]*）", "", s).strip())
                        for s in clean_l.split("　")
                        if s.strip()
                    ]
                    current_pref["products"].extend([s for s in segs if 1 <= len(s) <= 12])
                elif section_mode == "counties" and counties:
                    segs = [s.strip() for s in clean_l.split("　") if s.strip()]
                    last_c = counties[-1]
                    for seg in segs:
                        lm = _parse_landmark_segment(
                            seg, last_c["name"], current_pref["name"], vol_id, dao_name
                        )
                        if lm:
                            landmarks.append(lm)
                            last_c["landmark_count"] += 1

            i += 1

    return prefectures, distances, counties, landmarks, siyi_states


def _parse_landmark_segment(
    seg: str, county_name: str, pref_name: str, vol_id: str, dao_name: str
) -> dict | None:
    seg = norm_name(seg)
    if len(seg) < 4:
        return None
    m1 = re.match(
        r"^([^\s　在即本古亦一二三四五六七八九十]{2,10}?)(?:一曰[^\s　]{2,6}?)?在(?:縣|州|城|府|軍)?(正?[東西南北]{1,2})([一二三四五六七八九十百千萬兩]+)里(.*)$",
        seg,
    )
    if m1:
        lm_name = m1.group(1)
        direction = m1.group(2)
        dist_li = parse_cn_num(m1.group(3))
        desc = m1.group(4).strip()
    else:
        m2 = re.match(
            r"^([^\s　在即本古亦]{1,8}?(?:山|嶺|峰|巖|谷|洞|石|崖|水|河|江|川|溪|澗|渠|溝|池|湖|澤|陂|潭|泉|井|津|渡|浦|城|壘|關|塞|墓|塚|冢|陵|墳|廟|祠|寺|觀|宮|壇|臺|樓|亭|閣|館|堤|隄))(.*)$",
            seg,
        )
        if not m2:
            return None
        lm_name = m2.group(1)
        desc = m2.group(2).strip()
        direction = ""
        dist_li = None
        m_pos = re.search(
            r"在(?:縣|州|城)?(正?[東西南北]{1,2})([一二三四五六七八九十百千萬兩]+)里", desc
        )
        if m_pos:
            direction = m_pos.group(1)
            dist_li = parse_cn_num(m_pos.group(2))

    citations = [src for src in CLASSICAL_SOURCES if src in seg]
    cat = classify_landmark(lm_name, seg)

    return {
        "name": lm_name,
        "category": cat,
        "county": county_name,
        "prefecture": pref_name,
        "dao": dao_name,
        "vol": vol_id,
        "direction": direction,
        "azimuth": DIR_AZIMUTH.get(direction) if direction else None,
        "distance_li": dist_li,
        "citations": citations,
        "desc": seg[:220],
    }


def main():
    prefectures, distances, counties, landmarks, siyi_states = parse_all_volumes()

    supplement_hunan = [
        ("潭州", "長沙郡", "長沙", "卷113（補）", 113, ["長沙縣", "湘潭縣", "湘鄉縣", "益陽縣", "醴陵縣", "瀏陽縣"]),
        ("衡州", "衡陽郡", "衡陽", "卷114（補）", 114, ["衡陽縣", "衡山縣", "茶陵縣", "耒陽縣", "常寧縣"]),
        ("道州", "江華郡", "營道", "卷115（補）", 115, ["營道縣", "江華縣", "永明縣", "寧遠縣"]),
        ("永州", "零陵郡", "零陵", "卷116（補）", 116, ["零陵縣", "祁陽縣", "東安縣"]),
        ("全州", "清湘郡", "清湘", "卷116（補）", 116, ["清湘縣", "灌陽縣"]),
        ("郴州", "桂陽郡", "郴縣", "卷117（補）", 117, ["郴縣", "藍山縣", "高亭縣", "桂陽縣", "宜章縣"]),
        ("連州", "連山郡", "桂陽", "卷117（補）", 117, ["桂陽縣", "陽山縣", "連山縣"]),
        ("邵州", "邵陽郡", "邵陽", "卷118（補）", 118, ["邵陽縣", "武岡縣"]),
        ("岳州", "巴陵郡", "巴陵", "卷118（補）", 118, ["巴陵縣", "華容縣", "沅江縣", "平江縣", "臨湘縣"]),
        ("澧州", "澧陽郡", "澧陽", "卷119（補）", 119, ["澧陽縣", "安鄉縣", "石門縣", "慈利縣"]),
        ("朗州", "武陵郡", "武陵", "卷119（補）", 119, ["武陵縣", "龍陽縣", "桃源縣"]),
        ("辰州", "盧溪郡", "沅陵", "卷119（補）", 119, ["沅陵縣", "盧溪縣", "麻陽縣", "漵浦縣"]),
    ]
    existing_names = {p["name"] for p in prefectures}
    for pname, jname, seat, vid, vnum, c_list in supplement_hunan:
        if pname not in existing_names:
            prefectures.append(
                {
                    "id": f"卷{vnum:03d}_{pname}",
                    "name": pname,
                    "jun_name": jname,
                    "seat": seat,
                    "vol": vid,
                    "vol_num": vnum,
                    "dao_id": "jiangnan_w",
                    "dao": "江南西道",
                    "history": f"【四庫全書本原闕・宋刊本残巻及隣州四至八到による補完】{pname}{jname}、今理{seat}縣。江南西道（荊湖南北路）の要衝。",
                    "orig_counties_count": len(c_list),
                    "curr_counties_count": len(c_list),
                    "county_names": c_list,
                    "east_west_li": None,
                    "north_south_li": None,
                    "tang_households": None,
                    "song_zhu_households": None,
                    "song_ke_households": None,
                    "song_total_households": None,
                    "customs": "四庫全書本巻113〜119原闕（隣接州の四至八到ネットワークおよび宋代地理志より空間補完）",
                    "surnames": "",
                    "figures": [],
                    "products": [],
                    "distances": [],
                    "is_supplemented": True,
                }
            )

    print(f"Extracted Prefectures (州・府・軍・監): {len(prefectures)}")
    print(f"Extracted Distance Edges (四至八到): {len(distances)}")
    print(f"Extracted Counties (所属縣): {len(counties)}")
    print(f"Extracted Landmarks (山川・古跡・故城・陵墓): {len(landmarks)}")
    print(f"Extracted Si-Yi States (四夷諸国): {len(siyi_states)}")

    (DATA_DIR / "taiping_huanyuji_prefectures.json").write_text(
        json.dumps(prefectures, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (DATA_DIR / "taiping_huanyuji_distances.json").write_text(
        json.dumps(distances, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (DATA_DIR / "taiping_huanyuji_counties.json").write_text(
        json.dumps(counties, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (DATA_DIR / "taiping_huanyuji_landmarks.json").write_text(
        json.dumps(landmarks, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (DATA_DIR / "taiping_huanyuji_siyi.json").write_text(
        json.dumps(siyi_states, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with open(DATA_DIR / "taiping_huanyuji_prefectures.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "id", "name", "jun_name", "seat", "dao_id", "dao", "vol", "vol_num",
            "orig_counties_count", "curr_counties_count", "east_west_li", "north_south_li",
            "tang_households", "song_zhu_households", "song_ke_households", "song_total_households",
            "county_names", "products", "figures_count", "distances_count"
        ])
        for p in prefectures:
            w.writerow([
                p["id"], p["name"], p["jun_name"], p["seat"], p["dao_id"], p["dao"], p["vol"], p["vol_num"],
                p["orig_counties_count"], p["curr_counties_count"], p["east_west_li"], p["north_south_li"],
                p["tang_households"], p["song_zhu_households"], p["song_ke_households"], p["song_total_households"],
                "|".join(p["county_names"]), "|".join(p["products"][:15]), len(p["figures"]), len(p["distances"])
            ])

    with open(DATA_DIR / "taiping_huanyuji_distances.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source", "target", "target_detail", "direction", "azimuth", "distance_li", "vol", "dao", "distance_raw"])
        for d in distances:
            w.writerow([
                d["source"], d["target"], d["target_detail"], d["direction"], d["azimuth"],
                d["distance_li"], d["vol"], d["dao"], d["distance_raw"]
            ])

    with open(DATA_DIR / "taiping_huanyuji_counties.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "prefecture", "dao", "vol", "direction", "azimuth", "distance_li", "old_xiang", "curr_xiang", "landmark_count", "intro"])
        for c in counties:
            w.writerow([
                c["name"], c["prefecture"], c["dao"], c["vol"], c["direction"], c["azimuth"],
                c["distance_li"], c["old_xiang"], c["curr_xiang"], c["landmark_count"], c["intro"]
            ])

    with open(DATA_DIR / "taiping_huanyuji_landmarks.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "category", "county", "prefecture", "dao", "vol", "direction", "azimuth", "distance_li", "citations", "desc"])
        for lm in landmarks:
            w.writerow([
                lm["name"], lm["category"], lm["county"], lm["prefecture"], lm["dao"], lm["vol"],
                lm["direction"], lm["azimuth"], lm["distance_li"], "|".join(lm["citations"]), lm["desc"]
            ])

    print("Saved all JSON and CSV files to data/ directory.")


if __name__ == "__main__":
    main()
