import json
import csv
import argparse


def hebrew_gematria(hebrew_str):
    """
    Convert a Hebrew string (letters) to its gematria (numerical value).
    Handles standard and final letters, ignores non-Hebrew chars.
    """
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


def get_chayei_links(filename='data/Chayei_Moharan.json'):
    """
    Load Chayei Moharan links from a JSON file.
    Returns a list of links.
    """
    def get_link_from_section(section, sec_num):
        """
        Extract the text בסימן ... from a section if it exists.
        """
        import re
        if not section:
            return None
        links = []
        for line in section[0].splitlines():

            if "סִימָן" in line:
                # Find all occurrences of 'סִימָן' and what follows
                # Book number: if word before 'סִימָן' ends with תִנְיָנָא, else 1
                siman_pattern = r'(?:\b(\S*תִנְיָנָא)\s+)?(סִימָן\s*(\([^)]+\)|[\u0590-\u05FF"׳״]+))'
                for match in re.finditer(siman_pattern, line):
                    book_number = 2 if match.group(1) else 1
                    siman_full = match.group(2)
                    para_number = match.group(3)
                    # Remove parentheses if present
                    para_clean = para_number.replace('(', '').replace(')', '').strip()
                    para_numerical = hebrew_gematria(para_clean)
                    # Create snippet: 10 words before, the found text, 10 words after
                    words = line.split()
                    # Find the index of the first word of siman_full
                    siman_words = siman_full.split()
                    try:
                        # Find the start index of siman_full in words
                        for i in range(len(words)):
                            if words[i:i+len(siman_words)] == siman_words:
                                start = i
                                break
                        else:
                            start = 0  # fallback if not found
                        end = start + len(siman_words)
                        snippet_start = max(0, start - 10)
                        snippet_end = min(len(words), end + 10)
                        snippet = ' '.join(words[snippet_start:snippet_end])
                    except Exception:
                        snippet = line
                    links.append({
                        'original_paragraph': str(sec_num),
                        'book_number': book_number,
                        'para_number': para_number,
                        'para_numerical': para_numerical,
                        'snippet': snippet
                    })
        return links if links else None

    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)

    sections = data["versions"][0]["text"]
    links = []
    sec_num = 0
    for sec in sections:
        sec_num += 1
        link = get_link_from_section(sec, sec_num)
        if link:
            links.extend(link)
            print(f"Section {sec_num}: Found link: {link}")
        else:
            print(f"Section {sec_num}: No link found.")
    return links

                    siman_pattern = r'(?:\b(\S*תִנְיָנָא)\s+)?(סִימָן\s*(\([^)]+\)|[\u0590-\u05FF"׳״]+))'
                    for match in re.finditer(siman_pattern, line):
                        book_number = 2 if match.group(1) else 1
                        siman_full = match.group(2)
                        para_number = match.group(3)
                        para_clean = para_number.replace('(', '').replace(')', '').strip()
                        para_numerical = hebrew_gematria(para_clean)
                        # Find snippet around the specific match
                        # Get character indices of the match
                        match_start, match_end = match.span(2)
                        # Get words and their character positions
                        words = line.split()
                        char_indices = []
                        idx = 0
                        for w in words:
                            char_indices.append(idx)
                            idx += len(w) + 1  # +1 for the space
                        # Find the word index where the match starts
                        match_word_start = 0
                        for i, cidx in enumerate(char_indices):
                            if cidx >= match_start:
                                match_word_start = i
                                break
                        match_word_end = match_word_start + len(siman_full.split())
                        snippet_start = max(0, match_word_start - 10)
                        snippet_end = min(len(words), match_word_end + 10)
                        snippet = ' '.join(words[snippet_start:snippet_end])
                        links.append({
                            'original_paragraph': str(sec_num),
                            'book_number': book_number,
                            'para_number': para_number,
                            'para_numerical': para_numerical,
                            'snippet': snippet
                        })