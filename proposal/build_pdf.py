#!/usr/bin/env python3
"""Build Stay_On_Task_proposal.pdf from proposal.md."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent
MD = ROOT / "proposal.md"
OUT_LOCAL = ROOT / "Stay_On_Task_proposal.pdf"

TEXT_WIDTH = 595 - 2 * 54  # points

CSS = """
html, body {
  font-family: sans-serif;
  font-size: 9.4pt;
  line-height: 1.34;
  color: #1a1a1a;
}
h1 {
  font-size: 19pt;
  font-weight: 700;
  color: #0b3a8c;
  margin: 0 0 4pt 0;
  line-height: 1.15;
}
h2 {
  font-size: 12.5pt;
  font-weight: 700;
  color: #0b3a8c;
  margin: 13pt 0 5pt 0;
  line-height: 1.2;
  page-break-after: avoid;
}
p { margin: 0 0 6pt 0; }
strong { font-weight: 700; }
code { font-size: 8.8pt; }
table {
  width: 100%;
  border-collapse: collapse;
  margin: 6pt 0 8pt 0;
  font-size: 8.6pt;
}
th, td {
  border: 0.6pt solid #d3d8e0;
  padding: 3pt 5pt;
  vertical-align: top;
  text-align: left;
}
th { font-weight: 700; color: #0b3a8c; }
img { display: block; margin: 6pt auto 8pt auto; }
.meta { margin: 0 0 8pt 0; font-size: 9.6pt; color: #555555; }
.refs ol { font-size: 7.6pt; line-height: 1.28; margin: 4pt 0 0 0; }
.refs li { margin: 0 0 2pt 0; }
"""


def md_to_html(text: str) -> str:
    # Convert kramdown image attrs: ![alt](path){: style="width:64%"}
    def img_repl(m: re.Match) -> str:
        alt, src, style = m.group(1), m.group(2), m.group(3)
        pct = float(re.search(r"width:\s*([0-9.]+)%", style).group(1))
        return f'<img src="{src}" alt="{alt}" width="{pct * TEXT_WIDTH / 100:.0f}" />'

    text = re.sub(
        r'!\[([^\]]*)\]\(([^)]+)\)\{:\s*style="([^"]+)"\}',
        img_repl,
        text,
    )
    body = markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "sane_lists"],
    )
    # first paragraph after h1 is meta line
    body = re.sub(
        r"(</h1>\s*)<p>(.*?)</p>",
        r'\1<p class="meta">\2</p>',
        body,
        count=1,
        flags=re.S,
    )
    # wrap references list
    body = re.sub(
        r"(<h2>References</h2>\s*)(<ol>.*?</ol>)",
        r'\1<div class="refs">\2</div>',
        body,
        flags=re.S,
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{CSS}</style></head>
<body>{body}</body></html>"""


def write_with_weasy(html: str, out: Path) -> None:
    from weasyprint import HTML

    HTML(string=html, base_url=str(ROOT)).write_pdf(str(out))


def write_with_pymupdf(html: str, out: Path) -> None:
    import fitz

    story = fitz.Story(html=html, archive=fitz.Archive(str(ROOT)))
    writer = fitz.DocumentWriter(str(out))
    mediabox = fitz.paper_rect("a4")
    where = mediabox + (54, 54, -54, -50)
    more = 1
    while more:
        device = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(device)
        writer.end_page()
    writer.close()

    # page numbers
    doc = fitz.open(str(out))
    for i, page in enumerate(doc, 1):
        page.insert_text(
            (mediabox.width / 2 - 4, mediabox.height - 22),
            str(i),
            fontsize=7.5,
            fontname="helv",
            color=(0.55, 0.55, 0.55),
        )
    doc.saveIncr()
    doc.close()


def main() -> int:
    html = md_to_html(MD.read_text())
    try:
        write_with_weasy(html, OUT_LOCAL)
        engine = "weasyprint"
    except Exception as e:
        print(f"weasyprint unavailable ({e}); using pymupdf", file=sys.stderr)
        write_with_pymupdf(html, OUT_LOCAL)
        engine = "pymupdf"
    print(f"wrote {OUT_LOCAL} via {engine}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
