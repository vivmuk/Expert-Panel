"""The client deck as a .pptx: the slide spec from live_report, drawn in Constellation Paper."""
import io
import os
from functools import lru_cache

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from .chatjob import load_state
from .live_report import ready, slides, title_of

STATIC = os.path.join(os.path.dirname(__file__), "static")
PAPER, PAPER_2, WHITE = RGBColor(0xFA, 0xFA, 0xF7), RGBColor(0xF0, 0xF0, 0xEC), RGBColor(0xFF, 0xFF, 0xFF)
INK, INK_2, INK_3 = RGBColor(0x0F, 0x0F, 0x0F), RGBColor(0x52, 0x52, 0x58), RGBColor(0x6E, 0x6E, 0x76)
RULE = RGBColor(0xDD, 0xDD, 0xD8)
COBALT, COBALT_WASH, RED, MAGENTA = RGBColor(0x00, 0x33, 0xCC), RGBColor(0xE8, 0xED, 0xFB), RGBColor(0xD7, 0x26, 0x3D), RGBColor(0xC4, 0x13, 0x6B)
SANS, MONO = "Arial", "Consolas"
W, H = 13.333, 7.5


@lru_cache(maxsize=8)
def _jpeg(path):
    from PIL import Image

    with Image.open(os.path.join(STATIC, path)) as image:
        image = image.convert("RGB")
        image.thumbnail((1200, 1200))
        out = io.BytesIO()
        image.save(out, "JPEG", quality=84, optimize=True)
        return out.getvalue()


def _box(slide, x, y, w, h, fill=None, line=None, round_=True):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if round_ else MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    if round_:
        shape.adjustments[0] = 0.06
    if fill is None:
        shape.fill.background()
    else:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = Pt(0.75)
    shape.shadow.inherit = False
    shape.text_frame.text = ""
    return shape


def _text(slide, x, y, w, h, paras, size=14, color=INK, bold=False, font=SANS, align=None, anchor=MSO_ANCHOR.TOP, gap=4):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.word_wrap = True
    frame.vertical_anchor = anchor
    frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = 0
    for index, para in enumerate(paras if isinstance(paras, list) else [paras]):
        p = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        if align:
            p.alignment = align
        p.space_after = Pt(gap)
        for run_text, run_color, run_bold in para if isinstance(para, tuple) and isinstance(para[0], tuple) else [(para, color, bold)]:
            run = p.add_run()
            run.text = str(run_text)
            run.font.size = Pt(size)
            run.font.name = font
            run.font.bold = run_bold
            run.font.color.rgb = run_color
    return box


def _chip(slide, x, y, label, owner=None, level=None):
    width = 0.12 + 0.085 * len(label)
    fill, line, color = WHITE, INK, INK
    if owner == "AI Agent" or level == "high":
        fill, line, color = COBALT, COBALT, WHITE
    elif owner == "Hybrid":
        line, color = MAGENTA, MAGENTA
    elif level == "medium":
        fill, line, color = COBALT_WASH, COBALT_WASH, COBALT
    elif level == "low":
        line, color = RULE, INK_2
    _box(slide, x, y, width, 0.3, fill, line)
    _text(slide, x, y, width, 0.3, label.upper(), 9, color, True, MONO, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    return width


def _frame(slide, index, total, title):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = PAPER
    _box(slide, 0, 0, W * 0.7, 0.06, COBALT, round_=False)
    _box(slide, W * 0.7, 0, W * 0.3, 0.06, RED, round_=False)
    _box(slide, 0.7, 7.02, 0.1, 0.1, COBALT, round_=False)
    _text(slide, 0.88, 6.97, 4, 0.2, "AI PARTNER", 9, INK, True, MONO)
    _text(slide, 6.2, 6.97, 6.43, 0.2, f"{title.upper()[:60]}  ·  {index:02d} / {total:02d}", 9, INK_3, False, MONO, PP_ALIGN.RIGHT)


def _head(slide, s, width=11.9):
    _text(slide, 0.7, 0.5, width, 0.3, s["kicker"].upper(), 10, COBALT, True, MONO)
    _text(slide, 0.7, 0.85, width, 1.1, s["title"], 28, INK, True)


def _cover(slide, s):
    _text(slide, 0.7, 1.0, 6.4, 0.3, s["kicker"].upper(), 11, COBALT, True, MONO)
    _text(slide, 0.7, 1.5, 6.4, 3.2, s["title"], 40, INK, True, anchor=MSO_ANCHOR.BOTTOM)
    _box(slide, 0.7, 4.95, 0.9, 0.06, RED, round_=False)
    _text(slide, 0.7, 5.2, 6.2, 1.5, s["sub"], 15, INK_2)
    slide.shapes.add_picture(io.BytesIO(_jpeg(s["art"])), Inches(7.4), Inches(1.15), Inches(5.3), Inches(3.975))


def _bullets(slide, s):
    art = s.get("art")
    width = 6.9 if art else 11.9
    _head(slide, s, width)
    y = 2.05
    if s.get("lede"):
        _text(slide, 0.7, y, width, 1.9, s["lede"], 15, INK_2)
        y = 4.0 if len(s["lede"]) > 260 else 3.3
    paras = [((f"{n}  " if s.get("numbered") else "—  ", RED if not s.get("numbered") else COBALT, True), (b, INK, False)) for n, b in enumerate(s["bullets"], 1)]
    _text(slide, 0.7, y, width, 6.8 - y, paras, 13 if len(" ".join(s["bullets"])) > 600 else 15, gap=9)
    if art:
        slide.shapes.add_picture(io.BytesIO(_jpeg(art)), Inches(8.0), Inches(1.6), Inches(4.7), Inches(3.525))


def _grid(slide, s):
    _head(slide, s)
    cols, w, h = 5, 2.3, 1.0
    for i, (name, role) in enumerate(s["items"][:20]):
        x, y = 0.7 + (i % cols) * (w + 0.1), 2.0 + (i // cols) * (h + 0.12)
        _box(slide, x, y, w, h, WHITE, RULE)
        _text(slide, x + 0.14, y + 0.12, w - 0.28, h - 0.2, [((name, INK, True),), ((role, INK_2, False),)], 10.5, gap=2)


def _table(slide, s):
    _head(slide, s)
    rows, cols = len(s["rows"]) + 1, len(s["head"])
    widths = list(s.get("widths") or [0.5, 6.6, 1.15, 1.15, 1.3, 1.2])[:cols]
    levels = set(s.get("levels") or (2, 3, 4))
    shape = slide.shapes.add_table(rows, cols, Inches(0.7), Inches(2.05), Inches(sum(widths)), Inches(0.5 + 0.8 * (rows - 1)))
    table = shape.table
    for c, width in enumerate(widths):
        table.columns[c].width = Inches(width)
    for r in range(rows):
        for c in range(cols):
            cell = table.cell(r, c)
            value = s["head"][c] if r == 0 else s["rows"][r - 1][c]
            cell.fill.solid()
            cell.fill.fore_color.rgb = PAPER_2 if r == 0 else WHITE
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_left = cell.margin_right = Inches(0.12)
            p = cell.text_frame.paragraphs[0]
            run = p.add_run()
            run.text = value.upper() if r == 0 or c in levels else value
            run.font.name = MONO if r == 0 or c in levels else SANS
            run.font.size = Pt(9 if r == 0 else (20 if c == 0 else 11 if len(value) > 70 else 12))
            run.font.bold = r == 0 or c == 0 or value == "high"
            run.font.color.rgb = INK_3 if r == 0 else (COBALT if c == 0 or value == "high" else INK)


def _rec(slide, s):
    _text(slide, 0.6, 1.3, 2.2, 3, str(s["n"]), 150, COBALT, True)
    x, w = 3.0, 9.6
    _text(slide, x, 0.9, w, 0.3, s["kicker"].upper(), 10, COBALT, True, MONO)
    _text(slide, x, 1.3, w, 1.5, s["title"], 26, INK, True, anchor=MSO_ANCHOR.BOTTOM)
    _text(slide, x, 3.0, w, 1.4, s["detail"], 15, INK_2)
    cx = x
    for label, value in s["levels"]:
        cx += _chip(slide, cx, 4.5, f"{label} {value}", level=value) + 0.12
    _text(slide, x, 5.0, w, 0.6, [((f"BACKED BY {len(s['backers'])}   ", INK_3, True), (", ".join(s["backers"]), INK, False))], 11)
    if s["dissent"]:
        _box(slide, x, 5.65, 0.05, 0.9, RED, round_=False)
        _text(slide, x + 0.2, 5.65, w - 0.2, 0.9, [(("Dissent. ", RED, True), (s["dissent"], INK_2, False))], 12)


def _chart(slide, s):
    _head(slide, s)
    _text(slide, 0.7, 1.75, 11.9, 0.7, s["lede"], 13, INK_2)
    rows = s["steps"][:6]
    h = min(0.72, 4.3 / max(len(rows), 1) - 0.08)
    for n, (name, task, owner) in enumerate(rows, 1):
        y = 2.55 + (n - 1) * (h + 0.08)
        _box(slide, 0.7, y, 11.9, h, WHITE, RULE)
        _box(slide, 0.7, y, 0.06, h, COBALT if owner == "AI Agent" else MAGENTA if owner == "Hybrid" else INK, round_=False)
        _text(slide, 0.95, y, 0.5, h, f"{n:02d}", 11, RED, True, MONO, anchor=MSO_ANCHOR.MIDDLE)
        paras = [((name, INK, True),)] + ([((task, INK_2, False),)] if task else [])
        _text(slide, 1.5, y + 0.06, 9.3, h - 0.12, paras, 12, anchor=MSO_ANCHOR.MIDDLE, gap=1)
        _chip(slide, 12.45 - (0.12 + 0.085 * len(owner)), y + (h - 0.3) / 2, owner, owner=owner)


def _columns(slide, s):
    _head(slide, s)
    count = len(s["cols"])
    gap = 0.2
    w = (11.9 - gap * (count - 1)) / count
    for i, (label, items) in enumerate(s["cols"]):
        x, on = 0.7 + i * (w + gap), s.get("on") == i
        _box(slide, x, 2.1, w, 4.5, COBALT if on else WHITE, COBALT if on else RULE)
        top = RED if count == 3 and i == 0 else COBALT if count == 3 and i == 1 else (WHITE if on else INK)
        _box(slide, x, 2.1, w, 0.07, top, round_=False)
        _text(slide, x + 0.22, 2.35, w - 0.44, 0.35, label.upper(), 10.5, WHITE if on else INK_3, True, MONO)
        _text(slide, x + 0.22, 2.85, w - 0.44, 3.6, [((("—  " if count == 3 else ""), RED, True), (item, WHITE if on else INK, False)) for item in items], 13, gap=10)


DRAW = {"cover": _cover, "bullets": _bullets, "grid": _grid, "table": _table, "rec": _rec, "chart": _chart, "columns": _columns}


def build_pptx(raw):
    state = load_state(raw)
    if not ready(state):
        raise ValueError("not ready")
    spec = slides(state)
    deck = Presentation()
    deck.slide_width, deck.slide_height = Inches(W), Inches(H)
    deck.core_properties.title = title_of(state)
    deck.core_properties.author = "AI Partner"
    blank = deck.slide_layouts[6]
    for index, item in enumerate(spec, 1):
        slide = deck.slides.add_slide(blank)
        _frame(slide, index, len(spec), title_of(state))
        DRAW[item["kind"]](slide, item)
    out = io.BytesIO()
    deck.save(out)
    return out.getvalue()
