from datetime import date, datetime, timedelta

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import portfolio
from ..models import CalendarItem, Chunk, Decision, Document, Event, FinancialQ, FinancialY, Promise, PromiseVerdict, Tripwire
from ..pull import cards, verdict
from ..push import tripwires as tw
from ..push.digest import decision_dict, event_card
from .common import DB, IST, company_or_404, doc_link, exposure, holding_of, research_row, thesis_health

router = APIRouter(tags=["companies"])


def _upcoming(db: Session, company_id: int, days: int = 10) -> list[CalendarItem]:
    today = datetime.now(IST).date()
    return db.scalars(select(CalendarItem).where(CalendarItem.company_id == company_id, CalendarItem.date >= today,
                                                 CalendarItem.date <= today + timedelta(days=days))
                      .order_by(CalendarItem.date)).all()


@router.get("/companies/{symbol}")
def company(symbol: str, db: Session = DB):
    c = company_or_404(db, symbol)
    r = research_row(db, c)
    h = holding_of(db, c)
    last = portfolio.latest_close(db, c.symbol)
    upcoming = _upcoming(db, c.id)
    today = datetime.now(IST).date()
    return {
        "symbol": c.symbol, "name": c.name, "sector": c.sector, "exchange": "NSE",
        "is_holding": c.is_holding, "is_research": c.is_research,
        "price": {"close": last.close, "date": last.date.isoformat(),
                  "label": f"EOD {last.date.day} {last.date.strftime('%b')}"} if last else None,
        "exposure": exposure(db, c),
        "research": {"status": r.status if r else "none", "updated_at": r.updated_at.isoformat() + "Z" if r else None,
                     "error": r.error if r else None},
        "scorecard": (r.cards or {}).get("scorecard") if r and r.cards else None,
        "thesis": h.thesis if h else None, "thesis_source": h.thesis_source if h else None,
        "health": thesis_health(db, c.id) if h else None,
        "coming_up": [{"date": u.date.isoformat(), "purpose": u.purpose} for u in upcoming],
        "prep_due": any((u.date - today).days <= 3 for u in upcoming),
        "decisions": [decision_dict(d) for d in db.scalars(select(Decision).where(Decision.company_id == c.id)
                                                            .order_by(Decision.created_at.desc()).limit(20))],
    }


@router.get("/companies/{symbol}/promises")
def promises(symbol: str, db: Session = DB):
    c = company_or_404(db, symbol)
    docs = {d.id: d for d in db.scalars(select(Document).where(Document.company_id == c.id)).all()}
    rows = db.execute(select(Promise, PromiseVerdict).outerjoin(PromiseVerdict, PromiseVerdict.promise_id == Promise.id)
                      .where(Promise.company_id == c.id)).all()
    order = {"missed": 0, "behind": 1, "late": 2, "dropped": 3, "kept": 4, "on_track": 5, "pending": 6}
    out = []
    for p, v in rows:
        d = docs.get(p.document_id)
        evidence = []
        for e in (v.evidence if v else []) or []:
            item = dict(e)
            if e.get("chunk_id"):
                ch = db.get(Chunk, e["chunk_id"])
                cd = docs.get(ch.document_id) if ch else None
                item["url"] = doc_link(cd, ch.page_from) if ch else None
            evidence.append(item)
        revisions, seen = [], {p.target_text}
        for r in reversed(p.repeats or []):  # latest first, one row per distinct target
            if r.get("target_text") and r["target_text"] not in seen:
                seen.add(r["target_text"])
                revisions.append(r)
        revisions = revisions[:2]
        out.append({
            "id": p.id, "metric": p.metric, "metric_key": p.metric_key, "made_in": p.made_in, "horizon": p.horizon,
            "target_text": p.target_text, "target_low": p.target_low, "target_high": p.target_high, "unit": p.unit,
            "quote": p.quote, "speaker": p.speaker, "page": p.page, "extractor": p.extractor,
            "source": {"label": f"{p.made_in} call" + (f", page {p.page}" if p.page else ""), "url": doc_link(d, p.page),
                       "document_id": d.id if d else None},
            "status": v.status if v else "pending", "actual_text": v.actual_text if v else None,
            "method": v.method if v else None, "evidence": evidence,
            "repeats": [r.get("made_in") for r in (p.repeats or []) if r.get("made_in")],
            "revisions": [{"made_in": r.get("made_in"), "target_text": r.get("target_text")} for r in revisions],
        })
    out.sort(key=lambda x: (order.get(x["status"], 9), x["made_in"]))
    return {"scorecard": verdict.scorecard(db, c.id), "promises": out,
            "documents": [{"id": d.id, "kind": d.kind, "period": d.period_label, "url": d.url, "pages": d.pages}
                          for d in sorted(docs.values(), key=lambda d: d.doc_date or date.min, reverse=True)]}


@router.get("/companies/{symbol}/financials")
def financials(symbol: str, db: Session = DB):
    c = company_or_404(db, symbol)
    qs = db.scalars(select(FinancialQ).where(FinancialQ.company_id == c.id, FinancialQ.source == "screener")
                    .order_by(FinancialQ.period_end)).all()
    ys = db.scalars(select(FinancialY).where(FinancialY.company_id == c.id).order_by(FinancialY.fy)).all()
    traj = cards.trajectory(db, c)
    return {
        "title": traj.get("title"),
        "basis": qs[-1].basis if qs else None,
        "quarters": [{"label": q.fiscal_label, "period_end": q.period_end.isoformat(), "revenue": q.revenue,
                      "ebitda": q.ebitda, "pat": q.pat, "pbt": q.pbt,
                      "opm": (q.ebitda / q.revenue * 100) if q.ebitda is not None and q.revenue else q.opm}
                     for q in qs[-12:]],
        "years": [{"fy": y.fy, "revenue": y.revenue, "ebitda": y.ebitda, "pat": y.pat, "opm": y.opm, "cfo": y.cfo,
                   "roce": y.roce, "total_debt": y.total_debt, "cash": y.cash} for y in ys[-6:]],
        "revenue_cagr_3y": traj.get("revenue_cagr_3y"), "pat_cagr_3y": traj.get("pat_cagr_3y"),
        "source": {"label": "screener.in, compiled from company filings",
                   "url": f"https://www.screener.in/company/{c.symbol}/consolidated/"},
    }


@router.get("/companies/{symbol}/cash")
def cash(symbol: str, db: Session = DB):
    c = company_or_404(db, symbol)
    r = research_row(db, c)
    card = (r.cards or {}).get("cash") if r and r.cards else None
    if not card or not card.get("available"):
        card = cards.cash_card(db, c, f"https://www.screener.in/company/{c.symbol}/consolidated/")
    return card


@router.get("/companies/{symbol}/story")
def story(symbol: str, db: Session = DB):
    c = company_or_404(db, symbol)
    r = research_row(db, c)
    cd = (r.cards or {}) if r else {}
    return {"business": cd.get("business") or {"available": False},
            "bullbear": cd.get("bullbear") or {"bull": [], "bear": []},
            "footnote": "Built only from annual reports and concall transcripts."}


@router.get("/companies/{symbol}/timeline")
def timeline(symbol: str, limit: int = 50, tier: str | None = None, db: Session = DB):
    c = company_or_404(db, symbol)
    q = select(Event).where(Event.company_id == c.id)
    if tier:
        q = q.where(Event.tier.in_(tier.split(",")))
    evs = db.scalars(q.order_by(Event.event_date.desc()).limit(min(limit, 200))).all()
    return {"events": [event_card(e, c) for e in evs]}


def _tripwire_dict(t: Tripwire) -> dict:
    return {"id": t.id, "kind": t.kind, "metric_key": t.metric_key, "op": t.op, "threshold": t.threshold,
            "label": t.label, "source": t.source, "enabled": t.enabled, "status": t.status,
            "value": t.last_value, "value_label": tw.fmt_value(t, t.last_value),
            "threshold_label": tw.fmt_value(t, t.threshold), "window_days": t.window_days}


@router.get("/companies/{symbol}/tripwires")
def get_tripwires(symbol: str, db: Session = DB):
    c = company_or_404(db, symbol)
    rows = db.scalars(select(Tripwire).where(Tripwire.company_id == c.id).order_by(Tripwire.id)).all()
    return {"tripwires": [_tripwire_dict(t) for t in rows], "metrics": EDITABLE}


EDITABLE = {"weight_pct": "Position weight (%)", "drawdown_pct": "Drawdown from your average cost (%)",
            "wc_days": "Working-capital days", "opm_q": "Quarterly EBITDA margin (%)",
            "key_exits_365d": "Key-person exits in 12 months"}


class TripwireIn(BaseModel):
    id: int | None = None
    metric_key: str
    op: str
    threshold: float
    label: str | None = None
    enabled: bool = True


@router.put("/companies/{symbol}/tripwires")
def put_tripwires(symbol: str, items: list[TripwireIn], db: Session = DB):
    """Replace the user's tripwires. Auto ones can be edited (threshold, on/off) but are kept."""
    c = company_or_404(db, symbol)
    existing = {t.id: t for t in db.scalars(select(Tripwire).where(Tripwire.company_id == c.id)).all()}
    keep = set()
    for it in items:
        if it.metric_key not in EDITABLE or it.op not in (">", "<"):
            continue
        t = existing.get(it.id) if it.id else None
        if not t:
            kind = {"weight_pct": "weight", "drawdown_pct": "drawdown", "key_exits_365d": "event_count"}.get(it.metric_key, "metric")
            t = Tripwire(company_id=c.id, kind=kind, metric_key=it.metric_key, source="user",
                         window_days=365 if kind == "event_count" else None)
            db.add(t)
        changed = (t.op, t.threshold) != (it.op, it.threshold)
        t.op, t.threshold, t.enabled = it.op, it.threshold, it.enabled
        if changed or not t.label:
            t.label = it.label or f"{EDITABLE[it.metric_key]} {'above' if it.op == '>' else 'below'} {it.threshold:g}"
            t.status = "ok"
        db.flush()
        keep.add(t.id)
    gone = [tid for tid, t in existing.items() if tid not in keep and t.source == "user"]
    if gone:
        db.execute(delete(Tripwire).where(Tripwire.id.in_(gone)))
    db.commit()
    if c.is_holding:
        tw.evaluate_all(db)
        db.commit()
    return get_tripwires(symbol, db)


@router.get("/companies/{symbol}/prep")
def prep(symbol: str, db: Session = DB):
    c = company_or_404(db, symbol)
    out = cards.prep_questions(db, c)
    out["coming_up"] = [{"date": u.date.isoformat(), "purpose": u.purpose} for u in _upcoming(db, c.id)]
    return out
