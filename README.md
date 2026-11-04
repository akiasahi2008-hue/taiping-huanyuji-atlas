# 『太平寰宇記』歴史地理情報システム (Taiping Huanyuji GIS & Interactive Atlas)

北宋初期の太平興国年間（976〜983年）に楽史が撰進した全二百巻の全国地理総志**『太平寰宇記』**の漢文テキストを構文解析・固有表現抽出（NER）・里程三辺測量により構造化し、現代日本語訳とともにインタラクティブに可視化したデジタル・ヒューマニティーズ（DH）歴史地図システムです。

---

## 🌟 プロジェクトの概要と特徴

1. **全国地理総志の完全構造化**
   - **十三道 387州府軍監**：四至八到（東西南北の里程）・所属県・治所・唐開元戸数・宋皇朝戸数（主戸・客戸）
   - **1,150県**：所属州府・治所位置
   - **6,934箇所**の山川古跡・城郭・関津・祠廟・陵墓等のNER抽出
   - **203の四夷諸国・部族**：東夷（高句麗・新羅・倭国等）・南蠻（林邑・真臘・夜郎等）・西戎（吐蕃・于闐・大秦等）・北狄（突厥・回紇・契丹等）

2. **漢文原文と現代日本語訳の統合**
   - 州府の沿革・風俗・姓氏・人物・土俗・物産の現代日本語全訳を搭載。
   - 漢文原文と日本語訳を瞬時に切り替えて閲覧可能。

3. **四至八到里程網とネットワーク三辺測量（Trilateration）**
   - 『太平寰宇記』に記された州間・都城間（東京開封府・西京河南府・長安）の里程（里）をNetworkXで有向グラフ化。
   - CHGIS（ハーバード中国歴史地理情報システム）の基準アンカー座標と宋代1里＝約372mの道路屈曲度（Tortuosity）モデルに基づき、座標未同定地点の三辺測量を実行。

4. **高度なWebGIS可視化（SVG / D3 / Canvas）**
   - 行政道・州府多角形領域（ボロノイ分割）
   - 唐代 vs 宋代 戸数バブルチャート
   - 地名ラベルのズーム不変スケール（Zoom-Invariant Typography：拡大しても文字が巨大化・微小化しない最適化）
   - 全道総覧、道別詳細、四夷諸国ビューのシームレスな切替

---

## 📂 ディレクトリ構成

```text
.
├── index.html                   # メインWebGISアプリケーション
├── css/
│   └── style.css                # スタイルシート（宋代風クラシカルデザイン）
├── js/
│   ├── app.js                   # アプリケーションロジック（地図投影・イベント・検索）
│   ├── taiping_atlas_data.js    # 構造化データバンドル（州府・県・山川・四夷・日本語訳）
│   └── china_geo_data.js        # 現代省境・河川水系データ
├── geojson/                     # 各種GeoJSONオープンデータ
│   ├── prefectures_song.geojson # 387州府ポリゴン・ポイント
│   ├── counties_song.geojson    # 1,150県ポイント
│   ├── landmarks_ner.geojson    # 6,934山川古跡ポイント
│   ├── network_edges.geojson    # 四至八到里程グラフ
│   └── siyi_states.geojson      # 四夷203諸国・部族ポイント
├── data/                        # 抽出・変換中間データ（JSON / CSV）
│   ├── taiping_huanyuji_prefectures.json
│   ├── taiping_huanyuji_counties.json
│   ├── taiping_huanyuji_landmarks.json
│   ├── taiping_huanyuji_siyi.json
│   └── reference_geo.json       # CHGIS突合用地理マスタ
├── 原文/                        # 『太平寰宇記』全200巻 漢文テキスト（巻別）
├── scripts/                     # データ解析・NER・測量パイプライン（Python）
│   ├── 01_fetch_texts.py        # 原文テキスト取得・クリーニング
│   ├── 02_parse_and_extract_ner.py # 形態素解析・NER・里程抽出
│   ├── 03_spatial_trilateration_and_geojson.py # CHGIS突合・三辺測量・GeoJSON生成
│   ├── 04_translate_to_japanese.py # 現代日本語訳バッチ生成
│   └── ftp_upload_taiping.py    # デプロイ用スクリプト
└── notebooks/                   # Google Colab用分析ノートブック
```

---

## 🚀 ローカルでの実行方法

Webブラウザで直接 `index.html` を開くか、ローカルHTTPサーバーを起動してアクセスしてください：

```bash
# Pythonの簡易Webサーバーを起動
python -m http.server 8000
```

ブラウザで `http://localhost:8000` を開くとマップが表示されます。

---

## 🛠 解析・構築パイプライン

1. **漢文テキスト解析・固有表現抽出 (NER)**
   - 巻ごとに「四至八到」「所属県」「管内山川・古跡・官衙」「風俗」「人物」「土産」を正規表現および自然言語処理モデルで構造化。
2. **地理空間同定 & 三辺測量 (NetworkX / GeoPandas)**
   - CHGIS（China Historical GIS）の宋代・唐代州県データと突合。
   - 異表記・改称（静州などの同名異地）の道別境界フィルタリングと手動補正。
   - 未知地点について既知アンカーからの距離方程式系を解き、推定座標を算出。
3. **日本語現代語訳 (LLM Translation Engine)**
   - 歴史地理用語・官制・地名の専門用語集をプロンプトに注入し、全州府・四夷諸国の解説を現代日本語に翻訳。

---

## 📜 ライセンス・クレジット

- **底本テキスト**：『太平寰宇記』（北宋・楽史 撰）
- **基礎地理データ**：CHGIS (Harvard Yenching Institute / Fudan University)
- **開発**：Antigravity & akiasahi2008-hue

