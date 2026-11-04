#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 6: 『太平寰宇記』全387州府軍監の戸口統計（唐開元・天宝戸数／北宋主戸・客戸・主客合算・不供戸・原書闕）
および誤抽出州名（巻166 邕州・巻122 業州）の完全補正スクリプト
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = BASE_DIR / "原文"
SK_MAP = json.loads((BASE_DIR / "scripts" / "skchars.json").read_text(encoding="utf-8"))

CN_NUM_MAP = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}
CN_UNIT_MAP = {"十": 10, "百": 100, "千": 1000, "萬": 10000}


def parse_cn_num(s: str) -> int | None:
    if not s:
        return None
    s = s.strip()
    if s.isdigit():
        return int(s)
    total = 0
    section = 0
    num = 0
    found = False
    for ch in s:
        if ch in CN_NUM_MAP:
            num = CN_NUM_MAP[ch]
            found = True
        elif ch in CN_UNIT_MAP:
            unit = CN_UNIT_MAP[ch]
            found = True
            if unit == 10000:
                if section == 0 and num == 0:
                    section = 1
                else:
                    section += num
                total += section * unit
                section = 0
                num = 0
            else:
                section += (num if num else 1) * unit
                num = 0
    total += section + num
    return total if found else None


def clean_wiki_text(raw: str) -> str:
    def _repl_skchar(m):
        return SK_MAP.get(m.group(1), "")

    s = re.sub(r"\{\{SKchar\|(\d+)(?:\|[^}]*)?\}\}", _repl_skchar, raw)
    s = re.sub(r"\{\{SK anchor\|([^}]+)\}\}", r"\1", s)
    s = re.sub(r"\{\{YL\|([^}]+)\}\}", r"\1", s)
    s = re.sub(r"\{\{SK notes\|註\}\}", "", s)
    s = re.sub(r"\{\{SK notes\|([^}]+)\}\}", r"（\1）", s)
    return s


def norm_match_str(s: str) -> str:
    s = clean_wiki_text(s)
    s = re.sub(r"\{\{[^}]+\}\}", "", s)
    s = re.sub(r"[\s　（）()]", "", s)
    for a, b in [
        ("㑹", "會"), ("寕", "寧"), ("寜", "寧"), ("䝉", "蒙"),
        ("𤣥", "玄"), ("𡰥", "崇"), ("𠑽", "獎"), ("髙", "高"),
        ("桞", "柳"), ("宻", "密"), ("賔", "賓"), ("䕶", "護"),
    ]:
        s = s.replace(a, b)
    return s


def clean_line(l: str) -> str:
    cl = re.sub(r"\{\{SK anchor\|([^}]+)\}\}", r"\1", l)
    cl = re.sub(r"\{\{YL\|([^}]+)\}\}", r"\1", cl)
    return cl.strip()


def extract_households_fixed(text: str) -> dict:
    has_que = "闕" in text or "缺" in text
    clean = re.sub(r"\{\{[^}]+\}\}", "", text).replace("　", "").replace(" ", "")
    clean = clean.replace("皇一朝", "皇朝")
    res = {
        "tang_kaiyuan": None,
        "song_zhu": None,
        "song_ke": None,
        "song_total": None,
        "song_note": None,
        "has_que": has_que,
        "raw": clean[:160],
    }

    # 1. Tang households:
    m_tang_list = list(
        re.finditer(
            r"(?:開元|間元|天寶|天寳|唐元|元和十道要畧|元和|長慶|唐舊|舊領|舊管)(?:年|中|領縣[一二三四五六七八九十]+|領?[一二三四五六七八九十]+縣|領)?[户戶戸尸]?([一二三四五六七八九十百千萬兩]+)",
            clean,
        )
    )
    for mt in m_tang_list:
        end_pos = mt.end()
        if end_pos < len(clean) and clean[end_pos] in ("年", "載", "月", "州", "縣", "鄉"):
            if (
                clean[mt.start() : end_pos].endswith("元年")
                and end_pos < len(clean)
                and clean[end_pos] in CN_NUM_MAP
            ):
                pass
            else:
                continue
        val = parse_cn_num(mt.group(1))
        if val and val >= 10:
            res["tang_kaiyuan"] = val
            break
    if res["tang_kaiyuan"] is None:
        m_qiong = re.search(r"開元(?:元年)?([一二三四五六七八九十百千萬兩]{3,})", clean)
        if m_qiong:
            res["tang_kaiyuan"] = parse_cn_num(m_qiong.group(1))
    if res["tang_kaiyuan"] is None:
        m_guo = re.search(r"(?:^|唐)(?:開|管|領)[户戶戸尸]([一二三四五六七八九十百千萬兩]+)", clean)
        if not m_guo:
            m_guo = re.search(r"唐[户戶戸尸]([一二三四五六七八九十百千萬兩]+)", clean)
        if m_guo:
            res["tang_kaiyuan"] = parse_cn_num(m_guo.group(1))
    if res["tang_kaiyuan"] is None and "皇朝" not in clean and "今管" not in clean and not clean.startswith("管"):
        m_plain = re.match(r"^(?:領[户戶戸])?([一二三四五六七八九十百千萬兩]{2,})(?:口|$|風俗)", clean)
        if m_plain:
            res["tang_kaiyuan"] = parse_cn_num(m_plain.group(1))

    # 2. Song households:
    song_part = ""
    m_song_start = re.search(r"(皇朝.*|今管.*|^管[户戶戸主客一二三四五六七八九十百千萬兩].*|^都管[户戶戸].*)", clean)
    if m_song_start:
        song_part = m_song_start.group(1)

    if song_part:
        if (
            "不供户" in song_part
            or "不供戶" in song_part
            or "不言户" in song_part
            or "只言丁" in song_part
        ) and "丁" in song_part:
            m_ding = re.search(
                r"([一二三四五六七八九十百千萬兩]+)丁|丁[户戶戸]?([一二三四五六七八九十百千萬兩]+)",
                song_part,
            )
            if m_ding:
                ding_val = parse_cn_num(m_ding.group(1) or m_ding.group(2))
                res["song_note"] = f"丁数のみ記載（{ding_val:,}丁・不供戸）"
            return res

        m_zhuke = re.search(r"主客(?:都共|共|都|[户戶戸]|漢[户戶戸])?([一二三四五六七八九十百千萬兩]+)", song_part)
        if m_zhuke:
            res["song_total"] = parse_cn_num(m_zhuke.group(1))
            res["song_note"] = "主客合算記載（内訳記載なし）"
            m_zhu_sub = re.search(r"主([一二三四五六七八九十百千萬兩]+)", song_part[m_zhuke.end():])
            m_ke_sub = re.search(r"客([一二三四五六七八九十百千萬兩]+)", song_part[m_zhuke.end():])
            if m_zhu_sub and m_ke_sub:
                res["song_zhu"] = parse_cn_num(m_zhu_sub.group(1))
                res["song_ke"] = parse_cn_num(m_ke_sub.group(1))
                res["song_note"] = "主客合算＋内訳記載"
            return res

        m_han = re.search(r"漢(?:税)?[户戶戸]?([一二三四五六七八九十百千萬兩]+)", song_part)
        if m_han:
            h_val = parse_cn_num(m_han.group(1)) or 0
            f_zhu = sum(
                parse_cn_num(m.group(1)) or 0
                for m in re.finditer(r"蕃[户戶戸]税[户戶戸]([一二三四五六七八九十百千萬兩]+)", song_part)
            )
            f_ke = sum(
                parse_cn_num(m.group(1)) or 0
                for m in re.finditer(r"蕃(?:客[户戶戸]|[户戶戸])(?!税)([一二三四五六七八九十百千萬兩]+)", song_part)
            )
            if f_zhu > 0 or f_ke > 0:
                res["song_zhu"] = h_val + f_zhu
                res["song_ke"] = f_ke
                res["song_total"] = h_val + f_zhu + f_ke
            else:
                res["song_total"] = h_val
                res["song_note"] = "総戸数のみ記載（漢戸・外は蕃戸）"
            return res

        m_zhu = re.search(r"(?:主[户戶戸]?|[户戶戸尸]主)([一二三四五六七八九十百千萬兩]+)", song_part)
        m_ke = re.search(r"[客容](?:[户戶戸])?([一二三四五六七八九十百千萬兩]+)", song_part)

        if not m_zhu and m_ke:
            m_implicit_zhu = re.search(
                r"皇朝(?:領縣[一二三四五六七八九十]+)?[户戶戸]([一二三四五六七八九十百千萬兩]+)[客容]",
                song_part,
            )
            if m_implicit_zhu:
                m_zhu = m_implicit_zhu

        if m_zhu:
            res["song_zhu"] = parse_cn_num(m_zhu.group(1))
        if m_ke:
            res["song_ke"] = parse_cn_num(m_ke.group(1))

        m_liao = re.search(r"獠[户戶戸]([一二三四五六七八九十百千萬兩]+)", song_part)
        if res["song_zhu"] and not res["song_ke"] and m_liao:
            res["song_ke"] = parse_cn_num(m_liao.group(1))

        if res["song_zhu"] is not None or res["song_ke"] is not None:
            res["song_total"] = (res["song_zhu"] or 0) + (res["song_ke"] or 0)
            return res

        m_tot = re.search(r"(?:皇朝|今管|都管|^管)[^主客丁]*?[户戶戸]([一二三四五六七八九十百千萬兩]+)", song_part)
        if not m_tot:
            m_tot = re.search(r"^管([一二三四五六七八九十百千萬兩]+)$", song_part)
        if m_tot:
            res["song_total"] = parse_cn_num(m_tot.group(1))
            res["song_note"] = "総戸数のみ記載（主客内訳なし）"

    return res


def classify_missing_song_note(p: dict, hh_res: dict, raw_hh_str: str) -> str:
    if hh_res.get("song_note"):
        return hh_res["song_note"]
    vol = p["vol"]
    dao = p["dao"]
    name = p["name"]
    if vol.endswith("（補）"):
        return "四庫全書本原闕巻（戸口統計散逸）"
    if hh_res.get("has_que") and "皇朝" in raw_hh_str:
        return "原書「皇朝戸 闕」"
    if "無籍" in raw_hh_str:
        return "原書「旧戸無籍」（数値記載なし）"
    if any(k in raw_hh_str for k in ("載撫州籍", "在循州籍", "皇朝二縣管户")):
        return "原書に皇朝戸数の数値記載なし"
    if dao == "隴右道":
        return "唐代のみ記載（北宋期は吐蕃・西域化外）"
    if dao == "河北道":
        if vol in ("卷069", "卷070") or name in ("媯州", "營州", "檀州"):
            return "唐代のみ記載（北宋期は契丹［遼］領・燕雲十六州）"
        if vol == "卷071":
            return "唐代のみ記載（唐末廃絶・東北羈縻州）"
        return "原書「皇朝戸 闕」または記載なし"
    if dao == "劍南西道":
        return "唐代のみ記載（吐蕃・西南夷境界州）"
    if dao == "江南西道":
        return "唐代のみ記載（西南渓洞・夜郎辺境州）"
    if dao == "嶺南道":
        if vol in ("卷170", "卷171"):
            return "唐代のみ記載（交趾・安南旧州／羈縻州）"
        return "唐代のみ記載（嶺南渓洞・辺境州）"
    if dao == "關西道":
        return "唐代のみ記載（党項・西夏境界州）"
    if dao == "河東道":
        return "唐代のみ記載（北宋期は契丹［遼］領・雲中地域）"
    return "原書に皇朝戸数の記載なし"


def main():
    prefs_path = DATA_DIR / "taiping_huanyuji_prefectures.json"
    prefs = json.loads(prefs_path.read_text(encoding="utf-8"))

    # 1. Fix 卷166_管羈縻州 -> 卷166_邕州 and 卷122_龍標縣州 -> 卷122_業州
    idx_122_longbiao = None
    idx_122_jiang = None
    for i, p in enumerate(prefs):
        if p["id"] == "卷166_管羈縻州":
            p["id"] = "卷166_邕州"
            p["name"] = "邕州"
            p["jun_name"] = "朗寧郡"
            p["seat"] = "宣化"
            p["history"] = re.sub(r"^樂善州在州西北一百五十里皇朝雍熈二年歸化\s*", "", p.get("history", ""))
            p["history_ja"] = re.sub(
                r"^楽善州は州の西北一百五十里にある。皇朝の雍煕二年（985年）に帰化した。\s*",
                "",
                p.get("history_ja", ""),
            )
            print("Fixed 卷166_管羈縻州 -> 卷166_邕州")
        elif p["id"] == "卷122_龍標縣州":
            idx_122_longbiao = i
        elif p["id"] == "卷122_獎州":
            idx_122_jiang = i

    if idx_122_longbiao is not None:
        ye_pref = prefs.pop(idx_122_longbiao)
        ye_pref["id"] = "卷122_業州"
        ye_pref["name"] = "業州"
        ye_pref["jun_name"] = "龍溪郡"
        ye_pref["seat"] = "峩山"
        ye_pref["lng"] = 109.18
        ye_pref["lat"] = 27.45
        ye_pref["coord_source"] = "historical_approx"
        ye_pref["tang_households"] = 1672
        ye_pref["song_zhu_households"] = None
        ye_pref["song_ke_households"] = None
        ye_pref["song_total_households"] = None
        ye_pref["history"] = (
            "業州龍溪郡今理峩山縣長安四年分沅州二縣置舞州開元十三年又改為業州天寶元年改為龍溪郡乾元元年復為業州"
        )
        ye_pref["history_ja"] = (
            "業州（龍渓郡）は現在の峩山県に治所を置く。長安四年（704年）に沅州の二県を分けて舞州を置き、"
            "開元十三年（725年）にまた改めて業州とし、天宝元年（742年）に改めて龍渓郡とし、乾元元年（758年）に復た業州とした。"
        )
        ye_pref["fengsu"] = "已上與沅州同"
        ye_pref["fengsu_ja"] = "以上は沅州と同じである。"
        ye_pref["tuchan"] = []
        # Insert right after 卷122_獎州
        insert_pos = next(i for i, p in enumerate(prefs) if p["id"] == "卷122_獎州") + 1
        prefs.insert(insert_pos, ye_pref)
        print("Fixed 卷122_龍標縣州 -> 卷122_業州 (placed after 卷122_獎州)")

    # Also update counties, landmarks, distances references
    for fn in ("counties", "landmarks", "distances"):
        fpath = DATA_DIR / f"taiping_huanyuji_{fn}.json"
        if not fpath.exists():
            continue
        items = json.loads(fpath.read_text(encoding="utf-8"))
        changed_fn = 0
        for item in items:
            for k in ("pref_id", "from_id", "to_id"):
                if item.get(k) == "卷166_管羈縻州":
                    item[k] = "卷166_邕州"
                    changed_fn += 1
                elif item.get(k) == "卷122_龍標縣州":
                    item[k] = "卷122_沅州"
                    changed_fn += 1
            for k in ("prefecture", "source", "target", "pref", "pref_name", "from_pref", "to_pref"):
                if item.get(k) == "管羈縻州":
                    item[k] = "邕州"
                    changed_fn += 1
                elif item.get(k) == "龍標縣州":
                    item[k] = "沅州"
                    changed_fn += 1
            if fn == "counties" and item.get("vol") == "卷122" and item.get("name") in ("峩山縣", "渭溪縣", "梓薑縣") and item.get("prefecture") == "獎州":
                item["prefecture"] = "業州"
                changed_fn += 1
        if changed_fn:
            fpath.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Updated {changed_fn} references in taiping_huanyuji_{fn}.json")

    # 2. Load all raw texts and update households for all 387 prefectures
    juan_texts = {}
    for path in sorted(glob.glob(str(RAW_DIR / "卷*.txt"))):
        stem = os.path.splitext(os.path.basename(path))[0]
        with open(path, "r", encoding="utf-8") as f:
            juan_texts[stem] = f.read()

    by_vol: dict[str, list[dict]] = {}
    for p in prefs:
        by_vol.setdefault(p["vol"], []).append(p)

    updated_count = 0
    for vol, vprefs in sorted(by_vol.items()):
        raw = juan_texts.get(vol, "")
        m_poem = re.search(r"<poem>(.*?)</poem>", raw, flags=re.DOTALL)
        body = m_poem.group(1) if m_poem else raw
        raw_lines = [l.strip() for l in body.splitlines() if l.strip()]
        norm_raw_lines = [norm_match_str(rl) for rl in raw_lines]

        pref_starts = []
        search_from = 0
        for p in vprefs:
            hist_full = norm_match_str(p.get("history", ""))
            found_line = None
            for probe in [hist_full[:14], hist_full[:8], hist_full[4:16], hist_full[6:18]]:
                if not probe or len(probe) < 4:
                    continue
                for li in range(search_from, len(raw_lines)):
                    if probe in norm_raw_lines[li]:
                        found_line = li
                        break
                if found_line is not None:
                    break
            pref_starts.append(found_line if found_line is not None else search_from)
            if found_line is not None:
                search_from = found_line + 1

        for idx_p, p in enumerate(vprefs):
            s_li = pref_starts[idx_p]
            e_li = (
                pref_starts[idx_p + 1]
                if idx_p + 1 < len(vprefs) and pref_starts[idx_p + 1] > s_li
                else len(raw_lines)
            )
            slice_lines = raw_lines[s_li:e_li]

            hh_text_parts = []
            in_hu = False
            seen_post_hu = False
            for sl_idx, sl in enumerate(slice_lines):
                cl = clean_line(sl)
                cl_no_notes = re.sub(r"\{\{[^}]+\}\}", "", cl).replace("　", "").strip()

                if sl_idx > 2 and (
                    cl_no_notes
                    in (
                        "寧化軍", "静戎軍", "寧邊軍", "平戎軍", "保順軍",
                        "建安軍", "温泉州", "崖州", "廢業州", "業州廢", "古州", "思明州",
                    )
                    or re.match(
                        r"^(?:寧化軍|静戎軍|管軍城本定州|平戎軍|保順軍|建安軍|温泉州|崖州|廢業州|業溪龍溪郡|古州)",
                        cl_no_notes,
                    )
                ):
                    break

                if in_hu:
                    is_county_line = re.match(r"^[^\s]{1,5}縣", cl_no_notes) and not any(
                        k in cl_no_notes
                        for k in ["唐", "開元", "天寶", "天寳", "皇朝", "舊户", "舊戶", "舊戸"]
                    )
                    if (
                        any(
                            cl_no_notes.startswith(k)
                            for k in ["風俗", "姓氏", "人物", "土産", "土產", "課利"]
                        )
                        or len(cl_no_notes) > 95
                        or is_county_line
                    ):
                        break
                    hh_text_parts.append(cl)
                    if cl_no_notes.endswith("風俗"):
                        break
                    continue

                if any(cl_no_notes.startswith(k) for k in ["風俗", "姓氏", "人物", "土産", "土產"]):
                    seen_post_hu = True
                if seen_post_hu:
                    break

                if cl_no_notes in ("户", "戶", "戸") or (
                    len(cl_no_notes) > 10 and cl_no_notes.endswith(("户", "戶", "戸")) and "至" in cl_no_notes
                ):
                    in_hu = True
                    continue

                if len(cl_no_notes) < 85 and (
                    re.match(
                        r"^(?:唐|漢朝)?(?:開元|間元|天寶|天寳|唐元|元和|長慶|舊[户戶戸載無領管]|皇朝[户戶戸管領都兩二五丁新]|皇一朝|今管[户戶戸主]|管[户戶戸主]|都管[户戶戸]|縣[户戶戸]舊|領[户戶戸][一二三四五六七八九十百千萬])",
                        cl_no_notes,
                    )
                    or re.match(r"^(?:廢)?[^\s]{1,4}州唐(?:開元|管)[户戶戸]", cl_no_notes)
                    or (
                        "皇朝" in cl_no_notes
                        and any(k in cl_no_notes for k in ["户主", "戶主", "戸主", "主戶", "主户", "主客"])
                    )
                ):
                    if not re.match(
                        r"^[^\s]{1,5}縣(?:[東西南北]|舊|今|[一二三四五六七八九十]+鄉|本|漢|唐)",
                        cl_no_notes,
                    ):
                        hh_text_parts.append(cl)
                        in_hu = True
                        if cl_no_notes.endswith("風俗"):
                            break

            combined_hh_str = " ".join(hh_text_parts)
            if combined_hh_str:
                hh_res = extract_households_fixed(combined_hh_str)
                old_vals = (
                    p.get("tang_households"),
                    p.get("song_zhu_households"),
                    p.get("song_ke_households"),
                    p.get("song_total_households"),
                )
                new_vals = (
                    hh_res["tang_kaiyuan"],
                    hh_res["song_zhu"],
                    hh_res["song_ke"],
                    hh_res["song_total"],
                )
                if old_vals != new_vals:
                    updated_count += 1
                p["tang_households"] = hh_res["tang_kaiyuan"]
                p["song_zhu_households"] = hh_res["song_zhu"]
                p["song_ke_households"] = hh_res["song_ke"]
                p["song_total_households"] = hh_res["song_total"]
                if hh_res["song_total"] is None:
                    p["household_note"] = classify_missing_song_note(p, hh_res, combined_hh_str)
                else:
                    p["household_note"] = hh_res.get("song_note")
            else:
                if p.get("song_total_households") is None:
                    p["household_note"] = classify_missing_song_note(p, {}, "")
                else:
                    p["household_note"] = None

    prefs_path.write_text(json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Successfully updated household records for {updated_count} prefectures (total: {len(prefs)}).")


if __name__ == "__main__":
    main()
