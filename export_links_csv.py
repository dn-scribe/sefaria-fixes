#!/usr/bin/env python3
"""
CSV Export Script for Link Data
Generates CSV file from tmp_lh_links.json style files

Usage:
    python export_links_csv.py [input_file] [output_file] [--mark-status-sent]
    
Arguments:
    input_file: JSON file to read from (default: tmp_lh_links.json)
    output_file: CSV file to write to (default: tmp_lh_links.csv)
    --mark-status-sent: Update status to "sent" in input file after export

Output CSV Format:
    RefAExact, RefA Snippet (quoted), RefBExact, RefB Snippet (quoted), RefALink, RefBLink, Status
"""

import json
import csv
import argparse
import os
import sys
from typing import List, Dict, Any
from pathlib import Path


def load_json_data(file_path: str) -> List[Dict[str, Any]]:
    """Load JSON data from file."""
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


def export_to_csv(data: List[Dict[str, Any]], output_file: str, export_all: bool = False) -> int:
    """Export data to CSV format and return number of records exported."""
    csv_headers = [
        'ID',
        'RefAExact', 
        'RefA Snippet', 
        'RefBExact', 
        'RefB Snippet', 
        'RefALink', 
        'RefBLink',
        'Status'
    ]
    
    exported_count = 0
    
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile, quoting=csv.QUOTE_ALL)
            writer.writerow(csv_headers)
            
            for record in data:
                # Filter to only verified records by default
                if not export_all and record.get('Status', '') != 'verified':
                    continue
                # Extract fields with fallbacks
                ref_a_exact = record.get('RefA', '')  # Fallback to RefA if RefAExact missing
                if 'RefAExact' in record and record['RefAExact']:
                    ref_a_exact = record['RefAExact']
                
                ref_a_snippet = record.get('LHSnippet', '')
                
                ref_b_exact = record.get('RefB', '')  # Fallback to RefB if RefBExact missing
                if 'RefBExact' in record and record['RefBExact']:
                    ref_b_exact = record['RefBExact']
                
                ref_b_snippet = record.get('LMSnippet', '')
                
                ref_a_link = record.get('RefALink', '')
                if 'RefAExactLink' in record and record['RefAExactLink']:
                    ref_a_link = record['RefAExactLink']
                
                ref_b_link = record.get('RefBLink', '')
                if 'RefBExactLink' in record and record['RefBExactLink']:
                    ref_b_link = record['RefBExactLink']
                
                status = record.get('Status', 'Pending')
                record_id = record.get('ID', '') 
                
                # Write row to CSV
                writer.writerow([
                    record_id,
                    ref_a_exact,
                    ref_a_snippet, 
                    ref_b_exact,
                    ref_b_snippet,
                    ref_a_link,
                    ref_b_link,
                    status
                ])
                exported_count += 1
                
        return exported_count
        
    except Exception as e:
        print(f"Error writing to '{output_file}': {e}", file=sys.stderr)
        sys.exit(1)


def mark_status_sent(data: List[Dict[str, Any]], input_file: str, export_all: bool = False) -> int:
    """Mark exported records as 'sent' status and save back to input file."""
    updated_count = 0
    
    for record in data:
        # Only mark records that would have been exported
        if not export_all and record.get('Status', '') != 'verified':
            continue
            
        current_status = record.get('Status', 'Pending')
        if current_status != 'sent':
            record['Status'] = 'sent'
            updated_count += 1
    
    if updated_count > 0:
        try:
            # Create backup
            backup_file = f"{input_file}.backup"
            if os.path.exists(input_file):
                import shutil
                shutil.copy2(input_file, backup_file)
                print(f"Created backup: {backup_file}")
            
            # Write updated data
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
    
    args = parser.parse_args()
    
    # Set default output file if not provided
    if not args.output_file:
        input_path = Path(args.input_file)
        args.output_file = str(input_path.with_suffix('.csv'))
    
    print(f"Reading data from: {args.input_file}")
    data = load_json_data(args.input_file)
    
    if not data:
        print("Warning: No data found in input file.", file=sys.stderr)
        return
    
    print(f"Loaded {len(data)} records")
    
    # Count verified records if not exporting all
    if not args.all:
        verified_count = sum(1 for record in data if record.get('Status', '') == 'verified')
        print(f"Found {verified_count} verified records (use --all to export all records)")
    
    print(f"Exporting to CSV: {args.output_file}")
    exported_count = export_to_csv(data, args.output_file, export_all=args.all)
    print(f"Exported {exported_count} records to CSV")
    
    if args.mark_status_sent:
        print("Updating status to 'sent' for exported records...")
        updated_count = mark_status_sent(data, args.input_file, export_all=args.all)
        print(f"Updated {updated_count} records to 'sent' status")
    
    print("Export completed successfully!")


if __name__ == '__main__':
    main()