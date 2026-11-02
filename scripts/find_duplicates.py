import sys, json, collections
sys.stdout.reconfigure(encoding='utf-8')
prefs = json.load(open('data/taiping_huanyuji_prefectures.json', encoding='utf-8'))
counts = collections.Counter(p['name'] for p in prefs)
dups = [name for name, cnt in counts.items() if cnt > 1]
print('Duplicates:', dups)
for p in prefs:
    if p['name'] in dups:
        print(f"{p['id']} ({p['dao']}): {p['name']} ({p['jun_name']}) {p['seat']}")
