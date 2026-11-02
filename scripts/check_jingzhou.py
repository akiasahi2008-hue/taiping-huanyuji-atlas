import sys, json

sys.stdout.reconfigure(encoding='utf-8')
prefs = json.load(open('data/taiping_huanyuji_prefectures_geo.json', encoding='utf-8'))
for p in prefs:
    if p['name'] == '静州':
        print(f"ID={p['id']}, Name={p['name']}, Dao={p['dao']}, Coord={p['coord']}, Trilat={p['trilaterated_coord']}, Err={p['trilateration_error_km']}km, Source={p['coord_source']}")

