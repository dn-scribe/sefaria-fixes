import requests
import json

class SefariaBookStructure:
    BASE_URL = "https://www.sefaria.org/api/v2/index/"

    def __init__(self, book_title):
        self.book_title = book_title
        self.structure = None

    def fetch_structure(self, structure_path=None):
        import os
        if structure_path and os.path.exists(structure_path):
            with open(structure_path, "r", encoding="utf-8") as f:
                self.structure = json.load(f)
            print(f"Loaded structure from {structure_path}")
            return self.structure
        url = f"{self.BASE_URL}{self.book_title.replace(' ', '_')}"
        response = requests.get(url)
        response.raise_for_status()
        self.structure = response.json()
        return self.structure

    def generate_refs(self, max_refs=None):
        if not self.structure:
            self.fetch_structure()
        refs = {}
        title = self.structure.get("title")
        schema = self.structure.get("schema", {})
        ref_count = [0]  # mutable counter

        def get_text_length(ref):
            url = f"https://www.sefaria.org/api/texts/{ref.replace(' ', '_')}?context=0"
            try:
                response = requests.get(url)
                response.raise_for_status()
                data = response.json()
                text = data.get("he", [])
                return text
            except Exception:
                return []


        def traverse(node, ref_path, depth=0):
            if max_refs is not None and ref_count[0] >= max_refs:
                return
            # Only add to ref_path if node has a title
            next_ref_path = ref_path
            if node.get("title"):
                next_ref_path = ref_path + [node["title"]]

            # Always recurse into children if 'nodes' is present
            if "nodes" in node and node["nodes"]:
                for child in node["nodes"]:
                    traverse(child, next_ref_path, depth+1)
            # Only fetch text for true leaf JaggedArrayNodes (no 'nodes')
            elif node.get("nodeType") == "JaggedArrayNode":
                ref_prefix = "%2C ".join([h for h in next_ref_path if h]).strip()
                print(f"Fetching: {ref_prefix}")
                before_count = ref_count[0]
                def build_refs(indices, text_segment, depth, max_depth):
                    if max_refs is not None and ref_count[0] >= max_refs:
                        return
                    # If at leaf depth, but text_segment is a list of strings, keep the list as the value
                    if depth == max_depth:
                        ref_str = f"{ref_prefix}.{'.'.join(str(x) for x in indices)}".strip()
                        refs[ref_str] = text_segment
                        ref_count[0] += 1
                        return
                    # If text_segment is a list of strings (not further nested), keep the list as the value
                    if isinstance(text_segment, list) and all(isinstance(x, str) for x in text_segment):
                        ref_str = f"{ref_prefix}.{'.'.join(str(x) for x in indices)}".strip()
                        refs[ref_str] = text_segment
                        ref_count[0] += 1
                        return
                    # Otherwise, recurse into sublists
                    if isinstance(text_segment, list):
                        for i, sub_segment in enumerate(text_segment, 1):
                            build_refs(indices + [i], sub_segment, depth + 1, max_depth)

                jagged_depth = node.get("depth", 1)
                text = get_text_length(ref_prefix)
                build_refs([], text, 0, jagged_depth)
                added = ref_count[0] - before_count
                print(f"Added {added} refs for {ref_prefix}. Total so far: {ref_count[0]}")

        traverse(schema, [], 0)
        return refs

    def save_structure_json(self, filename):
        import os
        if not self.structure:
            self.fetch_structure(structure_path=filename)
        if not os.path.exists(filename):
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(self.structure, f, ensure_ascii=False, indent=2)

    def save_refs_json(self, filename, max_refs=None):
        refs = self.generate_refs(max_refs=max_refs)
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(refs, f, ensure_ascii=False, indent=2)
        print(f"Processed {len(refs)} refs.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Pull Sefaria book structure and refs.")
    parser.add_argument("book_title", type=str, help="Book title (e.g. 'Likutei Halakhot')")
    parser.add_argument("--num", type=int, default=0, help="Number of refs to process (0 means all)")
    args = parser.parse_args()

    import os
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)
    structure_path = os.path.join(data_dir, f"{args.book_title.replace(' ', '_')}_structure.json")
    refs_path = os.path.join(data_dir, f"{args.book_title.replace(' ', '_')}_refs.json")
    sbs = SefariaBookStructure(args.book_title)
    sbs.save_structure_json(structure_path)
    sbs.save_refs_json(refs_path, max_refs=(args.num if args.num > 0 else None))
    if args.num > 0:
        print(f"Saved structure and up to {args.num} refs for {args.book_title} in {data_dir}/")
    else:
        print(f"Saved structure and all refs for {args.book_title} in {data_dir}/")
    print("Done.")
