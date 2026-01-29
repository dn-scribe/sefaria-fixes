import json
from collections import defaultdict

with open('tmp_lh_links.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Find duplicate keys
key_map = defaultdict(list)
for i, r in enumerate(data):
    key = (r.get('RefA'), r.get('RefBExact'))
    key_map[key].append(i)

duplicates = {k: v for k, v in key_map.items() if len(v) > 1}

print(f'Found {len(duplicates)} duplicate key groups:\n')
for (refa, refbexact), indices in list(duplicates.items())[:5]:
    print(f'Key: ({refa[:60]}..., {refbexact[:60] if refbexact else "EMPTY"}...)')
    print(f'  Indices: {indices}')
    for idx in indices:
        print(f'    [{idx}] Snippet: {data[idx].get("Snippet", "")[:80]}...')
        print(f'         Status: {data[idx].get("Status")}')
    print()
