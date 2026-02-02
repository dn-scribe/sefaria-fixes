import json

with open('tmp_lh_links.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f'Total records: {len(data)}')
print(f'\nRecord 39 (index 38):')
rec = data[38]
for k in ['RefA', 'RefBExact', 'Snippet', 'Status']:
    val = rec.get(k, 'N/A')
    if isinstance(val, str) and len(val) > 80:
        val = val[:80] + '...'
    print(f'  {k}: {val}')

# Check for duplicate keys
keys = [(r.get('RefA'), r.get('RefBExact')) for r in data]
unique_keys = set(keys)
print(f'\nTotal keys: {len(keys)}')
print(f'Unique keys: {len(unique_keys)}')
print(f'Duplicates: {len(keys) - len(unique_keys)}')

# Find records with same key as record 39
key_39 = (data[38].get('RefA'), data[38].get('RefBExact'))
matches = [i for i, r in enumerate(data) if (r.get('RefA'), r.get('RefBExact')) == key_39]
print(f'\nRecords with same key as record 39: {matches}')

# Check for empty RefBExact
empty_exact = [(i, r.get('RefA')) for i, r in enumerate(data) if not r.get('RefBExact')]
print(f'\nRecords with empty RefBExact: {len(empty_exact)}')
if empty_exact[:5]:
    print('First 5:')
    for idx, refa in empty_exact[:5]:
        print(f'  [{idx}] RefA: {refa}')
