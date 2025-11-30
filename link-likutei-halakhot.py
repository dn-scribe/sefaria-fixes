import json
import csv
import re
import argparse

# Sefaria webapp link generator
def sefaria_link(ref):
    return f"https://www.sefaria.org.il/{ref.replace(' ', '_').replace('%2C', ',')}"

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
# Hebrew letters: \u05D0-\u05EA
# Nikud (vowel points): \u0591-\u05C7
# Pattern allows nikud between letters
SIMAN_PATTERN = r'(?:[\u05D0-\u05EA\u0591-\u05C7]+\s+[\u05D0-\u05EA\u0591-\u05C7]+\s+)?[\u05D0-\u05EA\u0591-\u05C7]*ס[\u0591-\u05C7]*י[\u0591-\u05C7]*מ[\u0591-\u05C7]*ן[\u0591-\u05C7]*\s*([\u05D0-\u05EA\u0591-\u05C7"׳״()]+)'
MAAMAR_PATTERN = r'ע[\u0591-\u05C7]*ל[\u0591-\u05C7]*-[\u0591-\u05C7]*פ[\u0591-\u05C7]*י[\u0591-\u05C7]*\s+ה[\u0591-\u05C7]*מ[\u0591-\u05C7]*א[\u0591-\u05C7]*מ[\u0591-\u05C7]*ר[\u0591-\u05C7]*\s*["\u201c\u201d\u05f4][^"\u201c\u201d\u05f4]*["\u201c\u201d\u05f4]'
MAAMAR_WITH_SIMAN_PATTERN = r'ע[\u0591-\u05C7]*ל[\u0591-\u05C7]*-[\u0591-\u05C7]*פ[\u0591-\u05C7]*י[\u0591-\u05C7]*\s+ה[\u0591-\u05C7]*מ[\u0591-\u05C7]*א[\u0591-\u05C7]*מ[\u0591-\u05C7]*ר[\u0591-\u05C7]*\s*["\u201c\u201d\u05f4][^"\u201c\u201d\u05f4]*["\u201c\u201d\u05f4]\s*\(ב[\u0591-\u05C7]*ס[\u0591-\u05C7]*י[\u0591-\u05C7]*מ[\u0591-\u05C7]*ן[\u0591-\u05C7]*\s*([\u05D0-\u05EA\u0591-\u05C7"׳״\']+)\)'

# Main extraction function
def extract_links(refs_json, output_csv):
    print(f"Loading refs from {refs_json} ...")
    with open(refs_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    results = []
    def build_refA(ref_path):
        # Separate text parts from numeric parts
        # Join text parts with %2C_, then append numeric parts with dots
        if not ref_path:
            return ''
        
        text_parts = []
        numeric_parts = []
        
        # Collect all parts, separating text from numeric
        for part in ref_path:
            if part.isdigit():
                numeric_parts.append(part)
            else:
                # If we have accumulated numeric parts, this is a new text section
                # so we should have processed them already (shouldn't happen with correct structure)
                text_parts.append(part)
        
        # Build reference: text parts joined by %2C_, then numeric parts joined by dots
        if text_parts and numeric_parts:
            return '%2C_'.join(text_parts) + '.' + '.'.join(numeric_parts)
        elif text_parts:
            return '%2C_'.join(text_parts)
        else:
            return '.'.join(numeric_parts)

    def walk_refs(node, ref_path):
        found_links = 0
        if isinstance(node, dict):
            for k, v in node.items():
                found_links += walk_refs(v, ref_path + [str(k)])
        elif isinstance(node, list):
            for idx, item in enumerate(node, 1):
                found_links += walk_refs(item, ref_path + [str(idx)])
        elif isinstance(node, str):
            refA = build_refA(ref_path)
            siman_matches = list(re.finditer(SIMAN_PATTERN, node))
            maamar_with_siman_matches = list(re.finditer(MAAMAR_WITH_SIMAN_PATTERN, node))
            maamar_matches = list(re.finditer(MAAMAR_PATTERN, node))
            
            for match in siman_matches:
                # Check if "סעיף" appears within 2-3 words after "סימן" (indicates Shulchan Aruch citation)
                # Extract text after the match (next ~50 characters to check for "סעיף")
                check_start = match.start()
                check_end = min(len(node), match.end() + 50)
                check_text = node[check_start:check_end]
                # Remove nikud for matching
                check_text_no_nikud = re.sub(r'[\u0591-\u05C7]', '', check_text)
                # Count words after "סימן" - if "סעיף" appears within 2-3 words, skip this match
                words_after_siman = check_text_no_nikud.split()[:5]  # Check first 5 words
                if any('סעיף' in word for word in words_after_siman):
                    continue  # Skip this match - it's a Shulchan Aruch citation
                
                siman_raw = match.group(1)
                siman_clean = siman_raw.replace('(', '').replace(')', '').strip()
                siman_num = hebrew_gematria(siman_clean)
                # Use Part II if the reference contains 'תנינא' or 'תניינא' (strip diacritics for matching)
                # Get context around the match for checking
                context_start = max(0, match.start() - 50)
                context_end = min(len(node), match.end() + 50)
                context = node[context_start:context_end]
                # Remove all diacritics (nikud) for matching
                context_no_diacritics = re.sub(r'[\u0591-\u05C7]', '', context)
                # Check if 'תנינא' or 'תניינא' appears in the context
                if re.search(r'תנ[י]?[י]?נא', context_no_diacritics):
                    refB = f"Likutei Moharan%2C_Part_II.{siman_num}"
                else:
                    refB = f"Likutei Moharan.{siman_num}"
                results.append({
                    'RefA': refA,
                    'RefALink': sefaria_link(refA),
                    'RefB': refB,
                    'RefBLink': sefaria_link(refB),
                    'Snippet': re.sub(r'[\u0591-\u05C7]', '', node[max(0, match.start()-80):match.end()+100])
                })
                found_links += 1
            
            # Process מאמר with explicit סימן (e.g., "(בסימן ח')")
            for match in maamar_with_siman_matches:
                siman_text = match.group(1).strip()
                siman_clean = siman_text.replace('(', '').replace(')', '').strip()
                siman_num = hebrew_gematria(siman_clean)
                refB = f"Likutei Moharan.{siman_num}"
                
                results.append({
                    'RefA': refA,
                    'RefALink': sefaria_link(refA),
                    'RefB': refB,
                    'RefBLink': sefaria_link(refB),
                    'Snippet': re.sub(r'[\u0591-\u05C7]', '', node[max(0, match.start()-80):match.end()+80])
                })
                found_links += 1
            
            # Process מאמר without סימן (gets placeholder)
            # Skip positions already matched by maamar_with_siman
            maamar_with_siman_positions = {match.start() for match in maamar_with_siman_matches}
            for match in maamar_matches:
                if match.start() in maamar_with_siman_positions:
                    continue
                    
                results.append({
                    'RefA': refA,
                    'RefALink': sefaria_link(refA),
                    'RefB': "Likutei Moharan.[PLACEHOLDER]",
                    'RefBLink': sefaria_link("Likutei Moharan.[PLACEHOLDER]"),
                    'Snippet': re.sub(r'[\u0591-\u05C7]', '', node[max(0, match.start()-80):match.end()+80])
                })
                found_links += 1
        return found_links

    print("Processing refs recursively ...")
    total_links = walk_refs(data, [])
    print(f"Found {total_links} links in total.")

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
