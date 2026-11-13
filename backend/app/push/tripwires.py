"""Tripwires (spec 9.1): pre-set sell-review triggers per holding, evaluated after every ingest.

Standard ones exist for every holding; promise-based ones are added when research is ready.
Status: ok, near (within 10% of the limit), hit. A new hit creates a P0 'tripwire' event."""
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import portfolio
from ..models import Company, Event, FinancialQ, FinancialY, Tripwire
from .ingest import get_settings_row
from .score import Signals, score_event

STANDARD = {
    "key_exits": ("event_count", "key_exits_365d", ">", 1, "Another key person exits within 12 months"),
    "weight": ("weight", "weight_pct", ">", 10, "Position weight above 10%"),
    "drawdown": ("drawdown", "drawdown_pct", ">", 25, "Drawdown from your average cost above 25%"),
}


def ensure_standard(db: Session, company: Company):
    s = get_settings_row(db)
    defaults = s.tripwire_defaults or {}
    for key, (kind, metric, op, thr, label) in STANDARD.items():
        if not defaults.get(key, True):
            continue
        exists = db.scalar(select(Tripwire).where(Tripwire.company_id == company.id, Tripwire.metric_key == metric,
                                                  Tripwire.source == "auto"))
        if not exists:
            db.add(Tripwire(company_id=company.id, kind=kind, metric_key=metric, op=op, threshold=thr, label=label,
                            window_days=365 if kind == "event_count" else None, source="auto"))
    fy = db.scalars(select(FinancialY).where(FinancialY.company_id == company.id, FinancialY.wc_days.is_not(None))
                    .order_by(FinancialY.fy.desc()).limit(1)).first()
    if fy and defaults.get("wc_days", True) and not db.scalar(select(Tripwire).where(
            Tripwire.company_id == company.id, Tripwire.metric_key == "wc_days")):
        thr = round(fy.wc_days + 10)
        db.add(Tripwire(company_id=company.id, kind="metric", metric_key="wc_days", op=">", threshold=thr,
                        label=f"Working-capital days above {thr} ({fy.fy}: {fy.wc_days:.0f})", source="auto"))
    db.flush()


def add_promise_tripwire(db: Session, company: Company, metric_key: str, low: float, label_src: str):
    """From a missed/behind margin promise: trip if the quarterly margin falls 2 pts below the guided floor."""
    if metric_key != "ebitda_margin":
        return
    thr = round(low - 2, 1)
    if db.scalar(select(Tripwire).where(Tripwire.company_id == company.id, Tripwire.metric_key == "opm_q")):
        return
    db.add(Tripwire(company_id=company.id, kind="metric", metric_key="opm_q", op="<", threshold=thr,
                    label=f"Quarterly EBITDA margin below {thr:g}% ({label_src})", source="auto"))
    db.flush()


def current_value(db: Session, t: Tripwire, company: Company, book: dict) -> float | None:
    pos = book["positions"].get(company.symbol)
    if t.metric_key == "weight_pct":
        return pos["weight"] if pos else None
    if t.metric_key == "drawdown_pct":
        if not pos or not pos["avg_cost"]:
            return None
        return max(0.0, (pos["avg_cost"] - pos["close"]) / pos["avg_cost"] * 100)
    if t.metric_key == "key_exits_365d":
        since = datetime.utcnow() - timedelta(days=t.window_days or 365)
        evs = db.scalars(select(Event).where(Event.company_id == company.id, Event.category.in_(["kmp_change", "auditor_change"]),
                                             Event.event_date >= since)).all()
        return float(sum(1 for e in evs if (e.enrichment or {}).get("key_role")
                         and (e.enrichment or {}).get("change") in ("resignation", "cessation")))
    if t.metric_key == "wc_days":
        fy = db.scalars(select(FinancialY).where(FinancialY.company_id == company.id, FinancialY.wc_days.is_not(None))
                        .order_by(FinancialY.fy.desc()).limit(1)).first()
        return fy.wc_days if fy else None
    if t.metric_key == "opm_q":
        q = db.scalars(select(FinancialQ).where(FinancialQ.company_id == company.id, FinancialQ.revenue.is_not(None))
                       .order_by(FinancialQ.period_end.desc()).limit(1)).first()
        return (q.ebitda / q.revenue * 100) if q and q.revenue and q.ebitda is not None else None
    return t.last_value


def status_of(t: Tripwire, v: float | None) -> str:
    if v is None:
        return "ok"
    if (t.op == ">" and v > t.threshold) or (t.op == "<" and v < t.threshold):
        return "hit"
    margin = abs(t.threshold) * 0.10 if t.threshold else 1
    if t.kind == "event_count":
        return "near" if v >= t.threshold else "ok"
    if (t.op == ">" and v >= t.threshold - margin) or (t.op == "<" and v <= t.threshold + margin):
        return "near"
    return "ok"


def fmt_value(t: Tripwire, v: float | None) -> str:
    if v is None:
        return "n/a"
    if t.metric_key in ("weight_pct", "drawdown_pct", "opm_q"):
        return f"{v:.1f}%"
    return f"{v:.0f}"


def evaluate_all(db: Session) -> dict:
    s = get_settings_row(db)
    book = portfolio.book(db)
    counts = {"ok": 0, "near": 0, "hit": 0, "new_hits": 0}
    for c in db.scalars(select(Company).where(Company.is_holding.is_(True))).all():
        ensure_standard(db, c)
        for t in db.scalars(select(Tripwire).where(Tripwire.company_id == c.id, Tripwire.enabled.is_(True))).all():
            v = current_value(db, t, c, book)
            new = status_of(t, v)
            was = t.status
            t.last_value, t.status = v, new
            counts[new] += 1
            if new == "hit" and was != "hit":
                counts["new_hits"] += 1
                pos = book["positions"].get(c.symbol)
                sig = Signals(base_tier="P0", base_reason="Tripwire hit", locked=True,
                              weight_pct=pos["weight"] if pos else None)
                sig.extra_reasons.append(f"Your limit: {t.label.lower()}")
                tier, score, reasons = score_event("tripwire", sig, s.tier_overrides)
                key = f"tripwire:{t.id}:{datetime.utcnow().date().isoformat()}"
                if not db.scalar(select(Event.id).where(Event.dedupe_key == key)):
                    ev = Event(company_id=c.id, kind="tripwire", category="tripwire", tier=tier, score=score,
                                 reasons=reasons, dedupe_key=key, event_date=datetime.utcnow(),
                                 title=f"Tripwire hit: {t.label}",
                                 metric_line=f"Now {fmt_value(t, v)}, your limit {t.op} {fmt_value(t, t.threshold)}",
                                 impact_line=f"{pos['weight']:.1f}% of your book" if pos else None,
                                 enrichment={"tripwire_id": t.id, "value": v, "threshold": t.threshold, "op": t.op},
                                 context=[f"Set {'by FINN from your holding data' if t.source == 'auto' else 'by you'}"],
                                 facts=[], verify_ok=True)
                    db.add(ev)
                    db.flush()
                    if ev.tier == "P0":
                        from . import notify
                        notify.notify_event(db, ev, c)
    db.flush()
    return counts


def count_by_company(db: Session) -> dict[int, dict]:
    rows = db.execute(select(Tripwire.company_id, Tripwire.status, func.count()).where(Tripwire.enabled.is_(True))
                      .group_by(Tripwire.company_id, Tripwire.status)).all()
    out: dict[int, dict] = {}
    for cid, st, n in rows:
        out.setdefault(cid, {})[st] = n
    return out

