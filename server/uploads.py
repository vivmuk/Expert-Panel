import base64
import io
import re
import zipfile
from xml.etree import ElementTree

MAX_FILES = 4
MAX_TEXT = 8000


def take_uploads(incoming, existing):
    kept = list(existing or [])
    if not isinstance(incoming, list):
        return kept[:MAX_FILES]
    for item in incoming:
        parsed = _one(item)
        if parsed:
            kept.append(parsed)
    return kept[:MAX_FILES]


def _one(item):
    if not isinstance(item, dict):
        return None
    name = str(item.get("name") or "upload.txt")[:80]
    ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""
    if item.get("text") and ext in ("txt", "md", "markdown", ""):
        text = " ".join(str(item["text"]).split())[:MAX_TEXT]
    else:
        raw = _decode(item.get("base64"))
        if raw is None and item.get("text"):
            text = " ".join(str(item["text"]).split())[:MAX_TEXT]
        elif raw is None:
            return None
        elif ext == "docx":
            text = _docx(raw)[:MAX_TEXT]
        elif ext == "pdf":
            text = _pdf(raw)[:MAX_TEXT]
        else:
            text = raw.decode("utf-8", errors="ignore")
            text = " ".join(text.split())[:MAX_TEXT]
    text = " ".join(text.split())
    if len(text) < 2:
        return None
    kind = "template" if _looks_like_template(name, text) else "source"
    return {"name": name, "text": text[:MAX_TEXT], "kind": kind}


def _decode(value):
    if not value or not isinstance(value, str):
        return None
    if len(value) > 600_000:
        return None
    try:
        return base64.b64decode(value, validate=False)
    except Exception:
        return None


def _docx(data):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            xml = archive.read("word/document.xml")
    except Exception:
        return ""
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        return ""
    parts = []
    for node in root.iter():
        if node.tag.endswith("}t") and node.text:
            parts.append(node.text)
    return " ".join(parts)


def _pdf(data):
    parts = []
    for match in re.findall(rb"\((?:\\.|[^\\)]){2,240}\)", data[:2_000_000]):
        inner = match[1:-1].replace(b"\\n", b" ").replace(b"\\(", b"(").replace(b"\\)", b")")
        try:
            parts.append(inner.decode("latin-1"))
        except Exception:
            continue
        if len(parts) >= 80:
            break
    return " ".join(parts)


def _looks_like_template(name, text):
    lowered = name.lower()
    if "template" in lowered:
        return True
    return "{{" in text and "}}" in text
