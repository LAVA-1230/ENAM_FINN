"""Quarterly results card (spec 7.4.1): Revenue, EBITDA, PBT, PAT with QoQ and YoY.

Extraction order (cheapest first):
  1. a deterministic parser over the statement page (Indian results tables are regular: a label line
     followed by its column values: current quarter, previous quarter, year-ago quarter);
  2. the fast model with a JSON schema, only if the parser fails validation;
  3. screener.in's quarterly row (compiled from the same filing), clearly labelled as such.
Numbers are validated before they are shown: present in the PDF text, PBT - tax ~= PAT, and within 2% of
screener when screener has the quarter. Unverified numbers are never shown as fact."""
import logging
import re
from datetime import date

from sqlalchemy import select

from ... import fiscal, fmt
from ...llm import client as llm
from ...llm.schemas import ResultsExtract
from ...models import FinancialQ, Promise
from ...sources import pdf
from ..score import Signals
from .base import Ctx, EnrichResult, free_one_liner, impact_line, price_reaction

log = logging.getLogger(__name__)
UNIT_TO_CRORE = {"crore": 1.0, "lakh": 0.01, "million": 0.1, "thousand": 0.0001}
FIELDS = ["revenue", "other_income", "total_expenses", "finance_costs", "depreciation", "exceptional_items", "pbt", "tax", "pat",
          "interest_earned", "operating_profit", "provisions"]

LABELS = {
    "revenue": [r"^(total )?revenue from operations", r"^income from operations"],
    "interest_earned": [r"^interest earned"],
    "other_income": [r"^other income"],
    "finance_costs": [r"^finance costs?"],
    "depreciation": [r"^depreciation"],
    "exceptional_items": [r"^exceptional items?"],
    "operating_profit": [r"^operating profit.*before provisions", r"^operating profit"],
    "provisions": [r"^provisions \(other than tax\)", r"^provisions and contingencies"],
    "pbt": [r"^(net )?profit\s*/?\s*\(?(loss)?\)?\s*(from ordinary activities\s*)?before tax(?!.*exceptional)",
            r"^profit\s*/?\s*\(?(loss)?\)?\s*before (income )?tax"],
    "tax": [r"^total tax expenses?", r"^tax expenses?(?! relating)", r"^income tax expenses?"],
    "pat": [r"^net profit\s*/?\s*\(?(loss)?\)?\s*(after tax\s*)?for the (period|quarter)",
            r"^profit\s*/?\s*\(?(loss)?\)?\s*for the (period|quarter)(?!.*attributable)",
            r"^(net )?profit\s*/?\s*\(?(loss)?\)?\s*after tax(?!.*attributable)"],
    "total_income": [r"^total income"],
    "total_expenses": [r"^total expenses"],
}
FIELDS_X = FIELDS + ["total_income"]
NUM_TOKEN = r"[(\[{!]?-?\d[\d,]*(?:\.\d+)?[)\]}!]?"
NUM_LINE = re.compile(r"^[(\[{!]?\s*-?\s*[\d][\d ,]*(?:\s?\.\s?\d+)?\s*[)\]}!]?$")
MULTI_NUM_LINE = re.compile(rf"^{NUM_TOKEN}(?:\s+{NUM_TOKEN})+$")
TRAILING_NUMS = re.compile(rf"((?:\s+{NUM_TOKEN}){{3,}})\s*$")
MARKER = re.compile(r"^([a-zA-Z]{1,3}[.)]|\(?[ivx]{1,4}\)?\.?|\d{1,2}[.,]?)$")
DATE_RE = re.compile(r"(\d{2})[./-](\d{2})[./-](\d{4})")
MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
TEXT_DATE_RE = re.compile(rf"(\d{{1,2}})(?:st|nd|rd|th)?[\s\-]+({MONTHS})[a-z]*[\s,\-]+(\d{{2,4}})|"
                          rf"({MONTHS})[a-z]*\s+(\d{{1,2}}),?\s+(\d{{4}})", re.I)
MONTH_NUM = {m: i for i, m in enumerate(MONTHS.split("|"), start=1)}


def find_dates(text: str) -> list[date]:
    """Column header dates in order: 30.09.2026, 30th Sep 2026, 30-Sep-26, September 30, 2026."""
    found = []
    for m in DATE_RE.finditer(text):
        try:
            found.append((m.start(), date(int(m.group(3)), int(m.group(2)), int(m.group(1)))))
        except ValueError:
            pass
    for m in TEXT_DATE_RE.finditer(text):
        try:
            if m.group(1):
                y = int(m.group(3))
                found.append((m.start(), date(y + 2000 if y < 100 else y, MONTH_NUM[m.group(2)[:3].lower()], int(m.group(1)))))
            else:
                found.append((m.start(), date(int(m.group(6)), MONTH_NUM[m.group(4)[:3].lower()], int(m.group(5)))))
        except (ValueError, KeyError):
            pass
    return [d for _, d in sorted(found)]


def parse_num(tok: str) -> float | None:
    t = tok.strip()
    neg = t.startswith(("(", "[", "{", "!")) or t.startswith("-")
    t = re.sub(r"[()\[\]{}!\-\s]", "", t)
    if re.fullmatch(r"\d+,\d{2}", t):  # OCR: '258,15' means 258.15
        t = t.replace(",", ".")
    t = t.replace(",", "")
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def line_numbers(line: str) -> list[float]:
    """A cell line ('2,706.57'), an OCR-split cell ('41 .07'), or several cells on one line."""
    if MULTI_NUM_LINE.match(line) and all("." in t or "," in t for t in line.split()):
        return [v for v in (parse_num(t) for t in line.split()) if v is not None]
    if NUM_LINE.match(line):
        v = parse_num(line)
        return [v] if v is not None else []
    return []


def pick_statement_pages(pages: list[str]) -> list[tuple[int, str]]:
    """Candidate statement pages: revenue/interest + profit before tax + quarter column headers.
    Consolidated first, then standalone, each in page order."""
    cands = []
    for i, p in enumerate(pages):
        low = p.lower()
        if not (("revenue from operations" in low or "interest earned" in low or "income from operations" in low)
                and "before tax" in low):
            continue
        if len(find_dates(p[:4000])) < 3 and not re.search(r"(quarter|three months) ended", low):
            continue
        basis = "consolidated" if re.search(
            r"consolidated (un)?audited|(un)?audited consolidated|consolidated financial results|statement of consolidated|"
            r"consolidated statement", low) else "standalone"
        cands.append((0 if basis == "consolidated" else 1, i, basis))
    return [(i, b) for _, i, b in sorted(cands)]


def pick_statement_page(pages: list[str]) -> tuple[int, str] | None:
    c = pick_statement_pages(pages)
    return c[0] if c else None


def detect_unit(text: str) -> str:
    low = text.lower()
    head = low[:2000]
    for pat, unit in ((r"in\s+lakhs?|lakhs?\)|in\s+lacs?|\blacs\b", "lakh"), (r"in\s+millions?|millions?\)|\bmn\b", "million"),
                      (r"in\s+crores?|crores?\)|\bcr\.?\)", "crore"), (r"in\s+thousands?|thousands?\)", "thousand")):
        if re.search(pat, head):
            return unit
    for pat, unit in ((r"lakh|lacs", "lakh"), (r"million", "million"), (r"crore", "crore")):
        if re.search(pat, low):
            return unit
    return "crore"


def heuristic_extract(pages: list[str], screener_row: FinancialQ | None = None) -> dict | None:
    """Try candidate statement pages in order; return the first extraction that passes validation."""
    first = None
    for idx, basis in pick_statement_pages(pages)[:5]:
        out = _extract_page(pages[idx], idx, basis)
        if not out:
            continue
        if out["current"].get("revenue") is None and not out["is_bank_format"]:
            # revenue split into sub-lines with no total: total income - other income, only if screener agrees
            ti, oi = (out["current"].get("total_income"), out["current"].get("other_income"))
            if ti is None or oi is None or not screener_row:
                continue
            for col in ("current", "previous_quarter", "year_ago_quarter"):
                c = out[col]
                c["revenue"] = (c["total_income"] - c["other_income"]) if c.get("total_income") is not None and c.get("other_income") is not None else None
            out["revenue_derived"] = True
        first = first or out
        if validate(out, pages, screener_row)[0]:
            return out
    return first


def _extract_page(text: str, idx: int, basis: str) -> dict | None:
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    dates = find_dates(text[:4000])
    found: dict[str, list[float]] = {}
    for f, pats in LABELS.items():
        for pat in pats:  # patterns in priority order
            for i, ln in enumerate(lines):
                lnl = re.sub(r"^([a-z0-9]{1,3}[.)]|[ivxl]{1,4}[.)]?)\s+", "", ln.lower())
                if not re.search(pat, lnl):
                    continue
                nums = _row_values(lines, i)
                if len(nums) >= 3:
                    found[f] = nums[:3]
                    break
            if f in found:
                break
    if "pbt" not in found or "pat" not in found or ("revenue" not in found and "interest_earned" not in found):
        return None
    out = {"basis": basis, "unit": detect_unit(text), "is_bank_format": "interest_earned" in found,
           "page": idx + 1}
    for col, j in {"current": 0, "previous_quarter": 1, "year_ago_quarter": 2}.items():
        out[col] = {f: (found[f][j] if f in found else None) for f in FIELDS_X}
        out[col]["label"] = dates[j].isoformat() if len(dates) > j else None
    return out


def _row_values(lines: list[str], i: int) -> list[float]:
    """The first three numeric cells for label line i: on the label line itself, or on the following lines.
    A new label (a line starting with a capital letter) before any number means the row is empty;
    lowercase lines are label continuations."""
    m = TRAILING_NUMS.search(lines[i])
    if m:
        nums = [v for v in (parse_num(t) for t in m.group(1).split()) if v is not None]
        if len(nums) >= 3:
            return nums
    nums: list[float] = []
    for nxt in lines[i + 1:i + 14]:
        vals = line_numbers(nxt)
        if vals:
            nums.extend(vals)
            if len(nums) >= 3:
                break
        elif MARKER.match(nxt):
            continue
        elif nums:
            break
        elif nxt[:1].isupper() or nxt[:1] in "(-":
            break
    return nums

def llm_extract(pages: list[str]) -> dict | None:
    if not llm.available():
        return None
    text = "\n".join(f"=== page {i + 1} ===\n{t}" for i, t in enumerate(pages[:8]))[:60000]
    try:
        return llm.complete("results_extract", "fast", {"text": text}, schema=ResultsExtract, job="enrich_results")
    except Exception as e:  # noqa: BLE001
        log.info("results llm failed: %s", e)
        return None


def to_crore(x: dict, unit: str) -> dict:
    k = UNIT_TO_CRORE.get(unit, 1.0)
    return {f: (x.get(f) * k if isinstance(x.get(f), (int, float)) else None) for f in FIELDS}


def derive(c: dict, bank: bool) -> dict:
    """EBITDA = revenue - (total expenses - finance costs - depreciation); if total expenses is missing,
    PBT + finance costs + depreciation - other income, with exceptional items added back."""
    out = dict(c)
    if not bank and c.get("pbt") is not None and c.get("revenue"):
        exc = c.get("exceptional_items") or 0
        fin, dep = (c.get("finance_costs") or 0), (c.get("depreciation") or 0)
        if c.get("total_expenses"):
            # operating EBITDA: excludes other income, exceptional items and associates/JV share
            out["ebitda"] = c["revenue"] - (c["total_expenses"] - fin - dep)
        else:
            out["ebitda"] = c["pbt"] - exc + fin + dep - (c.get("other_income") or 0)
        out["margin"] = out["ebitda"] / c["revenue"] * 100
    else:
        out["ebitda"] = out["margin"] = None
    return out


def _digits_index(pages: list[str]) -> str:
    return re.sub(r"[\s,.()\-]", "", " ".join(pages))


def reconcile_unit(raw: dict, screener_row: FinancialQ | None) -> None:
    """Header units are easy to misread (and OCR drops them). screener.in is in Rs crore, so the ratio of the
    two revenue figures tells the unit: ~1 crore, ~10 million, ~100 lakh."""
    rev = raw["current"].get("revenue") or raw["current"].get("interest_earned")
    base = screener_row.revenue if screener_row else None
    if not rev or not base:
        return
    ratio = rev / base
    for unit, k in (("crore", 1), ("million", 10), ("lakh", 100), ("thousand", 10000)):
        if 0.85 * k <= ratio <= 1.15 * k:
            raw["unit"] = unit
            return


def validate(raw: dict, pages: list[str], screener_row: FinancialQ | None) -> tuple[bool, list[str]]:
    notes, ok = [], True
    reconcile_unit(raw, screener_row)
    cur = raw["current"]
    digits = _digits_index(pages[: max(8, raw.get("page") or 1)])
    for f in ("revenue", "pbt", "pat", "interest_earned"):
        v = cur.get(f)
        if v is None:
            continue
        reps = {f"{abs(v):.2f}".replace(".", ""), f"{abs(v):.1f}".replace(".", ""), f"{abs(v):.0f}"}
        if not any(r in digits for r in reps):
            ok = False
            notes.append(f"{f} not found in the PDF text")
    for col in ("current", "previous_quarter", "year_ago_quarter"):
        c = raw[col]
        if c.get("pbt") is not None and c.get("tax") is not None and c.get("pat") not in (None, 0):
            gap = abs((c["pbt"] - abs(c["tax"])) - c["pat"])
            if gap > abs(c["pat"]) * 0.015 + 0.02:
                # minority interest / associates can explain a gap; allow it if PAT is below PBT and same sign
                if not (abs(c["pat"]) <= abs(c["pbt"]) and gap < abs(c["pbt"]) * 0.25):
                    ok = False
                    notes.append(f"PBT minus tax does not match PAT in {col}")
    if screener_row and screener_row.revenue and cur.get("revenue"):
        rev_cr = cur["revenue"] * UNIT_TO_CRORE.get(raw["unit"], 1)
        if abs(rev_cr - screener_row.revenue) / screener_row.revenue <= 0.02:
            notes.append("matches screener.in")
        elif raw.get("basis") == "consolidated" or raw.get("revenue_derived"):
            ok = False
            notes.append("differs from screener.in by more than 2%")
    return ok, notes


def results_period(subject: str, published: date, summary: str = "") -> str:
    """'...for the period ended September 30, 2026' -> Q2 FY27. Only dates after 'ended' count (a board-meeting
    date in the same subject must not win). Otherwise: the quarter before the filing date."""
    for text in (subject, summary):
        m = re.search(r"(?:period|quarter|half[- ]year|year|months)\s+ended\s+(?:on\s+)?(.{6,24})", text or "", re.I)
        if m:
            lbl = fiscal.parse_quarter_ended(m.group(1))
            if lbl and fiscal.quarter_end(lbl) < published:
                return lbl
    return fiscal.prev_quarter(fiscal.quarter_label(published))


def guided_margin(ctx: Ctx, fy: int) -> Promise | None:
    return ctx.db.scalar(select(Promise).where(Promise.company_id == ctx.company.id,
                                               Promise.metric_key == "ebitda_margin",
                                               Promise.horizon.like(f"%FY{fy % 100:02d}%"))
                         .order_by(Promise.id.desc()).limit(1))


def enrich(ctx: Ctx) -> EnrichResult:
    f = ctx.filing
    period = results_period(f.subject, f.published_at.date(), (f.raw or {}).get("voiceSummary") or "")
    dedupe = f"results:{ctx.company.id}:{period}"
    reaction, mv = price_reaction(ctx)
    sig = Signals(base_tier="P1", base_reason=f"{period} results", weight_pct=ctx.weight_pct, price_confirms=reaction)

    pages = pdf.pages_text(f.attachment_url, max_pages=60) if f.attachment_url else []
    if pages and not f.text:
        f.text = "\n".join(f"=== page {i + 1} ===\n{t}" for i, t in enumerate(pages[:6]))[:20000]
    screener_row = ctx.db.scalar(select(FinancialQ).where(FinancialQ.company_id == ctx.company.id,
                                                          FinancialQ.fiscal_label == period,
                                                          FinancialQ.source == "screener"))
    raw, method, notes, verified = None, None, [], False
    for name, fn in (("parser", lambda p: heuristic_extract(p, screener_row)), ("llm", llm_extract)):
        cand = fn(pages) if pages else None
        if not cand:
            continue
        ok, n = validate(cand, pages, screener_row)
        if ok:
            raw, method, notes, verified = cand, name, n, True
            break
        log.info("%s %s extraction failed validation: %s", ctx.company.symbol, name, n)

    lender = (ctx.company.sector or "") in ("Banks", "Financials")
    bank = bool(raw and raw.get("is_bank_format")) or lender
    rows, basis, unit_note, page = None, None, None, None
    if raw:
        k = raw["unit"]
        rows = {c: derive(to_crore(raw[c], k), raw.get("is_bank_format")) for c in ("current", "previous_quarter", "year_ago_quarter")}
        basis, page = raw["basis"], raw.get("page")
        unit_note = f"Rs crore (filed in {k})" if k != "crore" else "Rs crore"
        bank = raw.get("is_bank_format", False) or lender
    elif screener_row:
        method = "screener"
        q = {lbl: ctx.db.scalar(select(FinancialQ).where(FinancialQ.company_id == ctx.company.id,
                                                         FinancialQ.fiscal_label == lbl, FinancialQ.source == "screener"))
             for lbl in (period, fiscal.prev_quarter(period), fiscal.year_ago(period))}

        def from_q(r):
            if not r:
                return {f: None for f in FIELDS} | {"ebitda": None, "margin": None}
            return {"revenue": r.revenue, "other_income": r.other_income, "finance_costs": r.interest,
                    "depreciation": r.depreciation, "pbt": r.pbt, "tax": r.tax, "pat": r.pat,
                    "ebitda": r.ebitda, "margin": (r.ebitda / r.revenue * 100) if r.ebitda is not None and r.revenue else None}
        rows = {"current": from_q(q[period]), "previous_quarter": from_q(q[fiscal.prev_quarter(period)]),
                "year_ago_quarter": from_q(q[fiscal.year_ago(period)])}
        basis, unit_note = screener_row.basis, "Rs crore"
        notes = ["From screener.in's quarterly table (compiled from company filings); not checked against this PDF"]

    enrichment = {"period": period, "method": method, "basis": basis, "unit": unit_note, "page": page,
                  "bank_format": bank, "notes": notes, "ebitda_definition":
                  "EBITDA = revenue − operating expenses (before finance costs, depreciation, other income and exceptional items)"}
    context = []
    if not rows or rows["current"].get("pat") is None:
        return EnrichResult(
            title=f"{period} results filed, numbers not verified",
            summary="Couldn't verify the numbers automatically. Open the PDF to read them.",
            signals=sig, verify_ok=False, dedupe_key=dedupe, enrichment=enrichment,
            impact_line=impact_line(ctx, mv), context=context)

    cur, prv, yag = rows["current"], rows["previous_quarter"], rows["year_ago_quarter"]
    metrics = [("Revenue", "revenue"), ("EBITDA", "ebitda"), ("PBT", "pbt"), ("PAT", "pat")]
    if bank:
        metrics = [("Interest earned", "interest_earned"), ("Operating profit", "operating_profit"),
                   ("Provisions", "provisions"), ("PBT", "pbt"), ("PAT", "pat")]
        if cur.get("interest_earned") is None:
            metrics = [("Revenue", "revenue"), ("PBT", "pbt"), ("PAT", "pat")]
    table = []
    for name, key in metrics:
        table.append({"metric": name, "value": cur.get(key), "prev": prv.get(key), "year_ago": yag.get(key),
                      "qoq": fmt.pct_change(cur.get(key), prv.get(key)),
                      "yoy": fmt.pct_change(cur.get(key), yag.get(key))})
    if not bank and cur.get("margin") is not None:
        table.append({"metric": "EBITDA margin", "value": cur["margin"], "prev": prv.get("margin"),
                      "year_ago": yag.get("margin"), "is_pct": True,
                      "qoq": (cur["margin"] - prv["margin"]) if prv.get("margin") is not None else None,
                      "yoy": (cur["margin"] - yag["margin"]) if yag.get("margin") is not None else None})
    enrichment["table"] = table

    pat_yoy = fmt.pct_change(cur.get("pat"), yag.get("pat"))
    rev_yoy = fmt.pct_change(cur.get("revenue") or cur.get("interest_earned"), yag.get("revenue") or yag.get("interest_earned"))
    q, fy = fiscal.parse_label(period)
    guide = guided_margin(ctx, fy) if not bank else None
    if guide and cur.get("margin") is not None and guide.target_low is not None:
        lo, hi = guide.target_low, guide.target_high or guide.target_low
        band = f"{lo:g}–{hi:g}%" if hi != lo else f"{lo:g}%"
        context.append(f"EBITDA margin {cur['margin']:.1f}% vs {band} guided ({guide.made_in} call)")
        enrichment["guidance"] = {"text": guide.target_text, "made_in": guide.made_in, "quote": guide.quote,
                                  "page": guide.page, "promise_id": guide.id}
        gap = cur["margin"] - lo if cur["margin"] < lo else (cur["margin"] - hi if cur["margin"] > hi else 0)
        if abs(gap) > 3:
            sig.base_tier = "P0"
            sig.extra_reasons.append(f"Margin {abs(gap):.1f} pts {'below' if gap < 0 else 'above'} guidance")
    if pat_yoy is not None and abs(pat_yoy) > 20:
        sig.base_tier = "P0"
        sig.base_reason = f"{period} results, PAT {fmt.signed_pct(pat_yoy, 0)} YoY"
    if cur.get("margin") is not None and yag.get("margin") is not None:
        context.append(f"EBITDA margin {cur['margin']:.1f}%, {fmt.pts(cur['margin'] - yag['margin'])} vs a year ago")
    if screener_row is None and method != "screener":
        context.append("screener.in has not added this quarter yet; numbers checked against the PDF only")

    headline = f"{period} results: PAT {fmt.signed_pct(pat_yoy, 1)} YoY" if pat_yoy is not None else f"{period} results"
    metric_line = ", ".join(x for x in [
        f"Revenue {fmt.signed_pct(rev_yoy)} YoY" if rev_yoy is not None else None,
        f"margin {cur['margin']:.1f}%" if cur.get("margin") is not None else None,
    ] if x) or None
    return EnrichResult(title=headline, metric_line=metric_line, signals=sig, verify_ok=verified or method == "screener",
                        summary=free_one_liner(f, ctx.company.name), impact_line=impact_line(ctx, mv),
                        context=context, enrichment=enrichment, dedupe_key=dedupe,
                        facts=[{"k": "Basis", "v": (basis or "").capitalize(), "src": f"filing p.{page}" if page else "screener.in"}])
