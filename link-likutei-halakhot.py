import json
import csv
import re
import argparse
import os
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple, Set

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

HEBREW_NIKUD_RE = re.compile(r'[\u0591-\u05C7]')
HTML_TAG_RE = re.compile(r'<[^>]+>')
NON_HEBREW_RE = re.compile(r'[^0-9\u05D0-\u05EA\s]')


def strip_nikud(text: str) -> str:
    return HEBREW_NIKUD_RE.sub('', text)


def normalize_text_for_tokens(text: str) -> str:
    text = HTML_TAG_RE.sub(' ', text or '')
    text = strip_nikud(text)
    text = (text.replace('״', '"')
                .replace('“', '"')
                .replace('”', '"')
                .replace('׳', "'"))
    text = NON_HEBREW_RE.sub(' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def tokenize(text: str) -> List[str]:
    normalized = normalize_text_for_tokens(text)
    if not normalized:
        return []
    return normalized.split()


def build_context_tokens(text: str, match_start: int, match_end: int, context_words: int,
                         symmetric: bool = True) -> Tuple[List[str], str]:
    if context_words <= 0:
        context_words = 1
    before_tokens = tokenize(text[:match_start])
    after_tokens = tokenize(text[match_end:])
    ref_tokens = tokenize(text[match_start:match_end])
    if symmetric:
        pre_target = context_words // 2
        post_target = context_words - pre_target
        pre_tokens = before_tokens[-pre_target:] if pre_target else []
        post_tokens = after_tokens[:post_target] if post_target else []
        if len(pre_tokens) < pre_target:
            missing = pre_target - len(pre_tokens)
            post_tokens = after_tokens[:post_target + missing]
        if len(post_tokens) < post_target:
            missing = post_target - len(post_tokens)
            pre_tokens = before_tokens[-(pre_target + missing):]
    else:
        pre_tokens = []
        post_tokens = after_tokens[:context_words]
    context_tokens = pre_tokens + post_tokens
    snippet_tokens = pre_tokens + ref_tokens + post_tokens
    snippet = ' '.join(snippet_tokens).strip()
    return context_tokens, snippet


@dataclass
class ParagraphEntry:
    index: int
    path: List[str]
    text: str
    tokens: List[str]
    token_set: Set[str]
    @property
    def ref_path(self) -> str:
        return '.'.join(self.path)


class LikuteiMoharanIndex:
    def __init__(self, lm_json_path: str):
        with open(lm_json_path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        root = raw.get('Likutei Moharan', {})
        part_i = {k: v for k, v in root.items() if k != 'Part II'}
        part_ii = root.get('Part II', {})
        self.parts = {
            'Likutei Moharan': self._build_part_index(part_i),
            'Part II': self._build_part_index(part_ii)
        }

    def _build_part_index(self, part_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        index = {}
        for chapter_key, chapter_node in part_data.items():
            if not str(chapter_key).isdigit():
                continue
            paragraphs = self._flatten_chapter(chapter_node)
            index[str(chapter_key)] = {
                'paragraphs': paragraphs,
                'full_text': '\n'.join(p.text for p in paragraphs),
                'structured': chapter_node
            }
        return index

    def _flatten_chapter(self, chapter_node: Any) -> List[ParagraphEntry]:
        paragraphs: List[ParagraphEntry] = []
        counter = 0

        def walk(node: Any, path: List[str]):
            nonlocal counter
            if isinstance(node, str):
                clean_text = node.strip()
                if not clean_text:
                    return
                counter += 1
                token_list = tokenize(clean_text)
                paragraphs.append(
                    ParagraphEntry(
                        index=counter,
                        path=path.copy(),
                        text=clean_text,
                        tokens=token_list,
                        token_set=set(token_list)
                    )
                )
            elif isinstance(node, dict):
                for key in sorted(node.keys(), key=self._dict_sort_key):
                    walk(node[key], path + [str(key)])
            elif isinstance(node, list):
                for idx, item in enumerate(node, 1):
                    walk(item, path + [str(idx)])

        walk(chapter_node, [])
        return paragraphs

    @staticmethod
    def _dict_sort_key(key: str) -> Tuple[int, Any]:
        if str(key).isdigit():
            return (0, int(key))
        return (1, key)

    def has_chapter(self, part: str, chapter: int) -> bool:
        return str(chapter) in self.parts.get(part, {})

    def get_chapter(self, part: str, chapter: int) -> Optional[Dict[str, Any]]:
        return self.parts.get(part, {}).get(str(chapter))


def find_k_of_n_match(paragraphs: List[ParagraphEntry], context_tokens: List[str],
                      k: int, n: int) -> Optional[Dict[str, Any]]:
    if not paragraphs or not context_tokens:
        return None
    windows: List[List[str]] = []
    for idx in range(len(context_tokens)):
        window = context_tokens[idx:idx + n]
        if len(window) >= max(k, 1):
            windows.append(window)
    if not windows:
        windows = [context_tokens]

    best_match = None
    for paragraph in paragraphs:
        if not paragraph.tokens:
            continue
        token_set = paragraph.token_set
        for window in windows:
            matched_words: List[str] = []
            unique_words = set()
            weight = 0
            run_len = 0
            run_total_len = 0
            prev_match_idx = None
            for idx, word in enumerate(window):
                if word in token_set:
                    matched_words.append(word)
                    unique_words.add(word)
                    word_len = len(word)
                    if prev_match_idx is not None and idx == prev_match_idx + 1:
                        run_len += 1
                        run_total_len += word_len
                    else:
                        if run_len > 0:
                            weight += run_total_len * run_len
                        run_len = 1
                        run_total_len = word_len
                    prev_match_idx = idx
                else:
                    if run_len > 0:
                        weight += run_total_len * run_len
                        run_len = 0
                        run_total_len = 0
                    prev_match_idx = None
            if run_len > 0:
                weight += run_total_len * run_len
            matches = len(unique_words)
            if matches > 0:
                record = {
                    'paragraph_index': paragraph.index,
                    'paragraph_text': paragraph.text,
                    'paragraph_path': paragraph.ref_path,
                    'matches': matches,
                    'match_weight': weight,
                    'matched_words': matched_words,
                    'window_size': len(window),
                    'window_text': ' '.join(window),
                    'meets_threshold': matches >= k
                }
                if best_match is None:
                    best_match = record
                else:
                    if weight > best_match.get('match_weight', 0):
                        best_match = record
                    elif weight == best_match.get('match_weight', 0):
                        if matches > best_match['matches']:
                            best_match = record
                        elif matches == best_match['matches']:
                            if record['window_size'] > best_match['window_size']:
                                best_match = record
                            elif (record['window_size'] == best_match['window_size'] and
                                  paragraph.index < best_match['paragraph_index']):
                                best_match = record
                if matches >= k:
                    return record
    return best_match


# Main extraction function
def extract_links(refs_json, output_csv, lm_json, k_of_n, n_window, context_words,
                  symmetric_context=True, output_json=None, llm_payloads_path=None,
                  update_output_json=False):
    print(f"Loading refs from {refs_json} ...")
    with open(refs_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"Loading Likutei Moharan index from {lm_json} ...")
    lm_index = LikuteiMoharanIndex(lm_json)

    results = []
    llm_requests = []

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
            refA_link = sefaria_link(refA)
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
                    refB_prefix = "Likutei Moharan%2C_Part_II"
                    lm_part = 'Part II'
                else:
                    refB_prefix = "Likutei Moharan"
                    lm_part = 'Likutei Moharan'
                if not lm_index.has_chapter(lm_part, siman_num):
                    continue  # False positive - referenced chapter doesn't exist
                refB = f"{refB_prefix}.{siman_num}"
                refB_link = sefaria_link(refB)
                chapter_data = lm_index.get_chapter(lm_part, siman_num)
                context_tokens, snippet_text = build_context_tokens(
                    node,
                    match.start(),
                    match.end(),
                    context_words,
                    symmetric=symmetric_context
                )
                deterministic_match = find_k_of_n_match(
                    chapter_data.get('paragraphs', []),
                    context_tokens,
                    k_of_n,
                    n_window
                ) if chapter_data else None
                refB_exact = ''
                refB_exact_link = ''
                refB_excerpt = ''
                match_type = 'pending_llm'
                k_n_ref = ''
                deterministic_score = ''
                llm_status = 'pending'
                matched_words_value = ''
                queue_for_llm = False

                def enqueue_llm():
                    if not chapter_data:
                        return
                    llm_requests.append({
                        'ref_a': refA,
                        'ref_a_link': refA_link,
                        'ref_b': refB,
                        'ref_b_link': refB_link,
                        'lm_part': lm_part,
                        'lm_chapter': siman_num,
                        'lh_text': snippet_text,
                        'lm_chapter_text': chapter_data.get('full_text', ''),
                        'lm_chapter_structured': chapter_data.get('structured'),
                        'prompt_instructions': (
                            "Given the Likutei Halakhot paragraph and the structured Likutei Moharan chapter, "
                            "identify the single most relevant Likutei Moharan paragraph. "
                            "Return JSON with keys \"paragraph_ref\" (full hierarchical ref such as "
                            "\"Likutei Moharan%2C_Part_II.23.1.5\"), \"paragraph_link\", \"excerpt\", and "
                            "\"confidence\" (0-1). Include the full ref path down to the paragraph number "
                            "so it can be opened directly on Sefaria. Example outputs:\n"
                            "Example 1: {\"paragraph_ref\": \"Likutei Moharan.61.1.3\", "
                            "\"paragraph_link\": \"https://www.sefaria.org.il/Likutei_Moharan.61.1.3\", "
                            "\"excerpt\": \"הינו, כי כל הלמודים...\", \"confidence\": 0.91}\n"
                            "Example 2: {\"paragraph_ref\": \"Likutei Moharan%2C_Part_II.23.1.5\", "
                            "\"paragraph_link\": \"https://www.sefaria.org.il/Likutei_Moharan,_Part_II.23.1.5\", "
                            "\"excerpt\": \"וזה בחינת ששון ושמחה...\", \"confidence\": 0.87}"
                        )
                    })

                if deterministic_match:
                    matches = deterministic_match['matches']
                    window_size = deterministic_match['window_size']
                    k_n_ref = f"{matches}/{window_size} words match (window=\"{deterministic_match['window_text']}\")"
                    deterministic_score = f"{matches}/{window_size}"
                    matched_words_value = ' '.join(deterministic_match.get('matched_words', []))
                    refB_excerpt = deterministic_match['paragraph_text']
                    paragraph_index = deterministic_match['paragraph_index']
                    paragraph_path = deterministic_match['paragraph_path'] or str(paragraph_index)
                    refB_exact = f"{refB}.{paragraph_path}"
                    refB_exact_link = sefaria_link(refB_exact)
                    if deterministic_match.get('meets_threshold'):
                        match_type = 'k_of_n'
                        llm_status = 'not_needed'
                    else:
                        queue_for_llm = True
                else:
                    queue_for_llm = True

                if queue_for_llm:
                    enqueue_llm()
                result_row = {
                    'RefA': refA,
                    'RefALink': refA_link,
                    'RefB': refB,
                    'RefBLink': refB_link,
                    'Snippet': snippet_text,
                    'RefBExact': refB_exact,
                    'RefBExactLink': refB_exact_link,
                    'RefBExcerpt': refB_excerpt,
            'MatchType': match_type,
            'k_n_ref': k_n_ref,
            'MatchedWords': matched_words_value,
            'DeterministicScore': deterministic_score,
                    'LLMStatus': llm_status,
                    'LLMParagraph': '',
                    'LLMConfidence': '',
                    'LLMExcerpt': '',
                    'Status': 'Pending'
                }
                results.append(result_row)
                found_links += 1

            # Process מאמר with explicit סימן (e.g., "(בסימן ח')")
            for match in maamar_with_siman_matches:
                siman_text = match.group(1).strip()
                siman_clean = siman_text.replace('(', '').replace(')', '').strip()
                siman_num = hebrew_gematria(siman_clean)
                refB = f"Likutei Moharan.{siman_num}"
                _, snippet_text = build_context_tokens(
                    node,
                    match.start(),
                    match.end(),
                    context_words,
                    symmetric=symmetric_context
                )

                results.append({
                    'RefA': refA,
                    'RefALink': refA_link,
                    'RefB': refB,
                    'RefBLink': sefaria_link(refB),
                    'Snippet': snippet_text,
                    'RefBExact': '',
                    'RefBExactLink': '',
                    'RefBExcerpt': '',
                    'MatchType': 'maamar_with_siman',
                    'k_n_ref': '',
                    'DeterministicScore': '',
                    'LLMStatus': 'pending',
                    'LLMParagraph': '',
                    'LLMConfidence': '',
                    'LLMExcerpt': ''
                })
                found_links += 1

            # Process מאמר without סימן (gets placeholder)
            # Skip positions already matched by maamar_with_siman
            maamar_with_siman_positions = {match.start() for match in maamar_with_siman_matches}
            for match in maamar_matches:
                if match.start() in maamar_with_siman_positions:
                    continue
                _, snippet_text = build_context_tokens(
                    node,
                    match.start(),
                    match.end(),
                    context_words,
                    symmetric=symmetric_context
                )

                results.append({
                    'RefA': refA,
                    'RefALink': refA_link,
                    'RefB': "Likutei Moharan.[PLACEHOLDER]",
                    'RefBLink': sefaria_link("Likutei Moharan.[PLACEHOLDER]"),
                    'Snippet': snippet_text,
                    'RefBExact': '',
                    'RefBExactLink': '',
                    'RefBExcerpt': '',
                    'MatchType': 'maamar_without_siman',
                    'k_n_ref': '',
                    'DeterministicScore': '',
                    'LLMStatus': 'pending',
                    'LLMParagraph': '',
                    'LLMConfidence': '',
                    'LLMExcerpt': ''
                })
                found_links += 1
        return found_links

    print("Processing refs recursively ...")
    total_links = walk_refs(data, [])
    print(f"Found {total_links} links in total.")

    print(f"Writing {len(results)} links to {output_csv} ...")
    fieldnames = [
        'RefA', 'RefALink', 'RefB', 'RefBLink', 'Snippet',
        'MatchType', 'k_n_ref', 'MatchedWords', 'DeterministicScore',
        'RefBExact', 'RefBExactLink', 'RefBExcerpt',
        'LLMStatus', 'LLMParagraph', 'LLMConfidence', 'LLMExcerpt',
        'Status'
    ]
    with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for row in results:
            writer.writerow(row)
    if output_json:
        print(f"Writing JSON dump to {output_json} ...")
        if update_output_json and os.path.exists(output_json):
            with open(output_json, 'r', encoding='utf-8') as f:
                existing = json.load(f)
            existing_map = {(row.get('RefA'), row.get('RefBExact')): i for i, row in enumerate(existing)}
            for row in results:
                key = (row.get('RefA'), row.get('RefBExact'))
                idx = existing_map.get(key)
                if idx is not None:
                    existing_status = existing[idx].get('Status', 'Pending')
                    if existing_status != 'Pending':
                        row['Status'] = existing_status
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
    if llm_payloads_path:
        print(f"Writing {len(llm_requests)} pending LLM payloads to {llm_payloads_path} ...")
        with open(llm_payloads_path, 'w', encoding='utf-8') as f:
            json.dump(llm_requests, f, ensure_ascii=False, indent=2)
    print("Done.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract Likutei Halakhot links to Likutei Moharan and export to CSV.")
    parser.add_argument('--refs-json', type=str, default='data/Likutei_Halakhot_refs.json', help='Input refs JSON file')
    parser.add_argument('--output-csv', type=str, default='data/likutei-halakhot-links.csv', help='Output CSV file')
    parser.add_argument('--lm-json', type=str, default='data/Likutei_Moharan_refs.json', help='Likutei Moharan refs JSON file')
    parser.add_argument('--match-k', type=int, default=4, help='Minimum overlapping words for k-of-n search')
    parser.add_argument('--match-n', type=int, default=7, help='Window size (n) for k-of-n search')
    parser.add_argument('--context-words', type=int, default=40, help='Maximum LH words to use around the reference for matching')
    parser.add_argument('--no-symmetric-context', action='store_true', help='Disable symmetric context (use only words after the ref)')
    parser.add_argument('--output-json', type=str, help='Optional JSON dump of the link results')
    parser.add_argument('--update-output-json', action='store_true', help='Only overwrite rows with Status="Pending" when writing output JSON')
    parser.add_argument('--llm-payloads-json', type=str, help='Optional path to write pending LLM payloads JSON')
    args = parser.parse_args()
    extract_links(
        args.refs_json,
        args.output_csv,
        args.lm_json,
        args.match_k,
        args.match_n,
        args.context_words,
        symmetric_context=not args.no_symmetric_context,
        output_json=args.output_json,
        llm_payloads_path=args.llm_payloads_json,
        update_output_json=args.update_output_json
    )
