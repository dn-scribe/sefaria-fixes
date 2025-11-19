import json
import csv
import re
import argparse

# Sefaria webapp link generator
def sefaria_link(ref):
    return f"https://www.sefaria.org/{ref.replace(' ', '_').replace('%2C', ',')}"

# Gematria function (copied from link-likutei-chayei.py)
def hebrew_gematria(hebrew_str):
    gematria_map = {
        'א': 1, 'ב': 2, 'ג': 3, 'ד': 4, 'ה': 5, 'ו': 6, 'ז': 7, 'ח': 8, 'ט': 9,
        'י': 10, 'כ': 20, 'ך': 20, 'ל': 30, 'מ': 40, 'ם': 40, 'נ': 50, 'ן': 50,
        'ס': 60, 'ע': 70, 'פ': 80, 'ף': 80, 'צ': 90, 'ץ': 90, 'ק': 100, 'ר': 200,
        'ש': 300, 'ת': 400, '"': 0, '׳': 0, '״': 0, "'": 0, '(': 0, ')': 0
    }
    total = 0
    for c in hebrew_str:
        total += gematria_map.get(c, 0)
    return total

# Patterns for Likutei Moharan links in Likutei Halakhot
SIMAN_PATTERN = r'(?:בְּלִקּוּטֵי\s+תִּנְיָנָא\s+)?סִימָן\s*([\u0590-\u05FF"׳״()]+)'
MAAMAR_PATTERN = r'עַל-פִּי\s+הַמַּאֲמָר\s*([\u0590-\u05FF"׳״()]+)'

# Main extraction function
def extract_links(refs_json, output_csv):
    print(f"Loading refs from {refs_json} ...")
    with open(refs_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    results = []
    total_refs = len(data)
    print(f"Processing {total_refs} refs ...")
    for idx, (refA, text) in enumerate(data.items(), 1):
        siman_matches = list(re.finditer(SIMAN_PATTERN, text))
        maamar_matches = list(re.finditer(MAAMAR_PATTERN, text))
        found_links = 0
        for match in siman_matches:
            siman_raw = match.group(1)
            siman_clean = siman_raw.replace('(', '').replace(')', '').strip()
            siman_num = hebrew_gematria(siman_clean)
            if match.group(0).startswith('בְּלִקּוּטֵי תִּנְיָנָא'):
                refB = f"Likutei Moharan%2CPart_II.{siman_num}"
            else:
                refB = f"Likutei Moharan.{siman_num}"
            results.append({
                'RefA': refA,
                'RefALink': sefaria_link(refA),
                'RefB': refB,
                'RefBLink': sefaria_link(refB),
                'Snippet': text[max(0, match.start()-30):match.end()+30]
            })
            found_links += 1
        for match in maamar_matches:
            maamar_raw = match.group(1)
            maamar_clean = maamar_raw.replace('(', '').replace(')', '').strip()
            maamar_num = hebrew_gematria(maamar_clean)
            refB = f"Likutei Moharan.{maamar_num}"
            results.append({
                'RefA': refA,
                'RefALink': sefaria_link(refA),
                'RefB': refB,
                'RefBLink': sefaria_link(refB),
                'Snippet': text[max(0, match.start()-30):match.end()+30]
            })
            found_links += 1
        if found_links:
            print(f"[{idx}/{total_refs}] {refA}: Found {found_links} link(s)")
        else:
            print(f"[{idx}/{total_refs}] {refA}: No links found")

    print(f"Writing {len(results)} links to {output_csv} ...")
    with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=['RefA', 'RefALink', 'RefB', 'RefBLink', 'Snippet'])
        writer.writeheader()
        for row in results:
            writer.writerow(row)
    print("Done.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract Likutei Halakhot links to Likutei Moharan and export to CSV.")
    parser.add_argument('--refs-json', type=str, default='data/Likutei_Halakhot_refs.json', help='Input refs JSON file')
    parser.add_argument('--output-csv', type=str, default='data/likutei-halakhot-links.csv', help='Output CSV file')
    args = parser.parse_args()
    extract_links(args.refs_json, args.output_csv)
