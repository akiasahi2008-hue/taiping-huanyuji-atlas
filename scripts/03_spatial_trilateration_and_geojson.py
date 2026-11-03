#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 3: CHGIS/歴史座標データ突合・NetworkX 空間グラフ三辺測量・Shapely 領域ポリゴン生成・GeoJSON 出力
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import networkx as nx
import numpy as np
from shapely.geometry import MultiPoint, MultiPolygon, Point, Polygon, mapping, shape
from shapely.ops import unary_union, voronoi_diagram

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
GEOJSON_DIR = BASE_DIR / "geojson"
JS_DIR = BASE_DIR / "js"
GEOJSON_DIR.mkdir(parents=True, exist_ok=True)
JS_DIR.mkdir(parents=True, exist_ok=True)

# 十三道＋四夷のメタデータ・配色定義
DAO_META = [
    {"id": "henan", "name": "河南道", "vols": "卷1〜24", "capital": "東京開封府・西京河南府", "tint": "#b5452f", "desc": "北宋の首都・東京開封府と西京河南府（洛陽）を擁する天下の中枢。汴水・黄河・淮水の水運網が交差し、24巻にわたり30余の州府軍監を収録する。"},
    {"id": "guanxi", "name": "關西道", "vols": "卷25〜39", "capital": "雍州（京兆府・長安）", "tint": "#8f4b32", "desc": "漢唐の故都・長安（京兆府）を中心とする関中・朔方・オルドス南縁地域。秦の四塞に守られ、西北辺防の最前線となる諸州軍を収録。"},
    {"id": "hedong", "name": "河東道", "vols": "卷40〜51", "capital": "并州（太原府）", "tint": "#7c5a38", "desc": "太行山脈の西、黄河の東に位置する表裏山河の要害。太平興国四年（979）に太宗が北漢を親征して平定した太原・晋陽・雲中（燕雲十六州の一部）を含む。"},
    {"id": "hebei", "name": "河北道", "vols": "卷52〜71", "capital": "魏州（大名府）・鎮州・幽州", "tint": "#5c6b45", "desc": "黄河以北の大平原から燕山山脈・遼西に至る広大な領域。太宗が奪還を悲願とした幽・媯・営・檀など燕雲十六州および安東都護府の旧制も詳述される。"},
    {"id": "jiannan_w", "name": "劍南西道", "vols": "卷72〜81", "capital": "益州（成都府）", "tint": "#3b7366", "desc": "成都平原および岷江・大渡河流域からチベット高原東縁（松州・維州・嶲州）に至る天府の土。乾徳三年（965）の後蜀平定により宋の版図に帰した。"},
    {"id": "jiannan_e", "name": "劍南東道", "vols": "卷82〜88", "capital": "梓州", "tint": "#2f6b78", "desc": "四川盆地東部、涪江・沱江・嘉陵江中下流域の諸州および陵井監（塩井）を管轄し、巴蜀の経済・塩業を支えた地域。"},
    {"id": "jiangnan_e", "name": "江南東道", "vols": "卷89〜102", "capital": "昇州（江寧）・杭州・福州", "tint": "#2e5f85", "desc": "旧南唐・呉越・清源軍（閩）の故地。太平興国三年（978）の呉越納土により完全統合され、蘇州・杭州・明州・福州・泉州など海陸交易の繁栄を誇る。"},
    {"id": "jiangnan_w", "name": "江南西道", "vols": "卷103〜122", "capital": "洪州・江陵府・潭州", "tint": "#455482", "desc": "長江中流域の江西・湖北南部・湖南・黔中（貴州）を包括する広域道。主戸・客戸ともに人口増加が著しい江南開発の中心地帯。"},
    {"id": "huainan", "name": "淮南道", "vols": "卷123〜132", "capital": "揚州", "tint": "#684c7d", "desc": "長江と淮河に挟まれた江淮の要衝。通済渠（汴河）・邗溝を通じて江南の漕運を東京開封府へ送り届ける帝国経済の大動脈。"},
    {"id": "shannan_w", "name": "山南西道", "vols": "卷133〜141", "capital": "興元府（漢中）", "tint": "#87486d", "desc": "秦嶺山脈の南、漢水上流の漢中盆地から嘉陵江・渠江流域（巴州・達州・合州）に至る秦蜀往来の咽喉。"},
    {"id": "shannan_e", "name": "山南東道", "vols": "卷142〜149", "capital": "襄州・江陵府（荊州）", "tint": "#994652", "desc": "漢水中下流域（襄陽・鄧州）から三峡（荊州・峡州・帰州・夔州・万州）を扼する南北水陸交通の十字路。"},
    {"id": "longyou", "name": "隴右道", "vols": "卷150〜156", "capital": "秦州・涼州・沙州", "tint": "#a86832", "desc": "隴山以西、河西回廊（涼・甘・粛・瓜・沙）から西域（伊・西・庭州・安西都護府）に至るシルクロードの故道。漢唐の旧疆を考証して収録。"},
    {"id": "lingnan", "name": "嶺南道", "vols": "卷157〜171", "capital": "廣州・桂州・交州", "tint": "#4d784e", "desc": "五嶺以南の広東・広西・海南島から交趾（ベトナム北部：交州・愛州・驩州）に至る南海交易と百越の領域。開宝四年（971）南漢平定により編入。"},
    {"id": "siyi", "name": "四夷（東夷・南蠻・西戎・北狄）", "vols": "卷172〜200", "capital": "四裔諸国・羈縻州", "tint": "#6e655c", "desc": "巻172〜200に収録される東夷（高句麗・新羅・倭国等）・南蛮（林邑・真臘・滇・夜郎等）・西戎（車師・于闐・吐蕃・大秦等）・北狄（匈奴・突厥・回紇・契丹等）の総覧。"},
]

DAO_CENTERS = {
    "henan": (115.5, 35.0),
    "guanxi": (108.8, 36.2),
    "hedong": (112.3, 37.8),
    "hebei": (116.0, 38.5),
    "jiannan_w": (103.5, 30.6),
    "jiannan_e": (105.5, 30.8),
    "jiangnan_e": (119.5, 29.0),
    "jiangnan_w": (113.5, 28.0),
    "huainan": (117.5, 32.3),
    "shannan_w": (106.8, 32.2),
    "shannan_e": (111.5, 31.5),
    "longyou": (100.0, 37.5),
    "lingnan": (110.0, 22.8),
}

# 歴史地理データベース（CHGIS / 中国歴史地図集準拠の州・府・軍・監アンカー座標）
HISTORICAL_PREF_GAZETTEER = {
    # 首都別称
    "東京": [114.35, 34.79],
    "開封府": [114.35, 34.79],
    "西京": [112.45, 34.62],
    "河南府": [112.45, 34.62],
    "長安": [108.94, 34.26],
    "上都": [108.94, 34.26],
    "東都": [112.45, 34.62],
    "雍州": [108.94, 34.26],
    "京兆府": [108.94, 34.26],
    # 河南道
    "鄆州": [116.29, 35.91],
    "廣濟軍": [115.57, 35.07],
    "濟州": [116.01, 35.39],
    "單州": [116.08, 34.79],
    "淮陽軍": [117.96, 34.15],
    "漣水軍": [119.26, 33.78],
    "青州": [118.48, 36.70],
    "濰州": [119.10, 36.71],
    "齊州": [117.00, 36.67],
    "萊州": [119.94, 37.18],
    "兗州": [116.83, 35.55],
    "利國監": [117.34, 34.58],
    "萊蕪監": [117.67, 36.21],
    # 關西道
    "鳳翔府": [107.39, 34.52],
    "乾州": [108.24, 34.52],
    "原州": [106.28, 36.00],
    "慶州": [107.88, 36.03],
    "寧州": [107.92, 35.53],
    "鹽州": [107.60, 37.59],
    "保安軍": [108.76, 36.82],
    "綏州": [110.26, 37.50],
    "銀州": [109.90, 38.05],
    "振武軍": [111.82, 40.25],
    "麟州": [110.50, 38.84],
    "勝州": [111.19, 40.27],
    "府州": [111.07, 39.03],
    "宥州": [107.98, 38.45],
    "天德軍": [108.68, 40.75],
    "夏州": [108.79, 37.99],
    "靈州": [106.20, 38.10],
    "會州": [104.69, 36.56],
    "豐州": [111.02, 40.40],
    "豊州": [111.02, 40.40],
    # 河東道
    "并州": [112.55, 37.87],
    "太原府": [112.55, 37.87],
    "蒲州": [110.27, 34.82],
    "河中府": [110.27, 34.82],
    "晉州": [111.52, 36.09],
    "澤州": [112.85, 35.50],
    "潞州": [113.11, 36.19],
    "遼州": [113.41, 37.03],
    "嵐州": [111.67, 38.42],
    "憲州": [111.95, 38.06],
    "雲州": [113.30, 40.09],
    "威勝軍": [112.69, 36.68],
    "平定軍": [113.63, 37.79],
    "岢嵐軍": [111.57, 38.70],
    "火山軍": [111.20, 39.20],
    "大通監": [112.25, 37.50],
    # 河北道
    "孟州": [112.78, 34.90],
    "懷州": [112.95, 35.09],
    "懐州": [112.95, 35.09],
    "魏州": [115.15, 36.28],
    "大名府": [115.15, 36.28],
    "相州": [114.35, 36.10],
    "衛州": [114.07, 35.42],
    "德清軍": [115.05, 35.90],
    "通利軍": [114.55, 35.67],
    "貝州": [115.67, 37.07],
    "趙州": [114.77, 37.75],
    "鎮州": [114.57, 38.14],
    "濱州": [118.02, 37.38],
    "滄州": [116.86, 38.21],
    "定遠軍": [116.43, 37.89],
    "乾寧軍": [116.80, 38.56],
    "破鹵軍": [116.38, 39.02],
    "威鹵軍": [115.65, 39.04],
    "平塞軍": [115.32, 39.00],
    "靜戎軍": [115.78, 39.05],
    "寧邊軍": [114.99, 38.52],
    "北平軍": [115.15, 38.85],
    "幽州": [116.39, 39.90],
    "媯州": [115.52, 40.40],
    "營州": [120.45, 41.57],
    "檀州": [116.84, 40.37],
    "燕州": [116.25, 40.22],
    "慎州": [116.60, 39.95],
    "思順州": [116.50, 40.10],
    "玄州": [116.95, 40.15],
    "崇賓州": [117.10, 40.05],
    "師州": [116.30, 39.70],
    "鮮州": [117.30, 39.95],
    "帶州": [116.75, 39.85],
    "青山州": [117.50, 40.20],
    "歸順州": [116.65, 40.13],
    "帰順州": [116.65, 40.13],
    "安東都護府": [123.17, 41.27],
    # 劍南西道・東道
    "益州": [104.07, 30.67],
    "成都府": [104.07, 30.67],
    "彭州": [103.94, 30.99],
    "漢州": [104.28, 30.98],
    "永康軍": [103.62, 31.00],
    "嘉州": [103.77, 29.55],
    "蜀州": [103.67, 30.63],
    "簡州": [104.55, 30.39],
    "懷安軍": [104.43, 30.72],
    "黎州": [102.65, 29.35],
    "茂州": [103.85, 31.68],
    "翼州": [103.68, 32.04],
    "維州": [103.17, 31.44],
    "戎州": [104.64, 28.75],
    "霸州": [103.35, 31.70],
    "拓州": [102.95, 32.10],
    "恭州": [102.75, 31.90],
    "嶲州": [102.26, 27.89],
    "保州": [103.45, 31.55],
    "真州": [103.25, 31.65],
    "松州": [103.60, 32.64],
    "濶州": [103.30, 32.50],
    "當州": [102.90, 32.25],
    "悉州": [103.35, 31.95],
    "靜州": [103.05, 31.85],
    "静州": [103.05, 31.85],
    "劍州": [105.47, 32.03],
    "昌州": [105.71, 29.70],
    "陵州": [104.14, 30.00],
    "陵井監": [104.16, 29.98],
    "榮州": [104.42, 29.46],
    "果州": [106.08, 30.80],
    "閬州": [105.97, 31.56],
    "普州": [105.33, 30.10],
    "梓州": [105.09, 31.10],
    "遂州": [105.59, 30.53],
    "資州": [104.85, 29.76],
    "瀘州": [105.44, 28.87],
    # 江南東道・西道・淮南道
    "昇州": [118.78, 32.04],
    "龍焙監": [118.33, 27.03],
    "袁州": [114.39, 27.80],
    "涪州": [107.39, 29.70],
    "夷州": [107.19, 27.95],
    "播州": [106.93, 27.70],
    "費州": [108.25, 28.32],
    "思州": [108.55, 28.55],
    "南州": [106.68, 28.98],
    "西高州": [106.90, 28.60],
    "溱州": [106.75, 28.75],
    "牂州": [107.50, 27.05],
    "龍標縣州": [109.70, 27.20],
    "獎州": [109.20, 27.35],
    "鹽城監": [120.15, 33.38],
    "海陵監": [120.57, 32.39],
    "天長軍": [119.00, 32.69],
    "信陽軍": [114.09, 32.13],
    "無為軍": [117.90, 31.30],
    "高郵軍": [119.45, 32.78],
    "建安軍": [119.17, 32.27],
    # 山南西道・東道
    "興元府": [107.03, 33.07],
    "鳳州": [106.52, 33.91],
    "興州": [106.15, 33.33],
    "利州": [105.82, 32.43],
    "開州": [108.41, 31.16],
    "集州": [106.83, 32.35],
    "開寶監": [106.45, 33.85],
    "文州": [104.68, 32.94],
    "合州": [106.28, 29.97],
    "渝州": [106.55, 29.56],
    "達州": [107.50, 31.21],
    "洋州": [107.55, 33.22],
    "渠州": [106.97, 30.84],
    "廣安軍": [106.63, 30.46],
    "巴州": [106.75, 31.86],
    "蓬州": [106.41, 31.05],
    "壁州": [107.24, 31.95],
    "金州": [109.03, 32.69],
    "夔州": [109.53, 31.05],
    "大寧監": [109.60, 31.40],
    "萬州": [108.41, 30.81],
    "梁山軍": [107.80, 30.67],
    "荊門軍": [112.20, 31.03],
    "漢陽軍": [114.27, 30.55],
    "光化軍": [111.67, 32.39],
    # 隴右道
    "成州": [105.73, 33.74],
    "渭州": [106.67, 35.54],
    "肅州": [98.50, 39.74],
    "粛州": [98.50, 39.74],
    "河州": [103.21, 35.60],
    "儀州": [106.65, 35.22],
    "太平監": [105.72, 34.58],
    "沙州": [94.66, 40.14],
    "瓜州": [95.78, 40.52],
    "伊州": [93.51, 42.83],
    "岷州": [104.04, 34.43],
    "廓州": [102.15, 36.05],
    "疊州": [103.22, 34.06],
    "宕州": [104.39, 34.05],
    "西州": [89.19, 42.95],
    "庭州": [89.17, 44.00],
    "瀚海軍": [89.18, 44.02],
    "天山軍": [93.50, 42.82],
    "伊吾軍": [93.10, 43.60],
    "安西大都護府": [82.96, 41.72],
    # 嶺南道
    "賓州": [108.81, 23.22],
    "橫州": [109.26, 22.68],
    "横州": [109.26, 22.68],
    "宜州": [108.65, 24.50],
    "湯州": [106.80, 22.10],
    "環州": [108.25, 24.80],
    "澄州": [108.15, 23.50],
    "景州": [106.50, 22.00],
    "惠州": [114.41, 23.11],
    "湞州": [114.41, 23.11],
    "藤州": [110.91, 23.37],
    "龔州": [110.49, 23.54],
    "南儀州": [110.99, 22.92],
    "蒙州": [110.52, 24.20],
    "潯州": [110.08, 23.39],
    "梧州": [111.28, 23.48],
    "邕州": [108.32, 22.82],
    "管羈縻州": [107.50, 22.90],
    "田州": [106.95, 23.62],
    "山州": [109.30, 22.15],
    "白州": [109.98, 22.27],
    "柳州": [109.42, 24.33],
    "太平軍": [109.12, 21.67],
    "廉州": [109.12, 21.67],
    "交州": [105.85, 21.03],
    "愛州": [105.78, 19.81],
    "驩州": [105.68, 18.68],
    "峯州": [105.32, 21.30],
    "福禄州": [105.55, 19.10],
    "長州": [105.90, 20.30],
    "武峩州": [105.85, 21.60],
    "芝州": [108.35, 24.15],
    "演州": [105.60, 19.00],
    "林州": [106.50, 17.50],
    "籠州": [106.85, 22.35],
    # 湖南補完州
    "潭州": [112.98, 28.20],
    "衡州": [112.61, 26.89],
    "道州": [111.60, 25.53],
    "永州": [111.61, 26.21],
    "全州": [111.07, 25.93],
    "郴州": [113.01, 25.77],
    "連州": [112.38, 24.78],
    "邵州": [111.47, 27.24],
    "岳州": [113.09, 29.37],
    "澧州": [111.75, 29.64],
    "朗州": [111.69, 29.03],
    "辰州": [110.39, 28.45],
}

# 四夷諸国の代表座標辞書
SIYI_GAZETTEER = {
    "朝鮮": [125.75, 39.03],
    "濊國": [128.60, 37.75],
    "馬韓": [126.90, 35.95],
    "辰韓": [129.21, 35.84],
    "弁辰": [128.89, 35.23],
    "百濟": [126.91, 36.28],
    "高句麗國": [126.18, 41.13],
    "高句麗": [126.18, 41.13],
    "新羅國": [129.22, 35.86],
    "倭國": [135.80, 34.68],
    "日本": [135.77, 35.01],
    "夫餘國": [124.82, 43.50],
    "東沃沮國": [129.55, 42.90],
    "挹婁國": [130.35, 45.20],
    "勿吉國": [127.00, 45.50],
    "靺鞨國": [128.90, 44.30],
    "渤海國": [129.15, 44.14],
    "蝦夷國": [140.74, 40.82],
    "流鬼國": [142.80, 50.80],
    "倭": [135.80, 34.68],
    "林邑國": [108.22, 15.88],
    "真臘國": [103.86, 13.41],
    "扶南國": [105.00, 10.90],
    "赤土國": [100.15, 8.40],
    "丹丹國": [102.25, 6.12],
    "婆利國": [115.22, -8.65],
    "盤盤國": [99.30, 9.14],
    "驃國": [95.29, 18.82],
    "南詔": [100.16, 25.70],
    "滇國": [102.77, 24.70],
    "夜郎國": [105.30, 26.80],
    "邛都": [102.26, 27.89],
    "莋國": [102.65, 29.35],
    "冉駹": [103.58, 31.68],
    "白馬氐": [104.90, 33.40],
    "車師國": [89.19, 42.95],
    "樓蘭國": [89.92, 40.52],
    "且末國": [85.53, 38.14],
    "于闐國": [79.92, 37.11],
    "于闐": [79.92, 37.11],
    "龜茲國": [82.96, 41.72],
    "龜茲": [82.96, 41.72],
    "焉耆國": [86.57, 42.06],
    "疏勒國": [75.99, 39.47],
    "烏孫國": [81.13, 43.15],
    "姑墨國": [80.26, 41.17],
    "温宿國": [80.24, 41.27],
    "康居國": [68.80, 42.50],
    "大宛國": [71.78, 40.99],
    "大月氏國": [66.90, 36.76],
    "安息國": [58.20, 37.95],
    "條支國": [47.80, 30.50],
    "大秦國": [36.16, 36.20],
    "天竺國": [85.14, 25.60],
    "罽賓國": [69.17, 34.53],
    "波斯國": [52.53, 29.61],
    "大食國": [44.36, 33.31],
    "吐蕃": [91.11, 29.65],
    "泥婆羅國": [85.32, 27.71],
    "吐谷渾": [99.07, 36.82],
    "黨項": [102.00, 34.50],
    "高昌": [89.53, 42.85],
    "匈奴上": [102.80, 47.20],
    "匈奴中": [106.90, 47.90],
    "匈奴下": [104.50, 46.50],
    "南匈奴": [111.19, 39.80],
    "烏桓": [118.90, 42.25],
    "鮮卑": [121.20, 47.50],
    "拓跋氏": [112.18, 40.48],
    "蠕蠕": [103.50, 47.50],
    "慕容氏": [120.45, 41.57],
    "突厥上": [102.50, 47.80],
    "突厥中": [103.20, 47.50],
    "突厥下": [104.00, 47.20],
    "西突厥": [75.30, 42.80],
    "鐵勒": [95.00, 48.50],
    "薛延陀": [101.50, 48.20],
    "回紇": [102.85, 47.45],
    "契丹": [119.38, 43.99],
    "奚": [118.60, 41.30],
    "室韋": [121.50, 50.20],
    "骨利幹": [105.50, 52.50],
}


def haversine_km(c1: tuple[float, float] | list[float], c2: tuple[float, float] | list[float]) -> float:
    lon1, lat1 = math.radians(c1[0]), math.radians(c1[1])
    lon2, lat2 = math.radians(c2[0]), math.radians(c2[1])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 12742.0 * math.asin(math.sqrt(a))


def offset_coord(origin: list[float] | tuple[float, float], azimuth_deg: float, dist_km: float) -> list[float]:
    """origin (lon, lat) から方位角 azimuth_deg (北=0, 東=90) へ dist_km 進んだ座標を返す。"""
    lon0, lat0 = origin[0], origin[1]
    rad_az = math.radians(azimuth_deg)
    dlat = (dist_km * math.cos(rad_az)) / 111.12
    cos_lat = max(0.25, math.cos(math.radians(lat0)))
    dlon = (dist_km * math.sin(rad_az)) / (111.12 * cos_lat)
    return [round(lon0 + dlon, 4), round(lat0 + dlat, 4)]


DAO_BOUNDS = {
    "henan": (110.0, 123.0, 31.5, 38.5),
    "guanxi": (103.5, 112.5, 33.0, 42.0),
    "hedong": (110.0, 115.0, 34.5, 41.0),
    "hebei": (111.5, 124.0, 34.5, 42.5),
    "jiannan_w": (101.0, 106.0, 26.0, 33.5),
    "jiannan_e": (103.5, 108.5, 27.5, 33.0),
    "jiangnan_e": (115.5, 123.0, 23.5, 33.0),
    "jiangnan_w": (106.0, 119.0, 24.0, 32.0),
    "huainan": (113.0, 122.0, 29.5, 35.0),
    "shannan_w": (104.5, 111.0, 29.0, 34.5),
    "shannan_e": (107.5, 114.5, 29.5, 34.0),
    "longyou": (75.0, 107.5, 32.5, 46.0),
    "lingnan": (103.5, 118.0, 16.5, 26.5),
}


# 州府ID別ピンポイント指定（同名州の道別・巻次別曖昧性解消）
PREF_ID_OVERRIDES = {
    "卷067_霸州": [116.39, 39.12],  # 河北道・霸州
    "卷080_霸州": [103.35, 31.70],  # 劍南西道・霸州 (静戎郡)
    "卷068_保州": [115.48, 38.85],  # 河北道・保州 (清苑)
    "卷080_保州": [103.45, 31.55],  # 劍南西道・保州 (雲山郡・定廉)
    "卷071_黎州": [120.45, 41.57],  # 河北道・黎州 (新黎)
    "卷077_黎州": [102.65, 29.35],  # 劍南西道・黎州 (漢源)
    "卷071_昌州": [120.45, 41.57],  # 河北道・昌州 (龍山)
    "卷088_昌州": [105.71, 29.70],  # 劍南東道・昌州 (昌元)
    "卷071_信州": [123.35, 42.75],  # 河北道・信州 (舊黄龍)
    "卷107_信州": [117.97, 28.45],  # 江南西道・信州 (上饒)
    "卷168_環州": [108.25, 24.80],  # 嶺南道・環州 (思恩)
    "卷171_環州": [108.15, 24.65],  # 嶺南道・環州 (正平)
    "卷080_真州": [103.25, 31.65],  # 劍南西道・真州 (昭徳郡・真符)
    "卷128_真州": [118.98, 32.32],  # 淮南道・真州 (儀徴)
    "卷081_静州": [103.05, 31.85],  # 劍南西道・静州 (静川郡・悉唐)
}


def deterministic_angle(seed_str: str) -> float:
    h = int(hashlib.md5(seed_str.encode("utf-8")).hexdigest()[:8], 16)
    return (h % 3600) / 10.0


def main():
    prefs = json.loads((DATA_DIR / "taiping_huanyuji_prefectures.json").read_text(encoding="utf-8"))
    dists = json.loads((DATA_DIR / "taiping_huanyuji_distances.json").read_text(encoding="utf-8"))
    counties = json.loads((DATA_DIR / "taiping_huanyuji_counties.json").read_text(encoding="utf-8"))
    landmarks = json.loads((DATA_DIR / "taiping_huanyuji_landmarks.json").read_text(encoding="utf-8"))
    siyi = json.loads((DATA_DIR / "taiping_huanyuji_siyi.json").read_text(encoding="utf-8"))
    ref = json.loads((DATA_DIR / "reference_geo.json").read_text(encoding="utf-8"))

    char_t2s = ref.get("charT2S", {})

    def to_simp(s: str) -> str:
        return "".join(char_t2s.get(c, c) for c in s)

    all_ref = {**ref.get("settlementCoords", {}), **ref.get("prefCoords", {})}
    pref_polys = ref.get("prefPolys", {})

    # 1. Initial Anchor Matching (CHGIS / Reference Gazetteer)
    known_coords: dict[str, list[float]] = {}
    anchor_source: dict[str, str] = {}
    pref_coords_by_id: dict[str, list[float]] = {}

    for p in prefs:
        pid = p["id"]
        name = p["name"]
        dao_id = p.get("dao_id", "")
        bounds = DAO_BOUNDS.get(dao_id)

        # 1-A. Explicit ID override (resolves all duplicate name ambiguity)
        if pid in PREF_ID_OVERRIDES:
            c = PREF_ID_OVERRIDES[pid]
            pref_coords_by_id[pid] = list(c)
            known_coords[name] = list(c)
            anchor_source[name] = "CHGIS/考証指定基準点"
            continue

        # 1-B. Check explicit historical gazetteer
        c = HISTORICAL_PREF_GAZETTEER.get(name) or HISTORICAL_PREF_GAZETTEER.get(to_simp(name))
        if c and bounds and bounds[0] <= c[0] <= bounds[1] and bounds[2] <= c[1] <= bounds[3]:
            pref_coords_by_id[pid] = list(c)
            known_coords[name] = list(c)
            anchor_source[name] = "CHGIS/歴史地図集"
            continue

        # 1-C. Check all_ref
        ns = to_simp(name)
        seat = p.get("seat", "")
        seats = to_simp(seat)
        jun = p.get("jun_name", "")
        juns = to_simp(jun)

        candidates = [
            all_ref.get(name),
            all_ref.get(ns),
            all_ref.get(ns[:-1]) if len(ns) >= 3 else None,
            all_ref.get(seat) if seat else None,
            all_ref.get(seats) if seats else None,
            all_ref.get(jun) if jun else None,
            all_ref.get(juns) if juns else None,
        ]
        matched_c = None
        for cand in candidates:
            if cand:
                if bounds is None or (bounds[0] <= cand[0] <= bounds[1] and bounds[2] <= cand[1] <= bounds[3]):
                    matched_c = cand
                    break

        if matched_c:
            pref_coords_by_id[pid] = [round(matched_c[0], 4), round(matched_c[1], 4)]
            known_coords[name] = [round(matched_c[0], 4), round(matched_c[1], 4)]
            anchor_source[name] = "CHGIS/江山時序基準点"

    print(f"Initial anchored prefectures: {len([p for p in prefs if p['name'] in known_coords])} / {len(prefs)}")

    # 2. Empirical Calibration of Song 'Li' (1里 = κ km geodesic) from known-to-known 四至八到 edges
    G = nx.DiGraph()
    ratios = []
    for e in dists:
        u, v, li = e["source"], e["target"], e["distance_li"]
        G.add_edge(u, v, distance_li=li, azimuth=e["azimuth"], direction=e["direction"])
        if u in known_coords and v in known_coords and 30 <= li <= 2500:
            geo_km = haversine_km(known_coords[u], known_coords[v])
            if 10.0 <= geo_km <= 1500.0:
                ratio = geo_km / li
                if 0.15 <= ratio <= 0.85:
                    ratios.append(ratio)

    empirical_km_per_li = float(np.median(ratios)) if ratios else 0.415
    print(f"Calibrated Song Li geodesic factor from {len(ratios)} edges: 1 里 = {empirical_km_per_li:.4f} km (median)")

    # 3. NetworkX Spatial Graph Trilateration / Vector Least-Squares for Unanchored Prefectures
    trilaterated_coords: dict[str, list[float]] = {}
    trilateration_residuals: dict[str, float] = {}

    working_coords = {p["id"]: (pref_coords_by_id.get(p["id"]) or known_coords.get(p["name"])) for p in prefs if (p["id"] in pref_coords_by_id or p["name"] in known_coords)}
    pref_by_name_default = dict(known_coords)

    for iteration in range(6):
        newly_solved = 0
        for p in prefs:
            pid = p["id"]
            u_name = p["name"]
            estimates = []
            weights = []
            bounds = DAO_BOUNDS.get(p.get("dao_id", ""))

            # Outgoing edges: u -> v ("u の [方向] D里 に v がある" => u は v から azimuth+180° 方向に D*κ km)
            for e in p["distances"]:
                v = e["target"]
                v_coord = pref_coords_by_id.get(v) or pref_by_name_default.get(v)
                if v_coord and e["distance_li"] <= 3000:
                    dist_km = e["distance_li"] * empirical_km_per_li
                    rev_az = (e["azimuth"] + 180.0) % 360.0
                    est = offset_coord(v_coord, rev_az, dist_km)
                    if bounds is None or (bounds[0] - 2.5 <= est[0] <= bounds[1] + 2.5 and bounds[2] - 2.5 <= est[1] <= bounds[3] + 2.5):
                        w = 1.0 / max(50.0, float(e["distance_li"]))
                        estimates.append(est)
                        weights.append(w)

            if estimates:
                w_arr = np.array(weights)
                est_arr = np.array(estimates)
                avg_lon = float(np.sum(est_arr[:, 0] * w_arr) / np.sum(w_arr))
                avg_lat = float(np.sum(est_arr[:, 1] * w_arr) / np.sum(w_arr))
                tri_c = [round(avg_lon, 4), round(avg_lat, 4)]
                trilaterated_coords[pid] = tri_c
                if pid not in working_coords:
                    working_coords[pid] = tri_c
                    anchor_source[pid] = f"四至八到・三辺測量 (反復{iteration+1})"
                    newly_solved += 1
        if newly_solved == 0 and iteration >= 1:
            break

    # Fallback for any isolated prefectures without distance edges
    for idx, p in enumerate(prefs):
        pid = p["id"]
        if pid not in working_coords:
            same_dao = [
                working_coords[q["id"]]
                for q in prefs
                if q["dao_id"] == p["dao_id"] and q["id"] in working_coords
            ]
            base = same_dao[-1] if same_dao else list(DAO_CENTERS.get(p["dao_id"], (114.0, 34.0)))
            ang = deterministic_angle(pid)
            working_coords[pid] = offset_coord(base, ang, 28.0)
            anchor_source[pid] = "同道近傍補間"

        # Assign final coord & trilateration residual
        p["coord"] = pref_coords_by_id.get(pid) or working_coords[pid]
        p["coord_source"] = anchor_source.get(pid) or anchor_source.get(p["name"], "CHGIS")
        if pid in trilaterated_coords:
            p["trilaterated_coord"] = trilaterated_coords[pid]
            p["trilateration_error_km"] = round(haversine_km(p["coord"], trilaterated_coords[pid]), 1)
        else:
            p["trilaterated_coord"] = p["coord"]
            p["trilateration_error_km"] = 0.0

    print(f"Final solved coordinates for prefectures: {len(prefs)} / {len(prefs)}")

    # 4. Enrich Distance Network Edges with coordinates, geodesic km, and tortuosity ratio
    pref_coord_map = {p["name"]: p["coord"] for p in prefs}
    pref_coord_by_vol = {(p["vol"], p["name"]): p["coord"] for p in prefs}
    valid_edges = []
    for e in dists:
        u, v = e["source"], e["target"]
        c_u = pref_coord_by_vol.get((e.get("vol", ""), u)) or pref_coord_map.get(u)
        c_v = pref_coord_map.get(v)
        if c_u and c_v:
            if c_u == c_v:
                continue
            geo_km = round(haversine_km(c_u, c_v), 1)
            expected_km = round(e["distance_li"] * empirical_km_per_li, 1)
            tortuosity = round(expected_km / max(1.0, geo_km), 2)
            e["source_coord"] = c_u
            e["target_coord"] = c_v
            e["geodesic_km"] = geo_km
            e["expected_km"] = expected_km
            e["tortuosity"] = tortuosity
            valid_edges.append(e)

    print(f"Georeferenced 四至八到 network edges: {len(valid_edges)} / {len(dists)}")

    # 5. Georeference 1,150 Counties (所属縣)
    county_coords_map: dict[tuple[str, str], list[float]] = {}
    for c in counties:
        pname = c["prefecture"]
        p_coord = working_coords.get(pname, [114.35, 34.79])
        cname = c["name"]
        c_simp = to_simp(cname)
        c_base = to_simp(cname[:-1]) if cname.endswith("縣") else c_simp

        # Check if county is in reference settlements and within 180 km of its prefecture
        ref_c = all_ref.get(cname) or all_ref.get(c_simp) or all_ref.get(c_base)
        if ref_c and haversine_km(p_coord, ref_c) < 180.0:
            c["coord"] = [round(ref_c[0], 4), round(ref_c[1], 4)]
            c["coord_source"] = "CHGIS基準点"
        elif c["distance_li"] and c["azimuth"] is not None and c["distance_li"] <= 600:
            dist_km = c["distance_li"] * empirical_km_per_li
            c["coord"] = offset_coord(p_coord, c["azimuth"], dist_km)
            c["coord_source"] = f"州治より{c['direction']}{c['distance_li']}里"
        else:
            # Seat county or county without explicit mileage
            if cname.replace("縣", "") in pname or c["intro"].startswith(cname + "郭下") or "倚郭" in c["intro"][:25]:
                c["coord"] = [round(p_coord[0] + 0.01, 4), round(p_coord[1] + 0.01, 4)]
                c["coord_source"] = "州府倚郭（治所）"
            else:
                ang = deterministic_angle(f"{pname}_{cname}")
                c["coord"] = offset_coord(p_coord, ang, 18.0)
                c["coord_source"] = "州域内推計配置"
        county_coords_map[(pname, cname)] = c["coord"]

    # 6. Georeference 6,934 Landmarks (山川・古跡・故城・陵墓)
    for lm in landmarks:
        pname = lm["prefecture"]
        cname = lm["county"]
        base_coord = county_coords_map.get((pname, cname)) or working_coords.get(pname, [114.35, 34.79])
        if lm["distance_li"] and lm["azimuth"] is not None and lm["distance_li"] <= 500:
            dist_km = min(120.0, lm["distance_li"] * empirical_km_per_li)
            lm["coord"] = offset_coord(base_coord, lm["azimuth"], dist_km)
            lm["coord_source"] = f"縣{lm['direction']}{lm['distance_li']}里"
        else:
            ang = deterministic_angle(f"{pname}_{cname}_{lm['name']}")
            lm["coord"] = offset_coord(base_coord, ang, 6.5)
            lm["coord_source"] = "縣域内推計"

    # 7. Georeference Si-Yi States (四夷諸国)
    siyi_dir_centers = {
        "siyi_dongyi": [128.0, 39.5],
        "siyi_nanman": [103.5, 19.5],
        "siyi_xirong": [82.0, 38.5],
        "siyi_beidi": [106.0, 46.5],
    }
    for s in siyi:
        sname = s["name"]
        if sname in SIYI_GAZETTEER:
            s["coord"] = SIYI_GAZETTEER[sname]
            s["coord_source"] = "歴史地理基準点"
        else:
            # Check substring match
            matched_c = None
            for gk, gv in SIYI_GAZETTEER.items():
                if gk in sname or sname in gk:
                    matched_c = gv
                    break
            if matched_c:
                ang = deterministic_angle(sname)
                s["coord"] = offset_coord(matched_c, ang, 35.0)
                s["coord_source"] = "歴史領域推計"
            else:
                base = siyi_dir_centers.get(s["dao_id"], [105.0, 40.0])
                ang = deterministic_angle(sname)
                rad = 120.0 + (int(hashlib.md5(sname.encode("utf-8")).hexdigest()[:4], 16) % 350)
                s["coord"] = offset_coord(base, ang, rad)
                s["coord_source"] = "四裔方位推計"

    # 8. Polygon Boundary Construction (Shapely Clipped Voronoi + s_beisong_b0 Polygons)
    print("Constructing Prefecture and Thirteen Dao polygons with Shapely...")
    # Build landmass clip mask from s_beisong_b0 polities or buffered points
    pts_list = [Point(p["coord"][0], p["coord"][1]) for p in prefs]
    pts_mp = MultiPoint(pts_list)

    # Create smooth alpha-like hull around prefectures by buffering each point by ~1.45 degrees and unioning
    buffered_disks = [pt.buffer(1.35, resolution=12) for pt in pts_list]
    land_mask = unary_union(buffered_disks).simplify(0.05, preserve_topology=True)

    # Compute Voronoi diagram across all prefecture points
    vor_polys = voronoi_diagram(pts_mp, envelope=land_mask.envelope.buffer(2.0))

    # Map each prefecture to its Voronoi cell clipped by land_mask and bounded to max radius 1.45 deg
    pref_shapes: dict[str, Polygon | MultiPolygon] = {}
    dao_Cells: dict[str, list] = {d["id"]: [] for d in DAO_META if d["id"] != "siyi"}

    for p in prefs:
        pt = Point(p["coord"][0], p["coord"][1])
        # Find containing Voronoi cell
        cell = None
        for geom in vor_polys.geoms:
            if geom.contains(pt) or geom.distance(pt) < 1e-4:
                cell = geom
                break
        local_cap = pt.buffer(1.25 if p["dao_id"] not in ("longyou", "guanxi", "hebei") else 1.65, resolution=12)
        if cell is not None:
            clipped = cell.intersection(local_cap).intersection(land_mask).simplify(0.03, preserve_topology=True)
        else:
            clipped = pt.buffer(0.45, resolution=8)

        if clipped.is_empty:
            clipped = pt.buffer(0.35, resolution=8)

        pref_shapes[p["id"]] = clipped
        if p["dao_id"] in dao_Cells:
            dao_Cells[p["dao_id"]].append(clipped)

        # Save simplified ring coordinates onto prefecture object for fast web rendering
        p["rings"] = _geom_to_rings(clipped)

    # Merge prefecture cells per Dao to create seamless Thirteen Dao (十三道) regions!
    dao_regions_out = []
    for d in DAO_META:
        did = d["id"]
        if did == "siyi":
            continue
        cells = dao_Cells.get(did, [])
        if not cells:
            continue
        merged = unary_union(cells).buffer(0.02).buffer(-0.02).simplify(0.04, preserve_topology=True)
        rep_pt = merged.representative_point()
        dao_prefs = [p for p in prefs if p["dao_id"] == did]
        tang_hh = sum(p["tang_households"] or 0 for p in dao_prefs)
        song_hh = sum(p["song_total_households"] or 0 for p in dao_prefs)
        song_zhu = sum(p["song_zhu_households"] or 0 for p in dao_prefs)
        song_ke = sum(p["song_ke_households"] or 0 for p in dao_prefs)

        dao_obj = {
            **d,
            "anchor": [round(rep_pt.x, 3), round(rep_pt.y, 3)],
            "prefecture_count": len(dao_prefs),
            "county_count": sum(len(p["county_names"]) for p in dao_prefs),
            "tang_households": tang_hh,
            "song_total_households": song_hh,
            "song_zhu_households": song_zhu,
            "song_ke_households": song_ke,
            "rings": _geom_to_rings(merged),
            "geojson_geometry": mapping(merged),
        }
        dao_regions_out.append(dao_obj)

    # 9. Export Standard RFC 7946 GeoJSON Files
    _export_geojson(
        GEOJSON_DIR / "dao_regions.geojson",
        "太平寰宇記・十三道疆域",
        [
            {
                "type": "Feature",
                "properties": {
                    k: v
                    for k, v in d.items()
                    if k not in ("rings", "geojson_geometry")
                },
                "geometry": d["geojson_geometry"],
            }
            for d in dao_regions_out
        ],
    )

    _export_geojson(
        GEOJSON_DIR / "prefectures.geojson",
        "太平寰宇記・州府軍監政区",
        [
            {
                "type": "Feature",
                "properties": {
                    "id": p["id"],
                    "name": p["name"],
                    "jun_name": p["jun_name"],
                    "seat": p["seat"],
                    "dao_id": p["dao_id"],
                    "dao": p["dao"],
                    "vol": p["vol"],
                    "coord": p["coord"],
                    "trilaterated_coord": p["trilaterated_coord"],
                    "trilateration_error_km": p["trilateration_error_km"],
                    "coord_source": p["coord_source"],
                    "tang_households": p["tang_households"],
                    "song_zhu_households": p["song_zhu_households"],
                    "song_ke_households": p["song_ke_households"],
                    "song_total_households": p["song_total_households"],
                    "counties_count": len(p["county_names"]),
                    "products": p["products"][:10],
                },
                "geometry": mapping(pref_shapes[p["id"]]),
            }
            for p in prefs
        ],
    )

    _export_geojson(
        GEOJSON_DIR / "distance_network.geojson",
        "太平寰宇記・四至八到里程網",
        [
            {
                "type": "Feature",
                "properties": {
                    "source": e["source"],
                    "target": e["target"],
                    "direction": e["direction"],
                    "distance_li": e["distance_li"],
                    "geodesic_km": e["geodesic_km"],
                    "expected_km": e["expected_km"],
                    "tortuosity": e["tortuosity"],
                    "dao": e["dao"],
                    "vol": e["vol"],
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": [e["source_coord"], e["target_coord"]],
                },
            }
            for e in valid_edges
        ],
    )

    _export_geojson(
        GEOJSON_DIR / "counties.geojson",
        "太平寰宇記・所属縣",
        [
            {
                "type": "Feature",
                "properties": {k: v for k, v in c.items() if k != "coord"},
                "geometry": {"type": "Point", "coordinates": c["coord"]},
            }
            for c in counties
        ],
    )

    _export_geojson(
        GEOJSON_DIR / "landmarks.geojson",
        "太平寰宇記・山川古跡陵墓",
        [
            {
                "type": "Feature",
                "properties": {k: v for k, v in lm.items() if k != "coord"},
                "geometry": {"type": "Point", "coordinates": lm["coord"]},
            }
            for lm in landmarks
        ],
    )

    _export_geojson(
        GEOJSON_DIR / "siyi_states.geojson",
        "太平寰宇記・四夷諸国",
        [
            {
                "type": "Feature",
                "properties": {k: v for k, v in s.items() if k != "coord"},
                "geometry": {"type": "Point", "coordinates": s["coord"]},
            }
            for s in siyi
        ],
    )

    # Save enriched JSONs back to data/
    (DATA_DIR / "taiping_huanyuji_prefectures_geo.json").write_text(
        json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 10. Build Web App JS Bundles:
    #   - `js/taiping_atlas_data.js` (Lightweight Core Map Data ~1.1 MB for instant initial load)
    #   - `js/taiping_atlas_texts.js` (Full Classical Chinese & Japanese Translations loaded asynchronously)
    core_prefs = []
    texts_prefs = {}
    for p in prefs:
        pid = p["id"]
        core_prefs.append({
            "id": pid,
            "name": p["name"],
            "jun_name": p.get("jun_name", ""),
            "dao_id": p["dao_id"],
            "dao": p["dao"],
            "vol": p["vol"],
            "seat": p.get("seat", ""),
            "east_west_li": p.get("east_west_li"),
            "north_south_li": p.get("north_south_li"),
            "tang_households": p.get("tang_households"),
            "song_zhu_households": p.get("song_zhu_households"),
            "song_ke_households": p.get("song_ke_households"),
            "song_total_households": p.get("song_total_households"),
            "orig_counties_count": p.get("orig_counties_count"),
            "county_names": p.get("county_names", []),
            "products": p.get("products", []),
            "distance_count": len(p.get("distances", [])),
            "coord": p["coord"],
            "coord_source": p.get("coord_source", ""),
            "trilaterated_coord": p.get("trilaterated_coord"),
            "trilateration_error_km": p.get("trilateration_error_km", 0),
            "rings": p.get("rings", []),
        })
        texts_prefs[pid] = {
            "history": p.get("history", ""),
            "history_ja": p.get("history_ja", ""),
            "customs": p.get("customs", ""),
            "customs_ja": p.get("customs_ja", ""),
            "surnames": p.get("surnames", ""),
            "surnames_ja": p.get("surnames_ja", ""),
            "figures": p.get("figures", []),
            "figures_ja": p.get("figures_ja", []),
            "distances": p.get("distances", []),
        }

    core_counties = []
    texts_counties = []
    for c in counties:
        core_counties.append({
            "name": c["name"],
            "prefecture": c["prefecture"],
            "dao_id": c["dao_id"],
            "dao": c["dao"],
            "vol": c["vol"],
            "direction": c.get("direction", ""),
            "distance_li": c.get("distance_li"),
            "old_xiang": c.get("old_xiang"),
            "curr_xiang": c.get("curr_xiang"),
            "coord": c["coord"],
        })
        texts_counties.append([
            c.get("intro", ""),
            c.get("intro_ja", ""),
        ])

    core_landmarks = []
    texts_landmarks = []
    for lm in landmarks:
        xy = lm["coord"]
        core_landmarks.append([
            lm["name"],
            lm["category"],
            lm["county"],
            lm["prefecture"],
            lm["dao"],
            lm["vol"],
            lm.get("direction") or "",
            lm.get("distance_li") or 0,
            round(xy[0], 2),
            round(xy[1], 2),
        ])
        texts_landmarks.append([
            (lm.get("desc") or "")[:180],
            lm.get("desc_ja") or "",
            lm.get("citations") or [],
        ])

    core_siyi = []
    texts_siyi = []
    for s in siyi:
        prev = s.get("customs_ja") or s.get("customs") or s.get("history_ja") or ""
        short_prev = prev[:60] + ("…" if len(prev) > 60 else "")
        core_siyi.append({
            "name": s["name"],
            "vol": s["vol"],
            "dao_id": s["dao_id"],
            "dao": s["dao"],
            "distance_chang_an_li": s.get("distance_chang_an_li"),
            "coord": s.get("coord"),
            "short_preview": short_prev,
        })
        texts_siyi.append({
            "history": s.get("history", ""),
            "history_ja": s.get("history_ja", ""),
            "sizhi": s.get("sizhi", ""),
            "sizhi_ja": s.get("sizhi_ja", ""),
            "customs": s.get("customs", ""),
            "customs_ja": s.get("customs_ja", ""),
        })

    bundle = {
        "meta": {
            "title": "太平寰宇記 · 北宋太宗朝天下輿図",
            "author": "宋・楽史 撰（全二百巻）",
            "calibrated_km_per_li": round(empirical_km_per_li, 4),
            "prefecture_count": len(prefs),
            "distance_edge_count": len(valid_edges),
            "county_count": len(counties),
            "landmark_count": len(landmarks),
            "siyi_count": len(siyi),
        },
        "daos": [
            {k: v for k, v in d.items() if k != "geojson_geometry"}
            for d in dao_regions_out
        ] + [DAO_META[-1]],
        "prefectures": core_prefs,
        "edges": valid_edges,
        "counties": core_counties,
        "landmarks": core_landmarks,
        "siyi": core_siyi,
    }

    js_content = (
        "/**\n"
        " * 『太平寰宇記』全二百巻 空間構造化コアデータバンドル (軽量初期表示用)\n"
        " */\n"
        "window.TAIPING_ATLAS_DATA = "
        + json.dumps(bundle, ensure_ascii=False, separators=(",", ":"))
        + ";\n"
    )
    (JS_DIR / "taiping_atlas_data.js").write_text(js_content, encoding="utf-8")

    texts_bundle = {
        "prefectures": texts_prefs,
        "counties": texts_counties,
        "landmarks": texts_landmarks,
        "siyi": texts_siyi,
    }
    texts_js_content = (
        "/**\n"
        " * 『太平寰宇記』全二百巻 詳細テキスト・現代語和訳データバンドル (非同期遅延読込用)\n"
        " */\n"
        "window.TAIPING_ATLAS_TEXTS = "
        + json.dumps(texts_bundle, ensure_ascii=False, separators=(",", ":"))
        + ";\n"
        "if (window.taipingApp && typeof window.taipingApp.hydrateTexts === 'function') {\n"
        "  window.taipingApp.hydrateTexts(window.TAIPING_ATLAS_TEXTS);\n"
        "}\n"
    )
    (JS_DIR / "taiping_atlas_texts.js").write_text(texts_js_content, encoding="utf-8")
    print(
        f"Wrote js/taiping_atlas_data.js ({len(js_content.encode('utf-8')) / 1024 / 1024:.2f} MB) "
        f"and js/taiping_atlas_texts.js ({len(texts_js_content.encode('utf-8')) / 1024 / 1024:.2f} MB)!"
    )


def _geom_to_rings(geom) -> list[list[list[float]]]:
    rings = []
    if geom.is_empty:
        return rings
    polys = [geom] if isinstance(geom, Polygon) else list(geom.geoms) if isinstance(geom, MultiPolygon) else []
    for poly in polys:
        ext = [[round(x, 2), round(y, 2)] for x, y in poly.exterior.coords]
        if len(ext) >= 4:
            rings.append(ext)
    return rings


def _export_geojson(path: Path, name: str, features: list[dict]):
    fc = {
        "type": "FeatureCollection",
        "name": name,
        "features": features,
    }
    path.write_text(json.dumps(fc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
