"""Turn uploaded files into text blocks with locators, then into overlapping chunks."""
import io
import re
from datetime import datetime, timezone

from ..knowledge.lexicon import MONTHS
from ..nlp.extract import parse_dates

_MONTH_YEAR = re.compile(r"\b(" + "|".join(m[:-1] + r"\w?" if m.endswith(("я", "а")) else m for m in MONTHS) + r")\s+(20\d\d)\b", re.I)
_MONTH_STEM = {m[:4]: n for m, n in MONTHS.items()}


def read_blocks(name, raw):
    """Return (title_guess, [(locator, text)])."""
    low = name.lower()
    if low.endswith((".txt", ".md", ".csv")):
        text = raw.decode("utf-8-sig", errors="replace")
        blocks, section, buf = [], "документ", []

        def flush():
            if buf:
                blocks.append((f"раздел «{section}»", " ".join(buf)))
                buf.clear()

        for line in text.splitlines():
            h = re.match(r"\s*#{1,4}\s+(.*)", line)
            if h:
                flush()
                section = h.group(1).strip()[:80]
            elif not line.strip():
                flush()
            else:
                buf.append(line.strip())
        flush()
        first = next((ln.lstrip("# ").strip() for ln in text.splitlines() if ln.strip()), name)
        return first[:300], blocks
    if low.endswith(".pdf"):
        from pypdf import PdfReader
        r = PdfReader(io.BytesIO(raw))
        blocks = []
        for i, page in enumerate(r.pages, 1):
            t = (page.extract_text() or "").strip()
            for j, para in enumerate([x.strip() for x in re.split(r"\n\s*\n|(?<=[.!?])\n(?=[А-ЯA-Z])", t) if x.strip()], 1):
                blocks.append((f"стр. {i}, абз. {j}", re.sub(r"\s*\n\s*", " ", para)))
        meta_title = (r.metadata.title if r.metadata and r.metadata.title else None)
        first = meta_title or (blocks[0][1][:200] if blocks else name)
        return first, blocks
    if low.endswith(".docx"):
        from docx import Document
        d = Document(io.BytesIO(raw))
        blocks, section = [], "документ"
        for i, p in enumerate(d.paragraphs, 1):
            t = p.text.strip()
            if not t:
                continue
            if p.style is not None and p.style.name.lower().startswith(("heading", "заголовок")):
                section = t[:80]
                continue
            blocks.append((f"раздел «{section}», абз. {i}", t))
        return (blocks[0][1][:200] if blocks else name), blocks
    raise ValueError("Поддерживаются TXT, MD, PDF и DOCX")


def guess_date(text, fallback=None):
    for d in parse_dates(text[:3000]):
        return d + "T00:00:00+00:00"
    m = _MONTH_YEAR.search(text[:3000])
    if m:
        mon = _MONTH_STEM.get(m.group(1).lower()[:4])
        if mon:
            return f"{int(m.group(2)):04d}-{mon:02d}-01T00:00:00+00:00"
    return fallback or datetime.now(timezone.utc).isoformat()


def chunk_blocks(blocks, target=700, overlap=1):
    """Merge short paragraphs up to ~target chars; keep a one-block overlap so a claim is not cut off from its context."""
    chunks, cur, loc = [], [], None
    for locator, text in blocks:
        if loc is None:
            loc = locator
        cur.append(text)
        if sum(len(x) for x in cur) >= target:
            chunks.append((loc, " ".join(cur)))
            cur = cur[-overlap:] if overlap else []
            loc = locator
    if cur and (not chunks or sum(len(x) for x in cur) > 120 or len(cur) > overlap):
        chunks.append((loc or "документ", " ".join(cur)))
    return chunks
