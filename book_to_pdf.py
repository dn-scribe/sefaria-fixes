"""Render a book downloaded by pull_structured_book.py into a print-ready A4 PDF.

Each top-level chapter starts on a new page, so the result is ready to be
imposed as a booklet (e.g. via Acrobat's Print > Booklet option).
"""
import argparse
import json
import os
from html import escape

from weasyprint import HTML

HEBREW_FONT_STACK = '"Arial Hebrew", "SF Hebrew", "Noto Sans Hebrew", sans-serif'


def build_title_map(node, titles):
    key = node.get("key")
    if key:
        he_title = None
        for t in node.get("titles", []) or []:
            if t.get("lang") == "he" and t.get("primary"):
                he_title = t.get("text")
                break
        if not he_title:
            for t in node.get("titles", []) or []:
                if t.get("lang") == "he":
                    he_title = t.get("text")
                    break
        if not he_title:
            he_title = node.get("sharedTitle")
        if he_title:
            titles[key] = he_title
    for child in node.get("nodes", []) or []:
        build_title_map(child, titles)


def render_content(content, level, titles, out):
    if isinstance(content, str):
        if content.strip():
            out.append(f"<p>{escape(content)}</p>")
        return
    if not isinstance(content, dict):
        return
    for key, val in content.items():
        if key.isdigit():
            if isinstance(val, str):
                if val.strip():
                    # Sefaria text segments are HTML fragments (may contain <b>, <i>, <br>, etc.)
                    out.append(f'<p><span class="pnum">{key}.</span> {val}</p>')
            else:
                render_content(val, level, titles, out)
        else:
            heading = titles.get(key, key)
            tag = f"h{min(level + 2, 6)}"
            out.append(f"<{tag}>{escape(heading)}</{tag}>")
            render_content(val, level + 1, titles, out)


def build_html(book_title, he_book_title, book_content, titles):
    body = [
        '<div class="cover">',
        f"<h1>{escape(he_book_title)}</h1>",
        f'<p class="en-title">{escape(book_title)}</p>',
        "</div>",
    ]
    for chapter_key, chapter_content in book_content.items():
        chapter_title = titles.get(chapter_key, chapter_key)
        body.append('<section class="chapter">')
        body.append(f"<h1>{escape(chapter_title)}</h1>")
        render_content(chapter_content, 0, titles, body)
        body.append("</section>")

    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<style>
  @page {{
    size: A4;
    margin: 2cm 2.2cm;
    @bottom-center {{ content: counter(page); font-size: 10pt; }}
  }}
  body {{
    direction: rtl;
    text-align: right;
    font-family: {HEBREW_FONT_STACK};
    font-size: 14pt;
    line-height: 1.6;
  }}
  .cover {{
    text-align: center;
    padding-top: 40%;
    page-break-after: always;
  }}
  .cover h1 {{ font-size: 30pt; margin-bottom: 0.3em; }}
  .cover .en-title {{ font-size: 15pt; direction: ltr; color: #555; }}
  .chapter {{ page-break-before: always; }}
  h1 {{ font-size: 21pt; border-bottom: 1pt solid #333; padding-bottom: 0.2em; }}
  h2 {{ font-size: 18pt; }}
  h3 {{ font-size: 16pt; }}
  h4, h5, h6 {{ font-size: 14.5pt; }}
  p {{ margin: 0.6em 0; text-align: justify; }}
  .pnum {{ color: #888; font-size: 0.85em; }}
</style>
</head>
<body>
{''.join(body)}
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Render a downloaded Sefaria book to a print-ready A4 PDF.")
    parser.add_argument("book_title", type=str, help="Book title, matching the name used with pull_structured_book.py")
    parser.add_argument("--data-dir", type=str, default="data", help="Directory holding the *_refs.json / *_structure.json files")
    parser.add_argument("--output", type=str, default=None, help="Output PDF path (defaults to <book_title>.pdf)")
    args = parser.parse_args()

    slug = args.book_title.replace(" ", "_")
    refs_path = os.path.join(args.data_dir, f"{slug}_refs.json")
    structure_path = os.path.join(args.data_dir, f"{slug}_structure.json")
    output_path = args.output or f"{slug}.pdf"

    with open(refs_path, encoding="utf-8") as f:
        refs = json.load(f)
    with open(structure_path, encoding="utf-8") as f:
        structure = json.load(f)

    titles = {}
    build_title_map(structure["schema"], titles)

    he_book_title = titles.get(args.book_title, args.book_title)
    book_content = refs[args.book_title]

    html_doc = build_html(args.book_title, he_book_title, book_content, titles)
    HTML(string=html_doc).write_pdf(output_path)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
