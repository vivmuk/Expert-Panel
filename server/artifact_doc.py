"""Branded cover for a generated artifact. Markdown in, markdown and HTML out."""
from html import escape


def as_markdown(title, body, demo=False):
    footer = ""
    if demo:
        footer = "\n\n---\n\nDemo engagement — generated from public information.\n"
    return f"# {title}\n\n{body.strip()}\n{footer}"


def as_html(title, body, demo=False):
    footer = "Demo engagement — generated from public information." if demo else "AI Partner"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Playfair+Display:opsz,wght@5..120,560;5..120,680&family=Source+Sans+3:wght@400;600&display=swap">
<style>
  body {{ margin: 0; background: #f7f4ee; color: #142033; font: 18px/1.55 "Source Sans 3", "Helvetica Neue", sans-serif; }}
  header, main, footer {{ max-width: 42rem; margin: 0 auto; padding: 1.5rem; }}
  header {{ display: flex; gap: 1rem; align-items: center; border-bottom: 1px solid #e4d7c4; }}
  img {{ width: 72px; height: auto; }}
  h1 {{ font-family: "Playfair Display", Georgia, serif; font-size: 2.4rem; line-height: 1.05; margin: 0; }}
  main h2 {{ font-family: "Playfair Display", Georgia, serif; font-size: 1.4rem; }}
  table {{ border-collapse: collapse; width: 100%; }}
  td, th {{ border-bottom: 1px solid #e4d7c4; text-align: left; padding: 0.4rem 0.5rem; }}
  footer {{ color: #3d4a63; font-size: 0.9rem; border-top: 1px solid #e4d7c4; }}
  @media print {{ body {{ background: #fff; }} }}
</style>
</head>
<body>
<header>
  <img src="/img/brand/avatar.webp" alt="">
  <h1>{escape(title)}</h1>
</header>
<main>
{_md(body)}
</main>
<footer>{escape(footer)}</footer>
</body>
</html>
"""


def _md(body):
    parts = []
    rows = []
    for line in body.splitlines():
        if line.startswith("|"):
            rows.append(line)
            continue
        if rows:
            parts.append(_table(rows))
            rows = []
        if line.startswith("## "):
            parts.append(f"<h2>{escape(line[3:])}</h2>")
        elif line.startswith("# "):
            parts.append(f"<h2>{escape(line[2:])}</h2>")
        elif line.strip():
            parts.append(f"<p>{escape(line)}</p>")
    if rows:
        parts.append(_table(rows))
    return "\n".join(parts)


def _table(lines):
    body = []
    for index, line in enumerate(lines):
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if all(set(cell) <= set("-: ") for cell in cells):
            continue
        tag = "th" if index == 0 else "td"
        body.append("<tr>" + "".join(f"<{tag}>{escape(cell)}</{tag}>" for cell in cells) + "</tr>")
    return "<table>" + "".join(body) + "</table>"
