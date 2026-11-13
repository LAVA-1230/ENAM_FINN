"""Download PDFs once (cached by URL hash), extract per-page text once, select pages by keyword."""
import json
import logging
import re
from pathlib import Path

import pymupdf

from .. import http

log = logging.getLogger(__name__)
REFERERS = {"bseindia.com": "https://www.bseindia.com/", "nseindia.com": "https://www.nseindia.com/"}


def download(url: str, max_mb: float = 40) -> Path | None:
    p = http.cache_path("pdf", url, "pdf")
    if p.exists() and p.stat().st_size > 0:
        return p
    ref = next((v for k, v in REFERERS.items() if k in url), None)
    try:
        r = http.get(url, headers={"Referer": ref} if ref else None, min_gap=0.4)
    except Exception as e:  # noqa: BLE001
        log.warning("pdf download failed %s: %s", url, e)
        return None
    if not r.content.startswith(b"%PDF") or len(r.content) > max_mb * 1e6:
        log.warning("not a usable pdf: %s (%s bytes)", url, len(r.content))
        return None
    p.write_bytes(r.content)
    return p


def pages_text(url: str, max_pages: int | None = None) -> list[str]:
    """Per-page text, cached as JSON next to the PDF. [] if unavailable."""
    tp = http.cache_path("text", url, "json")
    if tp.exists():
        pages = json.loads(tp.read_text(encoding="utf-8"))
        return pages[:max_pages] if max_pages else pages
    pages = []
    for attempt in range(2):
        p = download(url)
        if not p:
            return []
        try:
            doc = pymupdf.open(p)
            pages = [_clean(pg.get_text()) for pg in doc]
            doc.close()
        except Exception as e:  # noqa: BLE001
            log.warning("pdf parse failed %s: %s", url, e)
        if pages:
            break
        p.unlink(missing_ok=True)  # truncated download: fetch once more
    if not pages:
        return []
    tp.write_text(json.dumps(pages), encoding="utf-8")
    return pages[:max_pages] if max_pages else pages


def prefetch(urls: list[str], workers: int = 4) -> None:
    """Download and extract several PDFs in parallel (the polite per-host gap still applies)."""
    from concurrent.futures import ThreadPoolExecutor
    todo = [u for u in dict.fromkeys(urls) if u and not http.cache_path("text", u, "json").exists()]
    if not todo:
        return
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(lambda u: pages_text(u), todo))


def _clean(t: str) -> str:
    t = t.replace(" ", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t)
    return t.strip()


SECTION_KEYWORDS = {
    "mdna": ["management discussion", "outlook", "industry overview", "opportunities", "threats",
             "risks and concerns", "business overview", "strategy"],
    "segments": ["segment information", "segment revenue", "operating segments", "segment results",
                 "revenue by geography", "geographical"],
    "cash": ["cash flow statement", "trade receivables", "inventories", "borrowings", "working capital",
             "net debt"],
}


def select_pages(pages: list[str], per_group: int = 15) -> dict[str, list[int]]:
    """Score each page by keyword hits per group; return the top pages (1-based) per group,
    preferring contiguous runs. Annual reports are 200-400 pages; we never send them whole."""
    out = {}
    for group, kws in SECTION_KEYWORDS.items():
        scores = []
        for i, t in enumerate(pages):
            low = t.lower()
            s = sum(low.count(k) for k in kws)
            if s:
                scores.append((s, i))
        scores.sort(reverse=True)
        picked = set()
        for s, i in scores:
            if len(picked) >= per_group:
                break
            picked.add(i)
            if i + 1 < len(pages) and len(picked) < per_group:
                picked.add(i + 1)  # sections run over to the next page
        out[group] = sorted(p + 1 for p in picked)
    return out
