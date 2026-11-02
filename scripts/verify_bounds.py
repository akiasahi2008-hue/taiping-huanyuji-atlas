import sys, json

sys.stdout.reconfigure(encoding='utf-8')

DAO_BOUNDS = {
    'henan': (110.0, 123.0, 31.5, 38.5),
    'guanxi': (103.5, 112.5, 33.0, 42.0),
    'hedong': (110.0, 115.0, 34.5, 41.0),
    'hebei': (111.5, 124.0, 34.5, 43.5),
    'jiannan_w': (101.0, 106.0, 26.0, 33.5),
    'jiannan_e': (103.5, 108.5, 27.5, 33.0),
    'jiangnan_e': (115.5, 123.0, 23.5, 33.0),
    'jiangnan_w': (106.0, 119.0, 24.0, 32.0),
    'huainan': (113.0, 122.0, 29.5, 35.0),
    'shannan_w': (104.5, 111.0, 29.0, 34.5),
    'shannan_e': (107.5, 114.5, 29.5, 34.0),
    'longyou': (75.0, 107.5, 32.5, 46.0),
    'lingnan': (103.5, 118.0, 16.5, 26.5),
}

prefs = json.load(open('data/taiping_huanyuji_prefectures_geo.json', encoding='utf-8'))
outliers = []
for p in prefs:
    w, e, s, n = DAO_BOUNDS[p['dao_id']]
    lon, lat = p['coord']
    if not (w <= lon <= e and s <= lat <= n):
        outliers.append(f"{p['id']} ({p['dao']}): {p['name']} at {p['coord']}")

print(f"Total Prefectures: {len(prefs)}")
print(f"Outliers count: {len(outliers)}")
for o in outliers:
    print("  Outlier:", o)

# Check specifically Jiannan West
print("\n--- 劍南西道 Prefectures ---")
for p in prefs:
    if p['dao_id'] == 'jiannan_w':
        print(f"  {p['id']}: {p['name']} ({p['jun_name']}) -> Coord={p['coord']} Trilat={p['trilaterated_coord']} Err={p['trilateration_error_km']}km")

