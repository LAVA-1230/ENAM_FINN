"""Promise extraction (spec 8.2): every explicit, numeric or dated forward-looking commitment by management.

One fast-model call per transcript (whole transcript; long-context models handle 15-40 pages). Without an
LLM key, a keyword extractor reads management's own sentences for forward-looking words plus a number.
Both keep the verbatim quote, page and speaker. Repeats across quarters are merged: the earliest call is
`made_in`, later mentions are kept as repeats, and a changed target is shown as a revision."""
import logging
import re

from .. import fiscal
from ..llm import client as llm
from ..llm.schemas import PromiseExtract
from . import chunks

log = logging.getLogger(__name__)

FORWARD = re.compile(r"\b(expect|guid|target|aim|aspire|plan to|planning|will be|would be|should be|we will|we'll|"
                     r"going forward|outlook|anticipate|envisage|by fy|by the end of|next year|next fiscal|"
                     r"in the coming|over the next|commission|on track to|endeavou?r|confident of|look(ing)? to)\w*", re.I)
NUMBERISH = re.compile(r"\d+(?:\.\d+)?\s*(?:%|percent|per cent|bps|basis points|crores?|cr\b|mtpa|mw|gw|stores|plants?)|"
                       r"\bFY\s?'?\d{2}\b|double[- ]digit|high single[- ]digit|mid[- ]teens?|\b20[23]\d\b", re.I)
PAST_ONLY = re.compile(r"\b(was|were|grew|declined|reported|delivered|achieved|stood at|came in)\b", re.I)
METRIC_KEYS = [
    ("ebitda_margin", r"ebitda margin|operating margin|\bmargins?\b|\bopm\b"),
    ("market_share", r"market share"),
    ("capex", r"\bcapex\b|capital expenditure|invest(ment)? of"),
    ("net_debt", r"net debt|debt[- ]free|deleverag|borrowing"),
    ("plant", r"\bplant\b|capacity|commission|facility|factory|greenfield|brownfield"),
    ("launch", r"\blaunch|new products?|introduce"),
    ("volume", r"\bvolumes?\b|tonnes|units sold"),
    ("pat_growth", r"\bpat\b|net profit|bottom[- ]line|earnings growth"),
    ("revenue_growth", r"revenue|top[- ]line|\bsales\b|\bgrowth\b|grow"),
]
WORD_NUM = {"double-digit": 10, "double digit": 10, "high single-digit": 7, "high single digit": 7,
            "mid-teens": 14, "mid teens": 14, "low teens": 11, "high teens": 17}


def metric_key_of(text: str) -> str:
    low = text.lower()
    for key, pat in METRIC_KEYS:
        if re.search(pat, low):
            return key
    return "other"


def parse_target(sent: str) -> tuple[float | None, float | None, str | None]:
    s = sent.replace("–", "-").replace("—", "-")
    m = re.search(r"(\d+(?:\.\d+)?)\s*%?\s*(?:-|to|and)\s*(\d+(?:\.\d+)?)\s*(%|percent|per cent)", s, re.I)
    if m:
        return float(m.group(1)), float(m.group(2)), "%"
    m = re.search(r"(?:at least|over|more than|above|around|about|~|close to|approximately)?\s*(\d+(?:\.\d+)?)\s*(%|percent|per cent)", s, re.I)
    if m:
        v = float(m.group(1))
        return v, v, "%"
    for w, v in WORD_NUM.items():
        if w in s.lower():
            return float(v), None, "%"
    m = re.search(r"(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d+)?)\s*(crores?|cr)", s, re.I) or re.search(r"([\d,]+(?:\.\d+)?)\s*(crores?|cr)\b", s, re.I)
    if m:
        v = float(m.group(1).replace(",", ""))
        return v, v, "Rs crore"
    return None, None, None


def horizon_of(sent: str, call_label: str) -> str:
    q, fy = fiscal.parse_label(call_label)
    m = re.search(r"\b(H[12])\s*FY\s?'?(\d{2})\b", sent, re.I)
    if m:
        return f"{m.group(1).upper()} FY{m.group(2)}"
    m = re.search(r"\b(Q[1-4])\s*FY\s?'?(\d{2})\b", sent, re.I)
    if m:
        return f"{m.group(1).upper()} FY{m.group(2)}"
    m = re.search(r"\bFY\s?'?(\d{2})(?:\s*-\s*\d{2})?\b", sent, re.I)
    if m:
        return f"FY{m.group(1)}"
    if re.search(r"next (fiscal|financial year|year)", sent, re.I):
        return fiscal.fy_label(fy + 1)
    m = re.search(r"next (\d|two|three|five) years", sent, re.I)
    if m:
        return f"next {m.group(1)} years"
    if re.search(r"second half|\bH2\b", sent, re.I):
        return f"H2 FY{fy % 100:02d}"
    if re.search(r"next quarter|coming quarter", sent, re.I):
        return fiscal.next_quarter(call_label)
    # Q4 calls usually talk about the year ahead
    return fiscal.fy_label(fy + 1) if q == 4 else fiscal.fy_label(fy)


def heuristic_extract(pages: list[str], call_label: str) -> list[dict]:
    turns = chunks.transcript_turns(pages)
    mgmt = chunks.management_speakers(pages, turns)
    out, seen = [], set()
    for t in turns:
        if not chunks.is_management(t["speaker"], mgmt):
            continue
        for sent in re.split(r"(?<=[.!?])\s+", t["text"]):
            sent = sent.strip()
            if not (40 <= len(sent) <= 420):
                continue
            if not FORWARD.search(sent) or not NUMBERISH.search(sent):
                continue
            if PAST_ONLY.search(sent) and not re.search(r"\b(will|expect|guid|target|should)\w*", sent, re.I):
                continue
            if re.search(r"not (giving|give|provide|guide)|no guidance|don't guide|do not guide", sent, re.I):
                continue
            key = metric_key_of(sent)
            if key == "other":
                continue  # without an LLM, only commitments we can name and check
            # the number must sit next to the metric word, not anywhere in the sentence
            kw = re.search(dict(METRIC_KEYS)[key], sent, re.I)
            window = sent[max(0, kw.start() - 80): kw.end() + 80] if kw else sent
            lo, hi, unit = parse_target(window)
            if key in ("revenue_growth", "ebitda_margin", "pat_growth", "volume", "market_share") and (lo is None or unit != "%"):
                continue
            if key == "ebitda_margin" and lo is not None and lo < 3:
                continue  # '100 to 150 bps' style changes are not a margin level
            sig = (key, lo, hi)
            if sig in seen:
                continue
            seen.add(sig)
            target = (f"{lo:g}–{hi:g}%" if unit == "%" and hi and hi != lo else f"{lo:g}%" if unit == "%" and lo is not None
                      else f"₹{lo:,.0f} cr" if unit == "Rs crore" else None)
            if target is None:
                fy_m = re.search(r"\b(by|in|during)\s+(FY\s?'?\d{2}|Q[1-4]\s*FY\s?'?\d{2}|the end of [a-z ]{3,20}|next year)", sent, re.I)
                if not fy_m:
                    continue
                target = f"Due {fy_m.group(2)}"
            metric = {"ebitda_margin": "EBITDA margin", "revenue_growth": "Revenue growth", "pat_growth": "Profit growth",
                      "capex": "Capex", "net_debt": "Net debt", "plant": "Capacity / plant", "launch": "Launches",
                      "volume": "Volume growth", "market_share": "Market share"}.get(key, "Other commitment")
            out.append({"metric": metric, "metric_key": key, "target_text": target, "target_low": lo, "target_high": hi,
                        "unit": unit, "horizon": horizon_of(sent, call_label), "quote": sent[:300], "page": t["page"],
                        "speaker": t["speaker"]})
            if len(out) >= 12:
                return out
    return out


def extract(pages: list[str], call_label: str, company: str) -> tuple[list[dict], str]:
    """Returns (promises, method)."""
    if llm.available():
        text = "\n".join(f"=== page {i + 1} ===\n{p}" for i, p in enumerate(pages))
        try:
            parts = [text] if len(text) < 250_000 else [text[:len(text) // 2], text[len(text) // 2:]]
            items = []
            for part in parts:
                out = llm.complete("promise_extract", "fast", {"period_label": call_label, "company": company, "text": part},
                                   schema=PromiseExtract, job="research")
                items.extend(out["promises"])
            return [verify_quote(p, pages) for p in items if p.get("quote")], "llm"
        except Exception as e:  # noqa: BLE001
            log.info("promise llm failed (%s); falling back to keyword rules", e)
    return heuristic_extract(pages, call_label), "heuristic"


def verify_quote(p: dict, pages: list[str]) -> dict:
    """Quotes must be verbatim. Find the page that contains the quote; flag it if we can't."""
    norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())  # noqa: E731
    q = norm(p["quote"])[:120]
    for i, pg in enumerate(pages, start=1):
        if q and q[:60] in norm(pg):
            p["page"] = i
            p["quote_verified"] = True
            return p
    p["quote_verified"] = False
    return p


def merge(all_calls: list[tuple[str, int, list[dict]]]) -> list[dict]:
    """all_calls: [(call_label, document_id, promises)] oldest first. Same metric_key + horizon across calls
    -> one row, made_in = earliest; repeats keep consistency; a changed target is a revision."""
    merged: dict[tuple, dict] = {}
    for label, doc_id, items in all_calls:
        for p in items:
            key = (p["metric_key"], (p.get("horizon") or "").upper().replace(" ", ""))
            if p["metric_key"] in ("other", "launch", "plant"):
                key = key + (p["metric"].lower()[:30],)
            if key in merged:
                m = merged[key]
                rep = {"made_in": label, "target_text": p["target_text"], "page": p.get("page"), "document_id": doc_id,
                       "quote": p["quote"], "target_low": p.get("target_low"), "target_high": p.get("target_high")}
                if (p.get("target_low"), p.get("target_high")) != (m.get("latest_low"), m.get("latest_high")) and \
                        p.get("target_low") is not None and m.get("latest_low") is not None:
                    rep["revision"] = f"{m['latest_text']} → {p['target_text']}"
                    m["latest_low"], m["latest_high"], m["latest_text"] = p.get("target_low"), p.get("target_high"), p["target_text"]
                m["repeats"].append(rep)
            else:
                merged[key] = {**p, "made_in": label, "document_id": doc_id, "repeats": [],
                               "latest_low": p.get("target_low"), "latest_high": p.get("target_high"),
                               "latest_text": p["target_text"]}
    return list(merged.values())
