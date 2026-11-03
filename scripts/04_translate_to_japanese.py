# -*- coding: utf-8 -*-
"""
04_translate_to_japanese.py
『太平寰宇記』の漢文解説（州府建置沿革・風俗・姓氏・人物・四至八到・所属県沿革・山川古跡・四夷伝）を
自然で読みやすい日本語（現代語和訳）に翻訳し、JSON / GeoJSON / Webバンドル (taiping_atlas_data.js) を更新する。
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
GEOJSON_DIR = ROOT_DIR / "geojson"
JS_DIR = ROOT_DIR / "js"
CACHE_PATH = DATA_DIR / "translation_cache_ja.json"

API_URL = "https://api.deepseek.com/chat/completions"

# 旧字体・異体字 → 常用漢字・標準漢字テーブル
KANJI_NORM = str.maketrans({
    "舊": "旧", "縣": "県", "鄉": "郷", "國": "国", "廢": "廃", "屬": "属", "隸": "隷",
    "據": "拠", "號": "号", "傳": "伝", "餘": "余", "處": "処", "廣": "広", "關": "関",
    "臺": "台", "澤": "沢", "險": "険", "亂": "乱", "戰": "戦", "從": "従", "與": "与",
    "為": "為", "爲": "為", "遷": "遷", "徙": "徙", "歸": "帰", "變": "変", "禮": "礼",
    "樂": "楽", "學": "学", "氣": "気", "實": "実", "寶": "宝", "寳": "宝", "顯": "顕",
    "觀": "観", "徳": "徳", "德": "徳", "夀": "寿", "壽": "寿", "靈": "霊", "鹽": "塩",
    "鐵": "鉄", "銅": "銅", "銀": "銀", "錢": "銭", "穀": "穀", "榖": "穀", "麥": "麦",
    "蠶": "蚕", "絲": "糸", "綿": "綿", "錦": "錦", "織": "織", "藥": "薬", "醫": "医",
    "嵗": "歳", "歲": "歳", "厯": "暦", "歷": "歴", "數": "数", "萬": "万", "雙": "双",
    "兩": "両", "邊": "辺", "逺": "遠", "遠": "遠", "邇": "邇", "隨": "随", "隱": "隠",
    "隠": "隠", "斷": "断", "絶": "絶", "絕": "絶", "續": "続", "統": "統", "總": "総",
    "稱": "称", "號": "号", "辭": "辞", "詞": "詞", "譯": "訳", "讀": "読", "書": "書",
    "圖": "図", "經": "経", "緯": "緯", "記": "記", "志": "志", "録": "録", "錄": "録",
    "廟": "廟", "祠": "祠", "墳": "墳", "墓": "墓", "葬": "葬", "塟": "葬", "𦵏": "葬",
    "營": "営", "築": "築", "鑿": "鑿", "開": "開", "閉": "閉", "鎮": "鎮", "鎭": "鎮",
    "軍": "軍", "師": "師", "將": "将", "将": "将", "帥": "帥", "討": "討", "滅": "滅",
    "敗": "敗", "破": "破", "降": "降", "陷": "陥", "沒": "没", "没": "没", "殺": "殺",
    "斬": "斬", "虜": "虜", "獲": "獲", "獻": "献", "貢": "貢", "賜": "賜", "封": "封",
    "拜": "拝", "授": "授", "襲": "襲", "繼": "継", "嗣": "嗣", "簒": "簒", "僭": "僭",
    "號": "号", "竊": "窃", "寇": "寇", "冦": "寇", "盜": "盗", "賊": "賊", "叛": "叛",
    "逆": "逆", "順": "順", "討": "討", "平": "平", "定": "定", "安": "安", "寧": "寧",
    "熈": "煕", "熙": "煕", "堯": "尭", "舜": "舜", "禹": "禹", "湯": "湯", "紂": "紂",
    "齊": "斉", "魯": "魯", "衛": "衛", "衞": "衛", "晉": "晋", "鄭": "鄭", "陳": "陳",
    "蔡": "蔡", "曹": "曹", "許": "許", "莒": "莒", "邾": "邾", "滕": "滕", "薛": "薛",
    "鄶": "鄶", "虢": "虢", "虞": "虞", "焦": "焦", "滑": "滑", "霍": "霍", "韓": "韓",
    "魏": "魏", "趙": "趙", "燕": "燕", "楚": "楚", "秦": "秦", "漢": "漢", "呉": "呉",
    "吳": "呉", "蜀": "蜀", "宋": "宋", "梁": "梁", "隋": "隋", "唐": "唐", "遼": "遼",
    "蠻": "蛮", "夷": "夷", "戎": "戎", "狄": "狄", "虜": "虜", "胡": "胡", "羌": "羌",
    "氐": "氐", "鮮": "鮮", "卑": "卑", "匈": "匈", "奴": "奴", "突": "突", "厥": "厥",
    "靺": "靺", "鞨": "鞨", "契": "契", "丹": "丹", "吐": "吐", "蕃": "蕃", "廻": "回",
    "紇": "紇", "高": "高", "髙": "高", "麗": "麗", "勾": "句", "百": "百", "濟": "済",
    "新": "新", "羅": "羅", "倭": "倭", "琉": "琉", "球": "球", "交": "交", "趾": "趾",
    "南": "南", "詔": "詔", "驃": "驃", "真": "真", "眞": "真", "臘": "臘", "扶": "扶",
    "林": "林", "邑": "邑", "環": "環", "王": "王", "盤": "盤", "陀": "陀", "于": "于",
    "闐": "闐", "疎": "疏", "勒": "勒", "龜": "亀", "茲": "茲", "焉": "焉", "耆": "耆",
    "高": "高", "昌": "昌", "伊": "伊", "吾": "吾", "康": "康", "居": "居", "大": "大",
    "宛": "宛", "月": "月", "氏": "氏", "罽": "罽", "賓": "賓", "天": "天", "竺": "竺",
    "波": "波", "斯": "斯", "大": "大", "食": "食", "拂": "拂", "菻": "菻",
    "兖": "兗", "豫": "豫", "冀": "冀", "青": "青", "徐": "徐", "揚": "揚", "荊": "荊",
    "荆": "荊", "梁": "梁", "雍": "雍", "幽": "幽", "并": "并", "營": "営",
    "潁": "潁", "頴": "潁", "汴": "汴", "洛": "洛", "雒": "洛", "伊": "伊", "瀍": "瀍",
    "澗": "澗", "河": "河", "濟": "済", "淮": "淮", "漢": "漢", "江": "江", "渭": "渭",
    "涇": "涇", "汾": "汾", "沁": "沁", "漳": "漳", "洹": "洹", "淇": "淇", "衛": "衛",
    "滹": "滹", "沱": "沱", "易": "易", "濡": "濡", "遼": "遼", "浿": "浿", "泗": "泗",
    "沂": "沂", "沭": "沭", "汶": "汶", "淄": "淄", "澠": "澠", "濰": "濰", "膠": "膠",
    "潁": "潁", "汝": "汝", "滍": "滍", "淯": "淯", "湍": "湍", "丹": "丹", "淅": "淅",
    "沔": "沔", "沮": "沮", "漳": "漳", "湘": "湘", "資": "資", "沅": "沅", "澧": "澧",
    "贛": "贛", "盱": "盱", "信": "信", "婺": "婺", "漸": "漸", "曹": "曹", "娥": "娥",
    "甌": "甌", "閩": "閩", "汀": "汀", "漳": "漳", "桂": "桂", "灕": "灕", "鬱": "鬱",
    "牂": "牂", "牁": "牁", "涪": "涪", "嘉": "嘉", "陵": "陵", "岷": "岷", "沱": "沱",
    "瀘": "瀘", "沫": "沫", "若": "若",
    "嶽": "岳", "岳": "岳", "嵩": "嵩", "泰": "泰", "華": "華", "恒": "恒", "恆": "恒",
    "衡": "衡", "霍": "霍", "終": "終", "南": "南", "太": "太", "行": "行", "王": "王",
    "屋": "屋", "底": "底", "柱": "柱", "析": "析", "城": "城", "雷": "雷", "首": "首",
    "龍": "竜", "門": "門", "岍": "岍", "岐": "岐", "荊": "荊", "終": "終", "南": "南",
    "鳥": "鳥", "鼠": "鼠", "積": "積", "石": "石", "崑": "崑", "崙": "崙", "崘": "崙",
    "嶧": "嶧", "蒙": "蒙", "羽": "羽", "大": "大", "別": "別", "桐": "桐", "柏": "柏",
    "熊": "熊", "耳": "耳", "外": "外", "方": "方", "伏": "伏", "牛": "牛", "九": "九",
    "疑": "疑", "嶷": "嶷", "羅": "羅", "浮": "浮", "庾": "庾", "嶺": "嶺", "峨": "峨",
    "眉": "眉", "青": "青", "城": "城", "劍": "剣", "閣": "閣", "巫": "巫", "峽": "峡",
    "峽": "峡", "峡": "峡", "峯": "峰", "峰": "峰", "巖": "巌", "巌": "巌", "洞": "洞",
    "溪": "渓", "谿": "渓", "澗": "澗", "潭": "潭", "淵": "淵", "泉": "泉", "池": "池",
    "湖": "湖", "陂": "陂", "塘": "塘", "渠": "渠", "溝": "溝", "瀆": "瀆", "津": "津",
    "渡": "渡", "橋": "橋", "梁": "梁", "坂": "坂", "阪": "坂", "坡": "坡", "岡": "岡",
    "崗": "崗", "原": "原", "野": "野", "坪": "坪", "洲": "洲", "島": "島", "嶼": "嶼",
    "灣": "湾", "浦": "浦", "濱": "浜", "灘": "灘",
    "乗": "乗", "乘": "乗", "邱": "丘", "䇿": "策", "乆": "久", "㧞": "抜", "拔": "抜",
    "凾": "函", "𡚁": "弊", "崈": "崇", "冐": "冒", "冨": "富", "躭": "耽", "㣲": "微",
    "竒": "奇", "衂": "衄", "昇": "昇", "夀": "寿", "䝉": "蒙", "厈": "斥", "㴻": "澍",
    "叚": "段", "葢": "蓋", "蓋": "蓋", "甞": "嘗", "嘗": "嘗", "𤣥": "玄", "莬": "菟",
    "㑹": "会", "𠉀": "候", "畧": "略", "矟": "槊", "隂": "陰", "陽": "陽", "駞": "駝",
    "鵝": "鵞", "鴨": "鴨", "鹽": "塩", "𠅤": "恵",
})


def normalize_kanji(text: str) -> str:
    if not text:
        return ""
    s = text.translate(KANJI_NORM)
    # Remove any leftover ideological description sequences like --
    s = re.sub(r"[⿱⿰⿸⿹⿺⿻⿲⿳].[--]*", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def rule_translate_landmark(lm: dict) -> str:
    """
    山川・古跡（6,934件）の漢文解説を自然な日本語解説に変換する。
    """
    name = normalize_kanji(lm.get("name", ""))
    cat = lm.get("category", "古跡")
    cnty = normalize_kanji(lm.get("county", ""))
    pref = normalize_kanji(lm.get("prefecture", ""))
    direction = lm.get("direction", "")
    li = lm.get("distance_li")
    raw = normalize_kanji(lm.get("desc", ""))

    if not raw:
        loc_str = f"{cnty}の{direction}{li}里" if (direction and li) else f"{pref}{cnty}域内"
        return f"【{cat}】{name}は{loc_str}に位置する。"

    s = raw
    # Strip leading repeat of name
    if s.startswith(name):
        s = s[len(name):].strip()

    # Location header
    loc_header = ""
    m_loc = re.match(r"^在(県|州|府|軍|郭)?(東南|東北|西南|西北|東|西|南|北)?([一二三四五六七八九十百千〇零]+里|郭下|城内|城外)?", s)
    if m_loc and m_loc.group(0):
        base = m_loc.group(1) or "県"
        d_str = m_loc.group(2) or ""
        l_str = m_loc.group(3) or ""
        if l_str in ("郭下", "城内"):
            loc_header = f"{name}は{base}の城内（郭下）にある。"
        elif d_str and l_str:
            loc_header = f"{name}は{base}の{d_str}{l_str}にある。"
        elif d_str:
            loc_header = f"{name}は{base}の{d_str}にある。"
        s = s[len(m_loc.group(0)):].strip()
    elif direction and li:
        loc_header = f"{name}は{cnty}の{direction}{li}里にある。"
    else:
        loc_header = f"{name}は{pref}{cnty}にある{cat}。"

    if not s:
        return loc_header

    # Translate Classical Chinese clauses into Japanese
    s = translate_classical_clauses(s)
    return f"{loc_header}{s}"


def translate_classical_clauses(text: str) -> str:
    """
    『太平寰宇記』の地志体漢文（建置沿革・風俗・山川古跡・四夷）の定型表現を
    自然な日本語（現代語和訳・書き下し調解説）へ変換する高精度ルールエンジン。
    """
    if not text:
        return ""
    s = normalize_kanji(text)

    # 1. Insert punctuation at clear structural boundaries in unpunctuated Siku Quanshu text
    # Citations
    cite_books = (
        r"禹貢|周礼職方氏|周礼|春秋左氏伝|左氏伝|左伝|史記|漢書地理志|漢書|後漢書|続漢書|晋書地道記|晋書|"
        r"宋書|斉書|梁書|陳書|後魏書|魏書|北斉書|周書|隋書|唐書|旧唐書|五代史|"
        r"水経注|水経|括地志|輿地志|元和郡県志|元和志|十道志|十道図|九州記|太康地記|郡国志|郡国県道記|"
        r"旧図経|図経|風俗通|風俗伝|陳留風俗伝|爾雅|博物志|帝王世紀|戦国策|竹書紀年|世本|山海経|論語|家語|詩云|毛詩|古今注|捜神記|列仙伝|高士伝|神仙伝|地理志|寰宇記"
    )
    s = re.sub(rf"(?<!^)(按)?({cite_books})(云|曰)", r"。『\2』にいわく、", s)
    s = re.sub(rf"^({cite_books})(云|曰)", r"『\1』にいわく、", s)

    # Dynasty / Era transitions
    dynasty_markers = (
        r"在春秋時|春秋時|戦国時|六国時|七国時|周末|秦末|漢初|後漢末|魏晋|自漢至晋|"
        r"秦併天下|秦兼天下|秦滅[六諸]?国|秦属|在秦|"
        r"漢高祖|漢武帝|漢宣帝|漢文帝|漢景帝|漢明帝|漢光武|後漢|両漢|前漢|"
        r"魏文帝|魏黄初|後魏|元魏|北魏|西魏|東魏|高斉|北斉|後周|周武帝|周大象|"
        r"隋開皇|隋大業|隋文帝|隋煬帝|隋初|隋末|隋乱|"
        r"唐武徳|唐貞観|唐永徽|唐顕慶|唐乾封|唐儀鳳|唐永淳|唐垂拱|唐天授|唐長安|唐神竜|唐景竜|唐開元|唐天宝|唐至徳|唐乾元|唐上元|唐大暦|唐貞元|唐元和|唐長慶|唐会昌|唐大中|唐咸通|唐乾符|唐天祐|唐初|唐末|"
        r"五代|朱梁|後梁|開平|後唐|同光|天成|長興|後晋|晋天福|後漢|乾祐|後周|広順|顕徳|皇朝|国朝|宋建隆|宋乾徳|宋開宝|太平興国"
    )
    s = re.sub(rf"(?<![。、，『])({dynasty_markers})", r"。\1", s)

    # Common structural patterns
    replacements = [
        # Administrative seat & boundaries
        (r"([^\s。、]+(?:府|州|軍|監))([^\s。、]+郡)?今理([^\s。、]+県)", r"\1（\2）は、現在\3を治所（行政の中心）とする。"),
        (r"今理([^\s。、]+県)", r"現在は\1を治所とする。"),
        (r"理([^\s。、]+県)", r"\1を治所とする。"),
        (r"旧([一二三四五六七八九十百]+)郷今([一二三四五六七八九十百]+)郷([一二三四五六七八九十百]+坊)?", r"旧制では\1郷、現在は\2郷\3を管轄する。"),
        (r"(東南|東北|西南|西北|東|西|南|北)([一二三四五六七八九十百千]+)里旧([一二三四五六七八九十百]+)郷今([一二三四五六七八九十百]+)郷", r"州の\1\2里にあり、旧制では\3郷、現在は\4郷を管轄する。"),
        (r"(東南|東北|西南|西北|東|西|南|北)([一二三四五六七八九十百千]+)里([一二三四五六七八九十百]+)郷今([一二三四五六七八九十百]+)郷", r"州の\1\2里にあり、旧\3郷・現在\4郷を管轄する。"),
        # Yu Gong & Astronomy
        (r"禹貢(?:為)?([^\s。、]{1,6}州)之域", r"『書経』禹貢における\1の領域にあたる。"),
        (r"禹貢(?:当|属)?([^\s。、]{1,6}州)之境", r"『書経』禹貢における\1の境域にあたる。"),
        (r"星分([^\s。、]{1,8})(?:之次)?", r"星野（二十八宿の分野）は\1に属する。"),
        # Spring & Autumn / Warring States
        (r"在?春秋時為([^\s。、]{1,8})(?:之)?(地|国|邑)", r"春秋時代には\1の\2であり、"),
        (r"春秋時属([^\s。、]{1,6})", r"春秋時代には\1に属し、"),
        (r"戦国時為([^\s。、]{1,8})(?:之)?(都|地|邑)", r"戦国時代には\1の\2であった。"),
        (r"(?:戦国|六国|七国)時属([^\s。、]{1,6})", r"戦国時代には\1に属した。"),
        # Qin & Han
        (r"秦(?:併|兼|并)天下(?:改)?為([^\s。、]{1,8}(?:郡|県))(?:地)?", r"秦が天下を統一すると\1の地となった。"),
        (r"秦滅([^\s。、]{1,4})為([^\s。、]{1,8}(?:郡|県))", r"秦が\1を滅ぼすと\2とした。"),
        (r"本漢([^\s。、]{1,6}県)地属([^\s。、]{1,6}郡)", r"もとは漢の\1県の地で、\2郡に属した。"),
        (r"本漢県属([^\s。、]{1,6}郡)", r"もとは漢代の県で、\1郡に属した。"),
        (r"漢為([^\s。、]{1,6}県)属([^\s。、]{1,6}(?:郡|国))", r"漢代には\1県となり、\2に属した。"),
        (r"漢為([^\s。、]{1,6}県)隷([^\s。、]{1,6}(?:郡|国))", r"漢代には\1県となり、\2に隷属した。"),
        (r"両漢為([^\s。、]{1,6}郡)之([^\s。、]{1,6}県)也?", r"前漢・後漢を通じて\1郡の\2県であった。"),
        # Administrative changes
        (r"於此置([^\s。、]{1,8}(?:州|郡|県|軍|鎮))", r"ここに\1を設置した。"),
        (r"于此置([^\s。、]{1,8}(?:州|郡|県|軍|鎮))", r"ここに\1を設置した。"),
        (r"改([^\s。、]{1,8})為([^\s。、]{1,8})", r"\1を改めて\2とした。"),
        (r"改為([^\s。、]{1,8}(?:州|郡|県|軍|池|台|城))", r"\1と改称した。"),
        (r"復為([^\s。、]{1,8}(?:州|郡|県|軍))", r"再び\1に戻した。"),
        (r"復置([^\s。、]{1,8}(?:州|郡|県))?", r"\1を再設置した。"),
        (r"罷州置郡", r"州を廃して郡を置いた。"),
        (r"廃郡置州", r"郡を廃して州を置いた。"),
        (r"罷郡為州", r"郡を廃して州とした。"),
        (r"罷州為([^\s。、]{1,8}郡)", r"州を廃して\1とした。"),
        (r"郡与県俱廃", r"郡と県がともに廃止された。"),
        (r"州廃県帰([^\s。、]{1,6}州)", r"州が廃止されると県は\1へ帰属した。"),
        (r"併入([^\s。、]{1,6}県?)", r"\1に編入された。"),
        (r"省([^\s。、]{1,8}県)入([^\s。、]{1,8}県)", r"\1を廃止して\2に編入した。"),
        (r"省([^\s。、]{1,6}県)", r"\1を廃止・統合した。"),
        (r"自([^\s。、]{1,6}州)来属", r"\1から移管されて当州の管轄に入った。"),
        (r"以廃([^\s。、]{1,6}州)之([^\s。、]{1,6}県)来属", r"廃止された\1の\2を当州に編入した。"),
        (r"割属([^\s。、]{1,6}(?:州|府))", r"分割して\1に属させた。"),
        (r"割入([^\s。、]{1,6}(?:州|府))", r"分割して\1に編入した。"),
        (r"移治([^\s。、]{1,8})", r"治所を\1へ移した。"),
        (r"移于今治", r"現在の治所へ移された。"),
        (r"升為([^\s。、]{1,8}(?:州|軍|府))", r"\1に昇格した。"),
        (r"昇為([^\s。、]{1,8}(?:州|軍|府))", r"\1に昇格した。"),
        (r"降為([^\s。、]{1,8}州)", r"\1に降格した。"),
        (r"皇朝因之", r"北宋（皇朝）もこれを継承している。"),
        (r"国朝因之", r"北宋（国朝）もこれを継承している。"),
        (r"自是至晋因之", r"これより晋代に至るまで継承された。"),
        (r"魏晋因之", r"魏・晋代もこれを継承した。"),
        # Naming & Location formulas
        (r"取([^\s。、]{1,8})為名也?", r"\1にちなんで名付けられた。"),
        (r"因([^\s。、]{1,8})為名也?", r"\1にちなんで名付けられた。"),
        (r"因以名県", r"これにちなんで県名とした。"),
        (r"因以為名", r"これにちなんで名付けられた。"),
        (r"故以為名", r"そのためこれを名称とした。"),
        (r"形似([^\s。、]{1,6})故名", r"形状が\1に似ていることから名付けられた。"),
        (r"即今([^\s。、]{1,12})是也", r"すなわち現在の\1がこれである。"),
        (r"即此地也", r"すなわちこの地である。"),
        (r"即此也", r"すなわちこれである。"),
        (r"是也", r"がこれにあたる。"),
        (r"今無水", r"現在は水が涸れている。"),
        (r"葬於此", r"この地に葬られた。"),
        (r"葬于此", r"この地に葬られた。"),
        (r"立祠焉", r"ここに祠を建てて祀った。"),
        # Rivers & Mountains
        (r"源出([^\s。、]{1,12}山)", r"水源は\1に発し、"),
        (r"西従([^\s。、]{1,8}県)界流入", r"西方の\1県境から流入し、"),
        (r"東従([^\s。、]{1,8}県)界流入", r"東方の\1県境から流入し、"),
        (r"北従([^\s。、]{1,8}県)界流入", r"北方の\1県境から流入し、"),
        (r"南従([^\s。、]{1,8}県)界流入", r"南方の\1県境から流入し、"),
        (r"流入([^\s。、]{1,8})", r"\1へ流れ込む。"),
        (r"北流入([^\s。、]{1,8})", r"北流して\1に注ぐ。"),
        (r"東流入([^\s。、]{1,8})", r"東流して\1に注ぐ。"),
        (r"南流入([^\s。、]{1,8})", r"南流して\1に注ぐ。"),
        (r"西流入([^\s。、]{1,8})", r"西流して\1に注ぐ。"),
        # Customs
        (r"^同([^\s。、]{1,6}州)$", r"\1の風俗と同じ。"),
        (r"^与([^\s。、]{1,6}州)同$", r"\1の風俗と同じ。"),
        (r"好儒術", r"儒学を好み、"),
        (r"好稼穡", r"農耕に励み、"),
        (r"尚忠", r"忠義を尊び、"),
        (r"尚質直", r"質朴実直を尊び、"),
        (r"俗重山川", r"風俗として山川を重んじ、"),
        (r"同姓不婚", r"同姓では婚姻せず、"),
        (r"知種麻養蚕作綿布", r"麻の栽培や養蚕、綿布の織造を知り、"),
        (r"遣使朝貢", r"使者を遣わして朝貢し、"),
        (r"遣使貢方物", r"使者を遣わして各地の特産物を献上し、"),
    ]

    for pat, rep in replacements:
        s = re.sub(pat, rep, s)

    # Clean up punctuation
    s = re.sub(r"。+", "。", s)
    s = re.sub(r"^。", "", s)
    if s and not s.endswith(("。", "」", "）")):
        s += "。"
    return s


def call_deepseek_json(api_key: str, prompt: str, timeout: float = 90.0) -> list[str] | None:
    payload = {
        "model": "deepseek-chat",
        "temperature": 0.1,
        "messages": [
            {
                "role": "system",
                "content": (
                    "あなたは中国歴史地理書『太平寰宇記』の専門翻訳者です。"
                    "入力された漢文（白文）の各項目を、正確で読みやすい現代日本語（和訳）に翻訳してください。"
                    "固有名詞（州名・県名・山川名・人名・書名・年号）は保持し、書名は『』で囲んでください。"
                    "出力は必ず {\"translations\": [\"和訳1\", \"和訳2\", ...]} のJSONオブジェクトのみとしてください。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = json.loads(r.read().decode("utf-8", "replace"))
                content = body["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                arr = parsed.get("translations")
                if isinstance(arr, list):
                    return [str(x).strip() for x in arr]
        except Exception as e:
            if attempt == 2:
                return None
            time.sleep(1.2 * (attempt + 1))
    return None


def batch_translate_llm(items: list[tuple[str, str]], api_key: str, cache: dict[str, str], batch_size: int = 15, max_workers: int = 25):
    """
    items: list of (cache_key, source_text)
    """
    todo = [(k, txt) for k, txt in items if txt and k not in cache]
    if not todo or not api_key:
        return

    batches = [todo[i : i + batch_size] for i in range(0, len(todo), batch_size)]
    print(f"  Running DeepSeek batch translation: {len(todo)} items in {len(batches)} batches (workers={max_workers})...")

    def run_one_batch(b_idx: int, batch: list[tuple[str, str]]):
        lines = []
        for idx, (_, txt) in enumerate(batch):
            clean_txt = normalize_kanji(txt)[:650]
            lines.append(f"{idx+1:02d}: {clean_txt}")
        prompt = (
            f"以下の『太平寰宇記』の漢文 {len(batch)} 件を、それぞれ自然な現代日本語に和訳してください。\n"
            f"要素数は必ず {len(batch)} 個の配列 translations としてJSONで返してください。\n\n"
            + "\n".join(lines)
        )
        res = call_deepseek_json(api_key, prompt)
        if res and len(res) == len(batch):
            return [(batch[i][0], res[i]) for i in range(len(batch))]
        return []

    done_batches = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(run_one_batch, i, b): i for i, b in enumerate(batches)}
        for fut in as_completed(futs):
            pairs = fut.result()
            for k, val in pairs:
                cache[k] = val
            done_batches += 1
            if done_batches % 10 == 0 or done_batches == len(batches):
                print(f"    Completed {done_batches}/{len(batches)} batches ({len(cache)} total cached)")


def translate_figure_str(fig: str) -> str:
    s = normalize_kanji(fig)
    # e.g. "管夷吾潁上人" -> "管夷吾（潁上の人）"
    m = re.match(r"^([^\s]{2,5}?)(?:字([^\s]{2}))?([^\s]{2,5})人(.*)$", s)
    if m:
        name, zi, place, rest = m.group(1), m.group(2), m.group(3), m.group(4)
        zi_str = f"（字は{zi}、{place}の出身）" if zi else f"（{place}の出身）"
        if rest:
            return f"{name}{zi_str}：{translate_classical_clauses(rest)}"
        return f"{name}{zi_str}"
    return translate_classical_clauses(s)


def translate_surnames_str(sur: str) -> str:
    if not sur:
        return ""
    s = normalize_kanji(sur)
    s = re.sub(r"([^\s]+)郡([一二三四五六七八九十]+)姓", r"\1郡の著姓（\2姓）：", s)
    s = re.sub(r"([^\s]+)([一二三四五六七八九十]+)姓", r"\1の著姓（\2姓）：", s)
    s = s.replace(" / ", " ／ ").strip(" ／")
    return s


def main():
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    cache: dict[str, str] = {}
    if CACHE_PATH.exists():
        try:
            cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    prefs_geo_path = DATA_DIR / "taiping_huanyuji_prefectures_geo.json"
    prefs_path = DATA_DIR / "taiping_huanyuji_prefectures.json"
    counties_path = DATA_DIR / "taiping_huanyuji_counties.json"
    landmarks_path = DATA_DIR / "taiping_huanyuji_landmarks.json"
    siyi_path = DATA_DIR / "taiping_huanyuji_siyi.json"

    prefs_geo = json.loads(prefs_geo_path.read_text(encoding="utf-8"))
    prefs_raw = json.loads(prefs_path.read_text(encoding="utf-8"))
    counties = json.loads(counties_path.read_text(encoding="utf-8"))
    landmarks = json.loads(landmarks_path.read_text(encoding="utf-8"))
    siyi_list = json.loads(siyi_path.read_text(encoding="utf-8"))

    # 1. Collect LLM translation jobs for Prefectures, Si-Yi, and Counties
    llm_jobs: list[tuple[str, str]] = []

    for p in prefs_geo:
        pid = p["id"]
        if p.get("history"):
            llm_jobs.append((f"pref_hist:{pid}", p["history"]))
        if p.get("customs") and len(p["customs"].strip()) > 6:
            llm_jobs.append((f"pref_cust:{pid}", p["customs"]))

    for idx, s in enumerate(siyi_list):
        sname = s["name"]
        if s.get("history"):
            llm_jobs.append((f"siyi_hist:{idx}:{sname}", s["history"][:650]))
        if s.get("sizhi"):
            llm_jobs.append((f"siyi_sizhi:{idx}:{sname}", s["sizhi"][:650]))
        if s.get("customs"):
            llm_jobs.append((f"siyi_cust:{idx}:{sname}", s["customs"][:650]))

    for idx, c in enumerate(counties):
        if c.get("intro"):
            llm_jobs.append((f"cnty_intro:{idx}:{c['prefecture']}_{c['name']}", c["intro"]))

    for idx, lm in enumerate(landmarks):
        desc = lm.get("desc", "").strip()
        if desc and len(desc) > 10:
            llm_jobs.append((f"lm_desc:{idx}", desc[:240]))

    print(f"Total texts for LLM translation: {len(llm_jobs)} (already cached: {len(cache)})")
    batch_translate_llm(llm_jobs, api_key, cache, batch_size=10, max_workers=35)

    # Save intermediate cache
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

    # 2. Apply translations to Prefectures
    pref_ja_map = {}
    for p in prefs_geo:
        pid = p["id"]
        hist_ja = cache.get(f"pref_hist:{pid}") or translate_classical_clauses(p.get("history", ""))
        cust_raw = p.get("customs", "").strip()
        if not cust_raw:
            cust_ja = ""
        elif len(cust_raw) <= 6:
            cust_ja = translate_classical_clauses(cust_raw)
        else:
            cust_ja = cache.get(f"pref_cust:{pid}") or translate_classical_clauses(cust_raw)

        surn_ja = translate_surnames_str(p.get("surnames", ""))
        figs_ja = [translate_figure_str(f) for f in (p.get("figures") or [])]

        p["history_ja"] = hist_ja
        p["customs_ja"] = cust_ja
        p["surnames_ja"] = surn_ja
        p["figures_ja"] = figs_ja
        pref_ja_map[pid] = (hist_ja, cust_ja, surn_ja, figs_ja)

    for p in prefs_raw:
        pid = p["id"]
        if pid in pref_ja_map:
            p["history_ja"], p["customs_ja"], p["surnames_ja"], p["figures_ja"] = pref_ja_map[pid]

    # 3. Apply translations to Counties
    for idx, c in enumerate(counties):
        ckey = f"cnty_intro:{idx}:{c['prefecture']}_{c['name']}"
        c["intro_ja"] = cache.get(ckey) or translate_classical_clauses(c.get("intro", ""))

    # 4. Apply translations to Landmarks (6,934 items)
    for idx, lm in enumerate(landmarks):
        lm["desc_ja"] = cache.get(f"lm_desc:{idx}") or rule_translate_landmark(lm)

    # 5. Apply translations to Si-Yi (203 items)
    for idx, s in enumerate(siyi_list):
        sname = s["name"]
        s["history_ja"] = cache.get(f"siyi_hist:{idx}:{sname}") or translate_classical_clauses(s.get("history", ""))
        s["sizhi_ja"] = cache.get(f"siyi_sizhi:{idx}:{sname}") or translate_classical_clauses(s.get("sizhi", ""))
        s["customs_ja"] = cache.get(f"siyi_cust:{idx}:{sname}") or translate_classical_clauses(s.get("customs", ""))

    # Save updated JSON files
    prefs_geo_path.write_text(json.dumps(prefs_geo, ensure_ascii=False, indent=2), encoding="utf-8")
    prefs_path.write_text(json.dumps(prefs_raw, ensure_ascii=False, indent=2), encoding="utf-8")
    counties_path.write_text(json.dumps(counties, ensure_ascii=False, indent=2), encoding="utf-8")
    landmarks_path.write_text(json.dumps(landmarks, ensure_ascii=False, indent=2), encoding="utf-8")
    siyi_path.write_text(json.dumps(siyi_list, ensure_ascii=False, indent=2), encoding="utf-8")

    # 6. Rebuild js/taiping_atlas_data.js and js/taiping_atlas_texts.js via 03 script
    import subprocess
    subprocess.run([sys.executable, str(ROOT_DIR / "scripts" / "03_spatial_trilateration_and_geojson.py")], check=True)

    print("All Japanese translations generated and saved successfully!")


if __name__ == "__main__":
    main()

