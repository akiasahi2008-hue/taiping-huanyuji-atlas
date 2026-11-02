import sys, json

sys.stdout.reconfigure(encoding='utf-8')
dists = json.load(open('data/taiping_huanyuji_distances.json', encoding='utf-8'))
for e in dists:
    if e['source'] in ['霸州', '保州']:
        print(f"{e['vol']} ({e['dao']}): {e['source']} -> {e['target']} ({e['direction']} {e['distance_li']}里)")

