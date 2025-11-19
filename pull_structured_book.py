import requests
import json

class SefariaBookStructure:
    def save_structure_json(self, filename):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.structure, f, ensure_ascii=False, indent=2)
    BASE_URL = "https://www.sefaria.org/api/v2/index/"

    def __init__(self, book_title):
        self.book_title = book_title
        self.structure = None

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
        section_count = [0]  # mutable counter for top-level sections

        def get_text_length(ref):
            url = f"https://www.sefaria.org/api/texts/{ref.replace(' ', '_')}?context=0"
            print(f"  [API] Fetching: {url}")
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
            if depth >= len(section_names):
                # Log paragraph fetch
                if isinstance(text_segment, list):
                    print(f"  Paragraphs: {len(text_segment)}")
                return text_segment
            if isinstance(text_segment, list):
                result = {}
                for i, sub_segment in enumerate(text_segment, 1):
                    key = str(i)
                    current_keys = parent_keys + [key]
                    print(f"    {section_names[depth]} {key}")
                    result[key] = build_hierarchy(section_names, sub_segment, depth + 1, current_keys)
                return result
            return text_segment

        def set_nested(refs, keys, value):
            d = refs
            for k in keys[:-1]:
                if k not in d:
                    d[k] = {}
                d = d[k]
            d[keys[-1]] = value

        def traverse(node, ref_path, depth=0, parent_section_names=None, max_refs=None, section_count=None):
            if section_count is None:
                section_count = [0]
            # Limit number of top-level sections (first level under root)
            if depth == 1 and max_refs is not None and section_count[0] >= max_refs:
                return
            next_ref_path = ref_path
            if node.get("title"):
                next_ref_path = ref_path + [node["title"]]

            section_names = node.get("sectionNames") or parent_section_names or []

            if node.get("nodeType") == "JaggedArrayNode" and not node.get("nodes"):
                jagged_depth = node.get("depth", 1)
                ref_prefix = "%2C ".join([h for h in next_ref_path if h]).strip()
                print(f"Section: {' > '.join(next_ref_path)} (depth {jagged_depth})")
                if depth == 1:
                    section_count[0] += 1
                if jagged_depth > 1:
                    base_text = get_text_length(ref_prefix)
                    num_chapters = len(base_text) if isinstance(base_text, list) else 0
                    chapters_dict = {}
                    for chapter_num in range(1, num_chapters + 1):
                        chapter_ref = f"{ref_prefix} {chapter_num}"
                        print(f"  Fetching chapter {chapter_num} for section: {ref_prefix}")
                        chapter_text = get_text_length(chapter_ref)
                        chapter_hierarchy = build_hierarchy(section_names[1:], chapter_text, 0)
                        chapters_dict[str(chapter_num)] = chapter_hierarchy
                    set_nested(refs, next_ref_path, chapters_dict)
                else:
                    print(f"  Fetching paragraphs for section: {ref_prefix}")
                    text = get_text_length(ref_prefix)
                    nested = build_hierarchy(section_names, text, 0)
                    set_nested(refs, next_ref_path, nested)
                return

            if "nodes" in node and node["nodes"]:
                for child in node["nodes"]:
                    # Only count top-level sections
                    if depth == 0 and max_refs is not None and section_count[0] >= max_refs:
                        break
                    traverse(child, next_ref_path, depth+1, section_names, max_refs, section_count)

        print("Starting schema traversal...")
        traverse(schema, [], 0, None, max_refs, section_count)
        print("Finished schema traversal.")
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
    parser.add_argument("--num", type=int, default=0, help="Number of refs to process (0 means all)")
    parser.add_argument("--language", type=str, choices=["he", "en"], default="he", help="Text language: 'he' for Hebrew, 'en' for English (default: he)")
    args = parser.parse_args()
    import os
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)
    structure_path = os.path.join(data_dir, f"{args.book_title.replace(' ', '_')}_structure.json")
    refs_path = os.path.join(data_dir, f"{args.book_title.replace(' ', '_')}_refs.json")
    sbs = SefariaBookStructure(args.book_title)
    sbs.save_structure_json(structure_path)
    sbs.save_refs_json(refs_path, max_refs=(args.num if args.num > 0 else None), language=args.language)
    if args.num > 0:
        print(f"Saved structure and up to {args.num} refs for {args.book_title} in {data_dir}/")
