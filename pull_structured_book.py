import requests
import json
import re

class SefariaBookStructure:
    def save_structure_json(self, filename):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.structure, f, ensure_ascii=False, indent=2)
    BASE_URL = "https://www.sefaria.org/api/v2/index/"

    @staticmethod
    def remove_nikud(text):
        """Remove Hebrew nikud (vowel points) from text."""
        if not text:
            return text
        # Hebrew nikud Unicode range: \u0591-\u05C7
        # This includes cantillation marks, vowel points, and other diacriticals
        nikud_pattern = r'[\u0591-\u05C7]'
        return re.sub(nikud_pattern, '', text)

    def __init__(self, book_title, with_nikud=False):
        self.book_title = book_title
        self.structure = None
        self.with_nikud = with_nikud

    def fetch_structure(self):
        url = f"{self.BASE_URL}{self.book_title.replace(' ', '_')}"
        response = requests.get(url)
        response.raise_for_status()
        self.structure = response.json()
        # Always save structure after fetching
        structure_path = f"data/{self.book_title.replace(' ', '_')}_structure.json"
        with open(structure_path, "w", encoding="utf-8") as f:
            json.dump(self.structure, f, ensure_ascii=False, indent=2)
        return self.structure

    def generate_refs(self, max_refs=None, language="he"):
        if not self.structure:
            self.fetch_structure()
        refs = {}
        title = self.structure.get("title")
        schema = self.structure.get("schema", {})
        if not schema:
            print("Warning: No schema found in structure. Check the book's index API response.")
            return refs
        api_call_count = [0]  # mutable counter for API calls

        def get_text_length(ref, max_refs=None, api_call_count=None):
            # Check if we've reached the API call limit
            if max_refs is not None and api_call_count[0] >= max_refs:
                print(f"  [LIMIT] Reached max API calls ({max_refs}). Skipping: {ref}")
                return None
            
            url = f"https://www.sefaria.org/api/texts/{ref.replace(' ', '_')}?context=0"
            print(f"  [API {api_call_count[0] + 1}/{max_refs if max_refs else '∞'}] Fetching: {url}")
            api_call_count[0] += 1
            try:
                response = requests.get(url)
                response.raise_for_status()
                data = response.json()
                if language == "en":
                    text = data.get("text", [])
                else:
                    text = data.get("he", [])
                if not text:
                    print(f"  [WARN] No text found for ref: {ref} (language: {language})")
                return text
            except Exception as e:
                print(f"  [ERROR] Exception fetching {url}: {e}")
                return []

        def get_section_key(node):
            return node.get("title") or node.get("key")

        def build_hierarchy(section_names, text_segment, depth=0, parent_keys=None):
            if parent_keys is None:
                parent_keys = []
            
            # Base case: we've processed all section names, return the actual text
            if depth >= len(section_names):
                # If it's a list of strings (actual text content), convert to dict with numbered keys
                if isinstance(text_segment, list) and text_segment and isinstance(text_segment[0], str):
                    result = {}
                    for i, text_item in enumerate(text_segment, 1):
                        # Remove nikud if requested
                        if not self.with_nikud and isinstance(text_item, str):
                            text_item = self.remove_nikud(text_item)
                        result[str(i)] = text_item
                    print(f"    Text segments: {len(text_segment)}")
                    return result
                # If it's already structured or empty, return as is
                return text_segment
            
            # Recursive case: process the hierarchy level by level
            if isinstance(text_segment, list):
                result = {}
                for i, sub_segment in enumerate(text_segment, 1):
                    key = str(i)
                    current_keys = parent_keys + [key]
                    print(f"    {section_names[depth]} {key}")
                    # Process sub_segment recursively
                    processed = build_hierarchy(section_names, sub_segment, depth + 1, current_keys)
                    # Also handle string content at this level (when sub_segment is a string)
                    if not self.with_nikud and isinstance(sub_segment, str):
                        processed = self.remove_nikud(sub_segment)
                    result[key] = processed
                return result
            # Handle single string at this level
            if not self.with_nikud and isinstance(text_segment, str):
                return self.remove_nikud(text_segment)
            return text_segment

        def set_nested(refs, keys, value):
            d = refs
            for k in keys[:-1]:
                if k not in d:
                    d[k] = {}
                d = d[k]
            d[keys[-1]] = value

        def traverse(node, ref_path, depth=0, parent_section_names=None, max_refs=None, api_call_count=None):
            if api_call_count is None:
                api_call_count = [0]
            
            # Stop traversal if we've hit the API call limit
            if max_refs is not None and api_call_count[0] >= max_refs:
                return
            
            next_ref_path = ref_path
            if node.get("title"):
                next_ref_path = ref_path + [node["title"]]

            section_names = node.get("sectionNames") or parent_section_names or []

            if node.get("nodeType") == "JaggedArrayNode" and not node.get("nodes"):
                # Check limit before processing this section
                if max_refs is not None and api_call_count[0] >= max_refs:
                    print(f"Reached max API calls ({max_refs}). Skipping remaining sections.")
                    return
                
                jagged_depth = node.get("depth", 1)
                ref_prefix = "%2C ".join([h for h in next_ref_path if h]).strip()
                print(f"Section: {' > '.join(next_ref_path)} (depth {jagged_depth}, sections: {section_names})")
                
                # Make API calls based on the depth and build hierarchy accordingly
                if jagged_depth == 1:
                    # Single level - just fetch the text directly
                    print(f"  Fetching {section_names[0]}s for: {ref_prefix}")
                    text = get_text_length(ref_prefix, max_refs, api_call_count)
                    if text is None:  # Hit API limit
                        return
                    nested = build_hierarchy(section_names, text, 0)
                    set_nested(refs, next_ref_path, nested)
                    
                elif jagged_depth == 2:
                    # Two levels - fetch top level, then iterate through second level
                    base_text = get_text_length(ref_prefix, max_refs, api_call_count)
                    if base_text is None:  # Hit API limit
                        return
                    num_first_level = len(base_text) if isinstance(base_text, list) else 0
                    first_level_dict = {}
                    for idx in range(1, num_first_level + 1):
                        if max_refs is not None and api_call_count[0] >= max_refs:
                            print(f"Reached max API calls ({max_refs}). Stopping iteration.")
                            break
                        item_ref = f"{ref_prefix} {idx}"
                        print(f"  Fetching {section_names[0]} {idx}")
                        item_text = get_text_length(item_ref, max_refs, api_call_count)
                        if item_text is None:  # Hit API limit
                            break
                        item_hierarchy = build_hierarchy(section_names[1:], item_text, 0)
                        first_level_dict[str(idx)] = item_hierarchy
                    set_nested(refs, next_ref_path, first_level_dict)
                    
                elif jagged_depth >= 3:
                    # Three or more levels - need to traverse the hierarchy step by step
                    # For depth 3, we iterate through Chapter.Section until we get empty results
                    first_level_dict = {}
                    
                    chapter_num = 1
                    while True:
                        if max_refs is not None and api_call_count[0] >= max_refs:
                            print(f"Reached max API calls ({max_refs}). Stopping iteration.")
                            break
                        
                        # Try fetching the first section to see if this chapter exists
                        test_ref = f"{ref_prefix} {chapter_num}.1"
                        print(f"  Checking {section_names[0]} {chapter_num}")
                        test_text = get_text_length(test_ref, max_refs, api_call_count)
                        
                        if test_text is None:  # Hit API limit
                            break
                        if not test_text:  # Empty response - no more chapters
                            print(f"    No more {section_names[0]}s found")
                            break
                        
                        # This chapter exists, now iterate through sections
                        second_level_dict = {}
                        second_level_dict["1"] = build_hierarchy(section_names[2:], test_text, 0)
                        
                        section_num = 2
                        while True:
                            if max_refs is not None and api_call_count[0] >= max_refs:
                                print(f"Reached max API calls ({max_refs}). Stopping iteration.")
                                break
                            
                            section_ref = f"{ref_prefix} {chapter_num}.{section_num}"
                            print(f"    Fetching {section_names[0]} {chapter_num}, {section_names[1]} {section_num}")
                            section_text = get_text_length(section_ref, max_refs, api_call_count)
                            
                            if section_text is None:  # Hit API limit
                                break
                            if not section_text:  # Empty response - no more sections
                                print(f"      No more {section_names[1]}s in {section_names[0]} {chapter_num}")
                                break
                            
                            # Build the remaining hierarchy (depth 2+)
                            item_hierarchy = build_hierarchy(section_names[2:], section_text, 0)
                            second_level_dict[str(section_num)] = item_hierarchy
                            section_num += 1
                        
                        first_level_dict[str(chapter_num)] = second_level_dict
                        chapter_num += 1
                    
                    set_nested(refs, next_ref_path, first_level_dict)
                return

            if "nodes" in node and node["nodes"]:
                for child in node["nodes"]:
                    # Check limit before processing each child
                    if max_refs is not None and api_call_count[0] >= max_refs:
                        print(f"Reached max API calls ({max_refs}). Stopping traversal.")
                        break
                    traverse(child, next_ref_path, depth+1, section_names, max_refs, api_call_count)

        print("Starting schema traversal...")
        traverse(schema, [], 0, None, max_refs, api_call_count)
        print("Finished schema traversal.")
        print(f"Total API calls made: {api_call_count[0]}")
        if not refs:
            print("Warning: No refs generated. The book may have an unexpected schema or no content.")
        return refs
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.structure, f, ensure_ascii=False, indent=2)

    def save_refs_json(self, filename, max_refs=None, language="he"):
        refs = self.generate_refs(max_refs=max_refs, language=language)
        # Remove empty entries recursively
        def remove_empty(d):
            if isinstance(d, dict):
                return {k: remove_empty(v) for k, v in d.items() if v not in ({}, [], None) and remove_empty(v) not in ({}, [], None)}
            elif isinstance(d, list):
                return [remove_empty(x) for x in d if x not in ({}, [], None) and remove_empty(x) not in ({}, [], None)]
            return d
        filtered_refs = remove_empty(refs)
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(filtered_refs, f, ensure_ascii=False, indent=2)
        print(f"Processed {len(filtered_refs)} top-level sections/chapters.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Pull Sefaria book structure and refs.")
    parser.add_argument("book_title", type=str, help="Book title (e.g. 'Likutei Halakhot')")
    parser.add_argument("--num", type=int, default=0, help="Maximum number of API calls to text API (0 means unlimited)")
    parser.add_argument("--language", type=str, choices=["he", "en"], default="he", help="Text language: 'he' for Hebrew, 'en' for English (default: he)")
    parser.add_argument("--with-nikud", action="store_true", help="Keep nikud (vowel points) in Hebrew text (default: remove nikud)")
    args = parser.parse_args()
    import os
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)
    structure_path = os.path.join(data_dir, f"{args.book_title.replace(' ', '_')}_structure.json")
    refs_path = os.path.join(data_dir, f"{args.book_title.replace(' ', '_')}_refs.json")
    sbs = SefariaBookStructure(args.book_title, with_nikud=args.with_nikud)
    sbs.save_structure_json(structure_path)
    sbs.save_refs_json(refs_path, max_refs=(args.num if args.num > 0 else None), language=args.language)
    if args.num > 0:
        print(f"Saved structure and made up to {args.num} API calls for {args.book_title} in {data_dir}/")
