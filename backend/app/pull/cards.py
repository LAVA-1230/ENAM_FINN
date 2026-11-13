"""Research cards (spec 8.4, 8.5, 8.8): cash quality, business snapshot, bull vs bear, concall prep.

Cash quality and the trajectory are computed in Python from screener.in's tables (compiled from the
annual reports). The business snapshot reads the annual report's own pages. Bull vs bear is written from
these structured cards only (smart model if a key is set, otherwise templates), each point citing its card."""
import logging
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import fmt
from ..llm import client as llm
from ..llm.guard import has_banned
from ..llm.schemas import BullBear, BusinessOut, PrepOut
from ..models import Company, Document, Event, FinancialQ, FinancialY, Promise, PromiseVerdict, Tripwire
from . import retrieval

log = logging.getLogger(__name__)


def _years(db: Session, company_id: int, n: int = 6) -> list[FinancialY]:
    rows = db.scalars(select(FinancialY).where(FinancialY.company_id == company_id).order_by(FinancialY.fy)).all()
    return [r for r in rows if r.revenue is not None][-n:]


def cash_card(db: Session, company: Company, screener_url: str | None) -> dict:
    ys = _years(db, company.id)
    if not ys:
        return {"available": False}
    src = f"screener.in, compiled from annual reports ({ys[0].fy}–{ys[-1].fy})"
    rows, flags = [], []
    conv = [(y.fy, y.cfo / y.pat) for y in ys if y.cfo is not None and y.pat and y.pat > 0]
    if conv:
        last3 = conv[-3:]
        avg = sum(c for _, c in last3) / len(last3)
        flag = "healthy" if avg >= 0.8 else "watch" if avg >= 0.5 else "red"
        rows.append({"key": "cfo_pat", "label": "Operating cash flow ÷ PAT", "value": f"{avg:.2f}x",
                     "detail": f"3-year average; {conv[-1][0]} {conv[-1][1]:.2f}x", "flag": flag,
                     "series": [{"fy": f, "v": round(c, 2)} for f, c in conv]})
        if flag != "healthy":
            flags.append(f"Profits converted to cash at {avg:.2f}x over 3 years")
    for key, label in (("receivable_days", "Receivable days"), ("inventory_days", "Inventory days"),
                       ("wc_days", "Working-capital days")):
        s = [(y.fy, getattr(y, key)) for y in ys if getattr(y, key) is not None]
        if len(s) < 2:
            continue
        rising = len(s) >= 3 and s[-1][1] > s[-2][1] > s[-3][1]
        rows.append({"key": key, "label": label, "value": f"{s[-1][1]:.0f}",
                     "detail": f"{s[0][0]} {s[0][1]:.0f} → {s[-1][0]} {s[-1][1]:.0f}",
                     "flag": "watch" if rising else "healthy", "series": [{"fy": f, "v": v} for f, v in s]})
        if rising:
            flags.append(f"{label} rose two years running, to {s[-1][1]:.0f}")
    debt = [(y.fy, (y.total_debt or 0) - (y.cash or 0), y.net_worth) for y in ys if y.total_debt is not None]
    if debt:
        fy, nd, nw = debt[-1]
        de = (ys[-1].total_debt or 0) / nw if nw else None
        rows.append({"key": "net_debt", "label": "Net debt" if nd > 0 else "Net cash",
                     "value": fmt.crore(abs(nd)), "detail": f"{fy}; debt/equity {de:.2f}" if de is not None else fy,
                     "flag": "watch" if de and de > 1 else "healthy",
                     "series": [{"fy": f, "v": round(v)} for f, v, _ in debt]})
    fcf = [(y.fy, y.fcf) for y in ys if y.fcf is not None]
    if fcf:
        neg = sum(1 for _, v in fcf[-3:] if v < 0)
        rows.append({"key": "fcf", "label": "Free cash flow", "value": fmt.crore(fcf[-1][1]), "detail": fcf[-1][0],
                     "flag": "watch" if neg >= 2 else "healthy", "series": [{"fy": f, "v": v} for f, v in fcf]})
    return {"available": True, "rows": rows, "flags": flags, "source": src, "url": screener_url}


def trajectory(db: Session, company: Company) -> dict:
    ys = _years(db, company.id)
    qs = db.scalars(select(FinancialQ).where(FinancialQ.company_id == company.id, FinancialQ.source == "screener")
                    .order_by(FinancialQ.period_end)).all()
    out = {"years": [{"fy": y.fy, "revenue": y.revenue, "pat": y.pat, "opm": y.opm, "roce": y.roce} for y in ys],
           "quarters": [{"label": q.fiscal_label, "revenue": q.revenue, "ebitda": q.ebitda, "pat": q.pat,
                         "opm": (q.ebitda / q.revenue * 100) if q.ebitda is not None and q.revenue else None}
                        for q in qs[-8:]]}
    if len(ys) >= 4 and ys[-4].revenue and ys[-1].revenue and ys[-4].revenue > 0:
        out["revenue_cagr_3y"] = ((ys[-1].revenue / ys[-4].revenue) ** (1 / 3) - 1) * 100
    if len(ys) >= 4 and ys[-4].pat and ys[-1].pat and ys[-4].pat > 0 and ys[-1].pat > 0:
        out["pat_cagr_3y"] = ((ys[-1].pat / ys[-4].pat) ** (1 / 3) - 1) * 100
    out["title"] = chart_title(out["quarters"])
    return out


def chart_title(quarters: list[dict]) -> str:
    """One sentence that states the finding, for the revenue/margin chart."""
    q = [x for x in quarters if x["revenue"]]
    if len(q) < 5:
        return "Quarterly revenue and EBITDA margin"
    yoy = (q[-1]["revenue"] - q[-5]["revenue"]) / q[-5]["revenue"] * 100 if q[-5]["revenue"] else None
    m = [x["opm"] for x in q if x["opm"] is not None]
    falls = 0
    for a, b in zip(m[::-1], m[-2::-1]):
        if a < b:
            falls += 1
        else:
            break
    rev = f"Revenue {fmt.signed_pct(yoy, 0)} YoY in {q[-1]['label']}" if yoy is not None else "Revenue"
    if falls >= 2:
        return f"{rev}; margin fell for {falls} quarters in a row"
    if len(m) >= 2:
        return f"{rev}; margin {m[-1]:.1f}%, {fmt.pts(m[-1] - m[-2])} on the quarter"
    return rev


def business_card(db: Session, company: Company) -> dict:
    """Segments from the annual report's pages (fast model). Without a key: the report's own words, quoted."""
    ar = db.scalar(select(Document).where(Document.company_id == company.id, Document.kind == "annual_report")
                   .order_by(Document.doc_date.desc()).limit(1))
    if not ar or not ar.page_texts:
        return {"available": False}
    pages = {int(k): v for k, v in ar.page_texts.items()}
    sel = (ar.selected_pages or {})
    if llm.available():
        nums = sorted(set(sel.get("segments", [])[:8] + sel.get("mdna", [])[:6]))
        text = "\n".join(f"=== page {n} ===\n{pages[n]}" for n in nums if n in pages)[:60000]
        try:
            out = llm.complete("business_extract", "fast", {"company": company.name, "text": text},
                               schema=BusinessOut, job="research")
            segs = [s for s in out["segments"] if s.get("name")]
            total = sum(s["revenue"] for s in segs if s.get("revenue")) or None
            for s in segs:
                if s.get("share_pct") is None and total and s.get("revenue"):
                    s["share_pct"] = s["revenue"] / total * 100  # computed in Python, not by the model
            return {"available": True, "method": "llm", "segments": segs, "unit": out.get("unit"), "period": out.get("period"),
                    "geography": out.get("geography", []), "description": out.get("description"),
                    "document": {"id": ar.id, "label": f"Annual report {ar.period_label}", "url": ar.url}}
        except Exception as e:  # noqa: BLE001
            log.info("business llm failed: %s", e)
    hits = retrieval.search(db, company.id, "company business segments products brands operates manufacturer leading", k=4,
                            doc_ids=[ar.id])
    quotes = []
    for c, _ in hits:
        sents = [s.strip() for s in re.split(r"(?<=[.])\s+", c.text) if 60 <= len(s.strip()) <= 260
                 and re.search(r"\b(we|company|our)\b", s, re.I)]
        if sents:
            quotes.append({"text": sents[0], "page": c.page_from})
        if len(quotes) >= 2:
            break
    return {"available": bool(quotes), "method": "quote", "segments": [], "quotes": quotes,
            "document": {"id": ar.id, "label": f"Annual report {ar.period_label}", "url": ar.url}}


def facts_for_bullbear(db: Session, company: Company, cash: dict, traj: dict, score: dict) -> list[dict]:
    facts = []

    def add(text, card):
        facts.append({"id": f"f{len(facts) + 1}", "text": text, "card": card})
    if traj.get("revenue_cagr_3y") is not None:
        add(f"Revenue 3-year CAGR {traj['revenue_cagr_3y']:.1f}%", "numbers")
    if traj.get("pat_cagr_3y") is not None:
        add(f"PAT 3-year CAGR {traj['pat_cagr_3y']:.1f}%", "numbers")
    q = [x for x in traj.get("quarters", []) if x.get("opm") is not None]
    if len(q) >= 5:
        add(f"EBITDA margin {q[-1]['opm']:.1f}% in {q[-1]['label']} vs {q[-5]['opm']:.1f}% a year earlier", "numbers")
    for r in cash.get("rows", []):
        add(f"{r['label']}: {r['value']} ({r['detail']})", "cash")
    add(score["sentence"], "promises")
    rows = db.execute(select(Promise, PromiseVerdict).join(PromiseVerdict, PromiseVerdict.promise_id == Promise.id)
                      .where(Promise.company_id == company.id)).all()
    for p, v in rows:
        if v.status in ("kept", "missed", "behind", "dropped", "on_track") and v.actual_text:
            add(f"{p.metric} target {p.target_text} ({p.made_in} call): {v.status.replace('_', ' ')}; {v.actual_text}", "promises")
    return facts[:24]


def bull_bear(db: Session, company: Company, cash: dict, traj: dict, score: dict) -> dict:
    facts = facts_for_bullbear(db, company, cash, traj, score)
    by_id = {f["id"]: f for f in facts}
    if llm.available() and len(facts) >= 4:
        try:
            out = llm.complete("bullbear", "smart", {"company": company.name,
                                                     "facts": "\n".join(f"{f['id']}: {f['text']}" for f in facts)},
                               schema=BullBear, job="research")
            clean = {}
            for side in ("bull", "bear"):
                # guard: every point must cite an input fact; banned words are dropped
                clean[side] = [{"text": p["text"][:140], "source": p["source"], "card": by_id[p["source"]]["card"],
                                "fact": by_id[p["source"]]["text"]}
                               for p in out[side] if p.get("source") in by_id and not has_banned(p["text"])][:3]
            if clean["bull"] and clean["bear"]:
                return {"method": "llm", **clean}
        except Exception as e:  # noqa: BLE001
            log.info("bullbear llm failed: %s", e)
    return template_bull_bear(facts)


def template_bull_bear(facts: list[dict]) -> dict:
    bull, bear = [], []
    for f in facts:
        t = f["text"]
        m = re.search(r"(Revenue|PAT) 3-year CAGR (-?[\d.]+)%", t)
        if m:
            (bull if float(m.group(2)) >= 10 else bear).append(f)
            continue
        m = re.search(r"EBITDA margin ([\d.]+)% in .* vs ([\d.]+)%", t)
        if m:
            (bull if float(m.group(1)) >= float(m.group(2)) else bear).append(f)
            continue
        if ": kept" in t or ": on track" in t:
            bull.append(f)
        elif re.search(r": (missed|behind|dropped)", t):
            bear.append(f)
        elif "cash flow ÷ PAT" in t:
            m = re.search(r"([\d.]+)x", t)
            if m:
                (bull if float(m.group(1)) >= 0.8 else bear).append(f)
        elif t.startswith("Net cash"):
            bull.append(f)
    pick = lambda xs: [{"text": x["text"][:140], "source": x["id"], "card": x["card"], "fact": x["text"]} for x in xs[:3]]  # noqa: E731
    return {"method": "template", "bull": pick(bull), "bear": pick(bear)}


def prep_questions(db: Session, company: Company) -> dict:
    """Concall prep: templated from missed/behind/dropped promises, tripwires near or hit, and KMP changes."""
    qs = []
    rows = db.execute(select(Promise, PromiseVerdict).join(PromiseVerdict, PromiseVerdict.promise_id == Promise.id)
                      .where(Promise.company_id == company.id)).all()
    for p, v in rows:
        if v.status in ("missed", "behind"):
            qs.append({"text": f"{p.horizon} {p.metric.lower()} guidance was {p.target_text}; {v.actual_text or 'delivery is behind'}. "
                               f"Is the guidance unchanged?", "why": f"Promise {v.status}", "promise_id": p.id})
        elif v.status == "dropped":
            qs.append({"text": f"In the {p.made_in} call you committed to {p.target_text} on {p.metric.lower()}. What is the status?",
                       "why": "Not mentioned in the last two calls", "promise_id": p.id})
    for t in db.scalars(select(Tripwire).where(Tripwire.company_id == company.id, Tripwire.status.in_(["near", "hit"]))):
        if t.metric_key == "wc_days":
            qs.append({"text": f"Working-capital days are at {t.last_value:.0f}. What is driving it, and where should it settle?",
                       "why": f"Tripwire {t.status}"})
    for e in db.scalars(select(Event).where(Event.company_id == company.id, Event.category == "kmp_change",
                                            Event.tier.in_(["P0", "P1"])).order_by(Event.event_date.desc()).limit(2)):
        qs.append({"text": f"On the change: {e.title}. How does it affect the plan you laid out?", "why": "Management change",
                   "event_id": e.id})
    qs = qs[:5]
    if qs and llm.available():
        try:
            out = llm.complete("prep_wording", "fast", {"questions": [q["text"] for q in qs]}, schema=PrepOut, job="prep")
            if len(out["questions"]) == len(qs):
                for q, t in zip(qs, out["questions"]):
                    q["text"] = t
        except Exception as e:  # noqa: BLE001
            log.info("prep wording failed: %s", e)
    return {"questions": qs}
