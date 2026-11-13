"""Classify a filing: rules first (free), the fast model only for leftovers."""
import logging
from collections import Counter

from ..llm import client as llm
from ..llm.schemas import ClassifyOut
from . import rules

log = logging.getLogger(__name__)
STATS: Counter = Counter()  # rules / llm / fallback hits, reported in the write-up and /admin/usage


def classify(desc: str, subject: str, summary: str | None = None) -> tuple[str, str]:
    """Returns (category, method) where method is rule | llm | fallback."""
    cat = rules.classify(desc, subject)
    if cat:
        STATS["rule"] += 1
        return cat, "rule"
    if llm.available():
        try:
            out = llm.complete("classify_filing", "fast",
                               {"category": desc, "subject": subject, "summary": (summary or "")[:1500]},
                               schema=ClassifyOut, job="ingest_filings")
            if out["category"] in rules.CATEGORIES and out["confidence"] >= 0.6:
                STATS["llm"] += 1
                return out["category"], "llm"
            STATS["llm_low"] += 1
            return "other", "llm"
        except Exception as e:  # noqa: BLE001
            log.info("classify llm failed: %s", e)
    STATS["fallback"] += 1
    if rules.GENERIC_DESC_RE.search(desc or ""):
        return "routine", "fallback"
    return "other", "fallback"
