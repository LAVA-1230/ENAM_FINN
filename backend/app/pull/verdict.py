"""Promise verdicts (spec 8.3). Numeric promises are judged in Python against reported quarters; the LLM
never does arithmetic. Non-numeric promises go to one smart-model call per company (if a key is set).

Statuses: kept / missed (horizon passed), late, on_track / behind (horizon open), pending (no data),
dropped (stated before, absent from the last two calls)."""
import logging
import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import fiscal
from ..llm import client as llm
from ..llm.schemas import JudgeOut
from ..models import Company, Document, FinancialQ, FinancialY, Promise, PromiseVerdict
from . import retrieval

log = logging.getLogger(__name__)
NUMERIC = ("revenue_growth", "ebitda_margin", "pat_growth", "net_debt", "capex")


def horizon_quarters(h: str | None) -> list[str] | None:
    if not h:
        return None
    h = h.upper().replace(" ", "")
    m = re.match(r"^Q([1-4])FY'?(\d{2})$", h)
    if m:
        return [f"Q{m.group(1)} FY{m.group(2)}"]
    m = re.match(r"^H([12])FY'?(\d{2})$", h)
    if m:
        fy = int(m.group(2))
        return [f"Q{q} FY{fy:02d}" for q in ((1, 2) if m.group(1) == "1" else (3, 4))]
    fy = fiscal.parse_fy(h)
    if fy and re.match(r"^(FY|BYFY|BYMAR|MAR)", h):
        return fiscal.quarters_of_fy(fy)
    return None


def _q(db: Session, company_id: int) -> dict[str, FinancialQ]:
    return {r.fiscal_label: r for r in db.scalars(select(FinancialQ).where(FinancialQ.company_id == company_id,
                                                                            FinancialQ.source == "screener"))}


def _sum(rows, attr):
    vals = [getattr(r, attr) for r in rows]
    return sum(vals) if vals and all(v is not None for v in vals) else None


def judge_numeric(db: Session, p: Promise, qs: dict[str, FinancialQ], screener_url: str | None) -> dict | None:
    lo, hi = p.target_low, p.target_high if p.target_high is not None else p.target_low
    if p.metric_key == "net_debt":
        fy = db.scalars(select(FinancialY).where(FinancialY.company_id == p.company_id, FinancialY.total_debt.is_not(None))
                        .order_by(FinancialY.fy.desc()).limit(1)).first()
        if not fy or lo is None:
            return None
        nd = (fy.total_debt or 0) - (fy.cash or 0)
        hz = fiscal.parse_fy(p.horizon or "")
        passed = hz is not None and fiscal.parse_fy(fy.fy) >= hz
        ok = nd <= (hi if hi is not None else lo)
        return {"status": ("kept" if ok else "missed") if passed else ("on_track" if ok else "behind"),
                "actual_value": nd, "actual_text": f"Net debt ₹{nd:,.0f} cr at end of {fy.fy}",
                "evidence": [{"kind": "table", "label": f"{fy.fy} balance sheet, screener.in", "url": screener_url}]}
    if p.metric_key == "capex":
        hz = fiscal.parse_fy(p.horizon or "")
        fy = db.scalar(select(FinancialY).where(FinancialY.company_id == p.company_id,
                                                FinancialY.fy == fiscal.fy_label(hz))) if hz else None
        if not fy or fy.capex is None or lo is None:
            return None  # capex is reported annually: pending until the year closes
        ok = fy.capex >= 0.85 * lo
        return {"status": "kept" if ok else "missed", "actual_value": fy.capex,
                "actual_text": f"Capex ₹{fy.capex:,.0f} cr in {fy.fy} vs ₹{lo:,.0f} cr planned",
                "evidence": [{"kind": "table", "label": f"{fy.fy} cash flow, screener.in", "url": screener_url}]}

    quarters = horizon_quarters(p.horizon)
    if not quarters or lo is None:
        return None
    have = [q for q in quarters if q in qs and qs[q].revenue]
    if not have:
        return {"status": "pending", "actual_text": f"No results reported yet for {p.horizon}", "actual_value": None,
                "evidence": []}
    complete = len(have) == len(quarters)
    rows = [qs[q] for q in have]
    span = have[0] if len(have) == 1 else f"{have[0].split()[0]}–{have[-1]}"
    ev = [{"kind": "table", "label": f"{span} quarterly results, screener.in (compiled from filings)", "url": screener_url}]
    pct = (p.unit or "%").strip().startswith("%")

    if p.metric_key == "ebitda_margin":
        e, r = _sum(rows, "ebitda"), _sum(rows, "revenue")
        if e is None or not r:
            return None
        val = e / r * 100
        per_q = ", ".join(f"{qs[q].ebitda / qs[q].revenue * 100:.1f}% in {q.split()[0]}" for q in have)
        if val >= lo - 0.5:
            status = "kept" if complete else "on_track"
        else:
            status = "missed" if complete else "behind"
        return {"status": status, "actual_value": val, "evidence": ev,
                "actual_text": f"Delivered {per_q}" + (f" ({val:.1f}% for {span})" if len(have) > 1 else "")}

    attr = "pat" if p.metric_key == "pat_growth" else "revenue"
    if p.metric_key not in ("revenue_growth", "pat_growth", "volume"):
        return None
    if p.metric_key == "volume":
        return None  # volumes are not in the financial tables: LLM judge or pending
    cur = _sum(rows, attr)
    if not pct:  # absolute target in Rs crore, e.g. "revenue of Rs 10,000 cr in FY27"
        if cur is None:
            return None
        run_rate = cur / len(have) * len(quarters)
        ok = (cur if complete else run_rate) >= lo * 0.98
        return {"status": ("kept" if ok else "missed") if complete else ("on_track" if ok else "behind"),
                "actual_value": cur, "evidence": ev,
                "actual_text": f"₹{cur:,.0f} cr in {span}" + ("" if complete else f", run-rate ₹{run_rate:,.0f} cr")}
    prev = [qs.get(fiscal.year_ago(q)) for q in have]
    if any(r is None or getattr(r, attr) is None for r in prev):
        return None
    base = sum(getattr(r, attr) for r in prev)
    if cur is None or not base:
        return None
    growth = (cur - base) / abs(base) * 100
    per_q = ", ".join(f"{(getattr(qs[q], attr) - getattr(qs[fiscal.year_ago(q)], attr)) / abs(getattr(qs[fiscal.year_ago(q)], attr)) * 100:+.1f}% in {q.split()[0]}"
                      for q in have if getattr(qs[fiscal.year_ago(q)], attr))
    status = ("kept" if complete else "on_track") if growth >= lo - 1 else ("missed" if complete else "behind")
    label = "Revenue" if attr == "revenue" else "PAT"
    return {"status": status, "actual_value": growth, "evidence": ev,
            "actual_text": f"{label} grew {per_q.replace('-', chr(8722))} YoY"}


def judge_dropped(db: Session, p: Promise, latest_docs: list[int]) -> dict | None:
    """Stated in an older call, not repeated, and absent from the last two transcripts."""
    if p.document_id in latest_docs or any(r.get("document_id") in latest_docs for r in (p.repeats or [])):
        return None
    hits = retrieval.search(db, p.company_id, f"{p.metric} {p.target_text}", k=3, doc_ids=latest_docs)
    words = [w for w in retrieval.tokens(p.metric) if len(w) > 3]
    if hits and words and any(all(w in c.text.lower() for w in words) for c, _ in hits):
        return None
    return {"status": "dropped", "actual_value": None, "evidence": [],
            "actual_text": "Not mentioned in the last two concalls"}


def judge_llm(db: Session, company: Company, items: list[Promise]) -> dict[int, dict]:
    if not items or not llm.available():
        return {}
    evidence, sources = [], {}
    for p in items:
        for c, _ in retrieval.search(db, company.id, f"{p.metric} {p.target_text} {p.quote[:120]}", k=3):
            if c.id in sources:
                continue
            d = db.get(Document, c.document_id)
            if d.id == p.document_id:
                continue
            n = len(sources) + 1
            sources[c.id] = n
            evidence.append({"n": n, "chunk_id": c.id, "label": f"{d.period_label} {d.kind.replace('_', ' ')}, p.{c.page_from}",
                             "text": c.text[:1200]})
    if not evidence:
        return {}
    try:
        out = llm.complete("promise_judge", "smart", {
            "today": date.today().isoformat(),
            "promises": [{"promise_id": p.id, "metric": p.metric, "target": p.target_text, "horizon": p.horizon,
                          "made_in": p.made_in, "quote": p.quote} for p in items],
            "evidence": "\n\n".join(f"[{e['n']}] {e['label']}\n{e['text']}" for e in evidence)},
            schema=JudgeOut, job="research")
    except Exception as e:  # noqa: BLE001
        log.info("promise judge failed: %s", e)
        return {}
    by_n = {e["n"]: e for e in evidence}
    res = {}
    for v in out["verdicts"]:
        cites = [by_n[n] for n in v.get("citations", []) if n in by_n]
        if v["status"] != "pending" and not cites:
            continue  # no evidence, no verdict
        res[v["promise_id"]] = {"status": v["status"], "actual_text": re.sub(r"\s*\[\d+\]", "", v.get("actual_text") or "") or None,
                                "actual_value": None, "method": "llm",
                                "evidence": [{"kind": "chunk", "chunk_id": e["chunk_id"], "label": e["label"]} for e in cites]}
    return res


def run(db: Session, company: Company, screener_url: str | None) -> dict:
    qs = _q(db, company.id)
    promises = db.scalars(select(Promise).where(Promise.company_id == company.id)).all()
    latest_docs = [d.id for d in db.scalars(select(Document).where(Document.company_id == company.id,
                                                                    Document.kind == "transcript")
                                            .order_by(Document.doc_date.desc()).limit(2))]
    verdicts, leftovers = {}, []
    for p in promises:
        v = judge_numeric(db, p, qs, screener_url) if p.metric_key in NUMERIC or p.target_low is not None else None
        if v:
            v["method"] = "rule"
            verdicts[p.id] = v
            continue
        dv = judge_dropped(db, p, latest_docs) if p.metric_key in ("plant", "launch", "market_share", "other", "capex", "volume") else None
        if dv:
            dv["method"] = "rule"
            verdicts[p.id] = dv
            continue
        leftovers.append(p)
    verdicts.update(judge_llm(db, company, leftovers[:12]))
    for p in promises:
        v = verdicts.get(p.id) or {"status": "pending", "actual_text": None, "actual_value": None, "evidence": [],
                                   "method": "rule"}
        row = db.scalar(select(PromiseVerdict).where(PromiseVerdict.promise_id == p.id))
        if not row:
            row = PromiseVerdict(promise_id=p.id)
            db.add(row)
        row.status, row.actual_text, row.actual_value = v["status"], v.get("actual_text"), v.get("actual_value")
        row.evidence, row.method = v.get("evidence", []), v.get("method", "rule")
    db.flush()
    return scorecard(db, company.id)


def scorecard(db: Session, company_id: int) -> dict:
    rows = db.execute(select(Promise, PromiseVerdict).join(PromiseVerdict, PromiseVerdict.promise_id == Promise.id)
                      .where(Promise.company_id == company_id)).all()
    counts: dict[str, int] = {}
    for _, v in rows:
        counts[v.status] = counts.get(v.status, 0) + 1
    due = sum(counts.get(s, 0) for s in ("kept", "missed", "late"))
    open_ = sum(counts.get(s, 0) for s in ("on_track", "behind"))
    delivered = counts.get("kept", 0) + counts.get("late", 0)
    if due:
        sentence = f"Management delivered {delivered} of {due} promises that came due"
    elif open_:
        sentence = f"{counts.get('on_track', 0)} of {open_} open promises on track so far"
    else:
        sentence = "No promise has come due yet"
    return {"sentence": sentence, "counts": counts, "total": len(rows), "due": due, "delivered": delivered, "open": open_}

