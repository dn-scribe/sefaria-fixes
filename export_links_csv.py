#!/usr/bin/env python3
"""
CSV Export Script for Link Data
Generates CSV file from tmp_lh_links.json style files

Usage:
    python export_links_csv.py [input_file] [output_file] [--mark-status-sent]

Arguments:
    input_file: JSON file to read from (default: tmp_lh_links.json)
    output_file: CSV file to write to (default: input_file with .csv extension)
    --mark-status-sent: Update status to "sent" in input file after export
    --check-existing: Filter out pairs already linked in Sefaria (requires network)

Output CSV Format:
    ID, RefAExact, RefA Snippet, RefBExact, RefB Snippet, RefALink, RefBLink, Status
"""

import json
import csv
import argparse
import os
import re
import sys
import urllib.parse
from typing import List, Dict, Any, Set, Tuple
from pathlib import Path


def normalize_ref(ref: str) -> str:
    """Convert URL-encoded ref to human-readable form.

    e.g. Likutei Halakhot%2C_Orach Chaim%2C_Laws of Morning Conduct.1.1.2
      -> Likutei Halakhot, Orach Chaim, Laws of Morning Conduct 1:1:2
    """
    decoded = urllib.parse.unquote(ref).replace('_', ' ')
    parts = decoded.split('.')
    text_parts: List[str] = []
    num_parts: List[str] = []
    collecting_nums = False
    for p in parts:
        if re.match(r'^\d+$', p):
            collecting_nums = True
        if collecting_nums:
            num_parts.append(p)
        else:
            text_parts.append(p)
    text = '.'.join(text_parts)
    if num_parts:
        return text + ' ' + ':'.join(num_parts)
    return text


def short_snippet(snippet: str, matched_words: str, window: int = 18) -> str:
    """Return ±window words around the tightest cluster of matched words in snippet."""
    if not snippet:
        return ''
    words = snippet.split()
    if len(words) <= window * 2:
        return snippet

    if not matched_words:
        result = ' '.join(words[:window])
        if len(words) > window:
            result += '...'
        return result

    match_list = matched_words.split()

    # Build list of all positions where any matched word appears
    all_positions: List[int] = []
    for mw in match_list:
        clean_mw = re.sub(r'[^\w]', '', mw)
        if not clean_mw:
            continue
        for i, w in enumerate(words):
            clean_w = re.sub(r'[^\w]', '', w)
            if clean_mw in clean_w or clean_w in clean_mw:
                all_positions.append(i)

    if not all_positions:
        result = ' '.join(words[:window])
        if len(words) > window:
            result += '...'
        return result

    # Find tightest cluster: sliding window of len(match_list) positions
    all_positions.sort()
    n = len(match_list)
    best_center = all_positions[0]
    best_span = float('inf')
    for i in range(len(all_positions) - n + 1):
        span = all_positions[min(i + n - 1, len(all_positions) - 1)] - all_positions[i]
        if span < best_span:
            best_span = span
            best_center = (all_positions[i] + all_positions[min(i + n - 1, len(all_positions) - 1)]) // 2

    start = max(0, best_center - window)
    end = min(len(words), best_center + window + 1)
    result = ' '.join(words[start:end])
    if start > 0:
        result = '...' + result
    if end < len(words):
        result = result + '...'
    return result


def fetch_existing_sefaria_links(refs: List[str]) -> Set[Tuple[str, str]]:
    """Fetch existing links from Sefaria API for given refs.

    Returns set of (normalized_ref_a, normalized_ref_b) pairs.
    """
    import urllib.request
    existing: Set[Tuple[str, str]] = set()
    seen_refs: Set[str] = set()

    for ref in refs:
        if ref in seen_refs:
            continue
        seen_refs.add(ref)

        # Build API URL - decode ref and replace spaces with underscores
        api_ref = urllib.parse.unquote(ref).replace(' ', '_')
        url = f"https://www.sefaria.org/api/links/{api_ref}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                links_data = json.loads(resp.read().decode('utf-8'))
            if isinstance(links_data, list):
                norm_a = normalize_ref(ref)
                for link in links_data:
                    ref_b = link.get('ref', '') or link.get('anchorRef', '')
                    if ref_b:
                        existing.add((norm_a, normalize_ref(ref_b)))
        except Exception as e:
            print(f"  Warning: could not fetch links for {ref}: {e}", file=sys.stderr)

    return existing


def load_json_data(file_path: str) -> List[Dict[str, Any]]:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in '{file_path}': {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading '{file_path}': {e}", file=sys.stderr)
        sys.exit(1)


def export_to_csv(
    data: List[Dict[str, Any]],
    output_file: str,
    export_all: bool = False,
    check_existing: bool = False,
) -> int:
    """Export data to CSV and return number of records exported."""
    csv_headers = [
        'ID',
        'RefAExact',
        'RefA Snippet',
        'RefBExact',
        'RefB Snippet',
        'RefALink',
        'RefBLink',
        'Status',
        'Comment'
    ]

    # Build candidate records first (apply status filter)
    candidates = [r for r in data if export_all or r.get('Status', '') == 'verified']

    # Fetch existing Sefaria links if requested
    existing_pairs: Set[Tuple[str, str]] = set()
    if check_existing:
        print("Fetching existing Sefaria links (this may take a while)...")
        all_refs = list({r.get('RefA', '') for r in candidates if r.get('RefA')})
        existing_pairs = fetch_existing_sefaria_links(all_refs)
        print(f"Found {len(existing_pairs)} existing Sefaria link pairs")

    exported_count = 0
    seen_pairs: Set[Tuple[str, str]] = set()
    skipped_dup = 0
    skipped_existing = 0

    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile, quoting=csv.QUOTE_ALL)
            writer.writerow(csv_headers)

            for record in candidates:
                ref_a_raw = record.get('RefA', '')
                if 'RefAExact' in record and record['RefAExact']:
                    ref_a_raw = record['RefAExact']

                ref_b_raw = record.get('RefB', '')
                if 'RefBExact' in record and record['RefBExact']:
                    ref_b_raw = record['RefBExact']

                ref_a_norm = normalize_ref(ref_a_raw)
                ref_b_norm = normalize_ref(ref_b_raw)

                # Deduplicate
                pair_key = (ref_a_norm, ref_b_norm)
                if pair_key in seen_pairs:
                    skipped_dup += 1
                    continue
                seen_pairs.add(pair_key)

                # Filter against existing Sefaria links
                if check_existing and pair_key in existing_pairs:
                    skipped_existing += 1
                    continue

                ref_a_snippet = short_snippet(
                    record.get('LHSnippet', ''),
                    record.get('MatchedWords', '')
                )
                ref_b_snippet = record.get('LMSnippet', '')

                ref_a_link = record.get('RefALink', '')
                if 'RefAExactLink' in record and record['RefAExactLink']:
                    ref_a_link = record['RefAExactLink']

                ref_b_link = record.get('RefBLink', '')
                if 'RefBExactLink' in record and record['RefBExactLink']:
                    ref_b_link = record['RefBExactLink']

                status = record.get('Status', 'Pending')
                record_id = record.get('ID', '')
                comment = record.get('Comment', '')

                writer.writerow([
                    record_id,
                    ref_a_norm,
                    ref_a_snippet,
                    ref_b_norm,
                    ref_b_snippet,
                    ref_a_link,
                    ref_b_link,
                    status,
                    comment
                ])
                exported_count += 1

        if skipped_dup:
            print(f"Skipped {skipped_dup} duplicate pairs")
        if skipped_existing:
            print(f"Skipped {skipped_existing} pairs already in Sefaria")
        return exported_count

    except Exception as e:
        print(f"Error writing to '{output_file}': {e}", file=sys.stderr)
        sys.exit(1)


def mark_status_sent(data: List[Dict[str, Any]], input_file: str, export_all: bool = False) -> int:
    updated_count = 0

    for record in data:
        if not export_all and record.get('Status', '') != 'verified':
            continue
        if record.get('Status', 'Pending') != 'sent':
            record['Status'] = 'sent'
            updated_count += 1

    if updated_count > 0:
        try:
            backup_file = f"{input_file}.backup"
            if os.path.exists(input_file):
                import shutil
                shutil.copy2(input_file, backup_file)
                print(f"Created backup: {backup_file}")

            with open(input_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"Error updating '{input_file}': {e}", file=sys.stderr)
            sys.exit(1)

    return updated_count


def main():
    parser = argparse.ArgumentParser(
        description='Export link data to CSV format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python export_links_csv.py
    python export_links_csv.py --all
    python export_links_csv.py data.json output.csv
    python export_links_csv.py tmp_lh_links.json --mark-status-sent
    python export_links_csv.py tmp_lh_links.json --check-existing
        """
    )

    parser.add_argument(
        'input_file',
        nargs='?',
        default='tmp_lh_links.json',
        help='Input JSON file (default: tmp_lh_links.json)'
    )

    parser.add_argument(
        'output_file',
        nargs='?',
        help='Output CSV file (default: input_file with .csv extension)'
    )

    parser.add_argument(
        '--mark-status-sent',
        action='store_true',
        help='Update status to "sent" in input file after export'
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='Export all records (default: only verified records)'
    )

    parser.add_argument(
        '--check-existing',
        action='store_true',
        help='Filter out pairs already linked in Sefaria (requires network)'
    )

    args = parser.parse_args()

    if not args.output_file:
        input_path = Path(args.input_file)
        args.output_file = str(input_path.with_suffix('.csv'))

    print(f"Reading data from: {args.input_file}")
    data = load_json_data(args.input_file)

    if not data:
        print("Warning: No data found in input file.", file=sys.stderr)
        return

    print(f"Loaded {len(data)} records")

    if not args.all:
        verified_count = sum(1 for r in data if r.get('Status', '') == 'verified')
        print(f"Found {verified_count} verified records (use --all to export all records)")

    print(f"Exporting to CSV: {args.output_file}")
    exported_count = export_to_csv(
        data, args.output_file,
        export_all=args.all,
        check_existing=args.check_existing,
    )
    print(f"Exported {exported_count} records to CSV")

    if args.mark_status_sent:
        print("Updating status to 'sent' for exported records...")
        updated_count = mark_status_sent(data, args.input_file, export_all=args.all)
        print(f"Updated {updated_count} records to 'sent' status")

    print("Export completed successfully!")


if __name__ == '__main__':
    main()
