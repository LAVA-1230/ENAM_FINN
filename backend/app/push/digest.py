"""The windowed brief (spec 7.7). Templated, no LLM: header, attention, FYI, routine (counted), coming up."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import fmt, portfolio
from ..models import CalendarItem, Company, Decision, Event, JobRun, PriceDaily, Tripwire
from ..sources.prices import latest_date
from .ingest import get_settings_row
from .score import CATEGORY_LABEL

IST = timezone(timedelta(hours=5, minutes=30))
WINDOWS = {"24h": timedelta(hours=24), "3d": timedelta(days=3), "7d": timedelta(days=7), "30d": timedelta(days=30)}


def resolve_window(db: Session, window: str, frm: str | None, to: str | None, now: datetime | None = None) -> tuple[datetime, datetime, str]:
    now = now or datetime.utcnow()
    if window == "custom" and frm:
        a = datetime.fromisoformat(frm)
        b = datetime.fromisoformat(to) + timedelta(days=1) if to else now
        return a, min(b, now), "custom"
    if window == "since_last_visit":
        s = get_settings_row(db)
        if s.last_brief_seen_at and s.last_brief_seen_at < now - timedelta(hours=1):
            return s.last_brief_seen_at, now, "since_last_visit"
        window = "24h"
    return now - WINDOWS.get(window, WINDOWS["24h"]), now, window if window in WINDOWS else "24h"


def header(db: Session, frm: datetime, to: datetime) -> dict | None:
    last = latest_date(db)
    if not last:
        return None
    end_d = min(last, to.date())
    sessions = db.scalars(select(PriceDaily.date).where(PriceDaily.key == portfolio.NIFTY, PriceDaily.date <= end_d)
                          .order_by(PriceDaily.date.desc()).limit(40)).all()
    if len(sessions) < 2:
        return None
    if to - frm <= timedelta(hours=36):
        start_d = sessions[1]  # the last session's move
    else:
        start_d = next((d for d in sessions if d <= frm.date()), sessions[-1])
    wc = portfolio.window_change(db, start_d, end_d)
    contrib = wc["contributors"]
    move_rs = wc["rs"]
    parts = []
    top = contrib[0] if contrib else None
    if top and move_rs and abs(move_rs) > 0:
        share = top["rs"] / move_rs * 100
        if 0 < share <= 100 and abs(share) >= 25:
            parts.append(f"{top['name']} caused {share:.0f}% of it.")
        else:
            parts.append(f"Largest mover: {top['name']}, {fmt.rupees(top['rs'], signed=True)}.")
    nifty = wc["nifty_ret"]
    parts.append(f"Nifty {'rose' if nifty >= 0 else 'fell'} {abs(nifty):.2f}%.")
    diff = wc["ret"] - nifty
    parts.append(f"Your book did {abs(diff):.2f} pts {'better' if diff >= 0 else 'worse'} than the market.")
    bars = []
    for cobj in contrib[:3]:
        bars.append({"symbol": cobj["symbol"], "name": cobj["name"], "rs": cobj["rs"], "ret": cobj["ret"]})
    others = sum(c["rs"] for c in contrib[3:])
    if contrib[3:]:
        bars.append({"symbol": None, "name": "Others", "rs": others, "ret": None})
    return {"ret": wc["ret"], "rs": move_rs, "value": wc["value"], "nifty_ret": nifty,
            "from_date": wc["from_date"].isoformat(), "to_date": wc["to_date"].isoformat(),
            "sentence": " ".join(parts), "contributors": bars,
            "freshness": f"EOD close {wc['to_date'].day} {wc['to_date'].strftime('%b')}"}


def event_card(ev: Event, company: Company | None, last_decision: Decision | None = None) -> dict:
    ist = ev.event_date.replace(tzinfo=timezone.utc).astimezone(IST)
    return {
        "id": ev.id, "symbol": company.symbol if company else None, "company": company.name if company else None,
        "kind": ev.kind, "category": ev.category, "category_label": CATEGORY_LABEL.get(ev.category, ev.category),
        "tier": ev.tier, "score": ev.score, "reasons": ev.reasons or [], "title": ev.title,
        "metric_line": ev.metric_line, "impact_line": ev.impact_line, "summary": ev.summary,
        "status": ev.status, "thesis_tag": ev.thesis_tag, "verify_ok": ev.verify_ok,
        "event_date": ev.event_date.isoformat() + "Z", "time_ist": ist.strftime("%H:%M"), "date_ist": ist.strftime("%d %b"),
        "has_quote": any(f.get("quote") for f in (ev.facts or [])),
        "quote": next((f["v"] for f in (ev.facts or []) if f.get("quote")), None),
        "last_decision": decision_dict(last_decision) if last_decision else None,
    }


def decision_dict(d: Decision) -> dict:
    return {"id": d.id, "action": d.action, "note": d.note, "date": d.created_at.date().isoformat(),
            "event_id": d.event_id}


def build_brief(db: Session, window: str = "24h", frm: str | None = None, to: str | None = None) -> dict:
    a, b, wname = resolve_window(db, window, frm, to)
    settings = get_settings_row(db)
    evs = db.scalars(select(Event).where(Event.event_date >= a, Event.event_date <= b)).all()
    companies = {c.id: c for c in db.scalars(select(Company)).all()}
    holding_ids = {c.id for c in companies.values() if c.is_holding}
    evs = [e for e in evs if e.company_id is None or e.company_id in holding_ids]
    last_dec = {}
    for d in db.scalars(select(Decision).order_by(Decision.created_at)).all():
        last_dec[d.company_id] = d

    def card(e):
        c = companies.get(e.company_id)
        ld = last_dec.get(e.company_id)
        return event_card(e, c, ld if ld and (not ld.event_id or ld.event_id != e.id) and ld.created_at < e.event_date + timedelta(days=60) else None)

    attention = sorted([e for e in evs if e.tier in ("P0", "P1") and e.status != "dismissed"],
                       key=lambda e: (-(e.tier == "P0"), -e.score, -e.event_date.timestamp()))
    fyi = sorted([e for e in evs if e.tier == "P2" and e.status != "dismissed"], key=lambda e: -e.event_date.timestamp())
    routine = [e for e in evs if e.tier == "P3"]
    groups = defaultdict(list)
    for e in routine:
        c = companies.get(e.company_id)
        groups[CATEGORY_LABEL.get(e.category, e.category)].append({"id": e.id, "company": c.name if c else "", "title": e.title,
                                                                   "symbol": c.symbol if c else None, "date_ist": card(e)["date_ist"]})
    routine_groups = sorted(({"label": k, "count": len(v), "companies": len({x["company"] for x in v}), "items": v}
                             for k, v in groups.items()), key=lambda g: -g["count"])

    today = datetime.now(IST).date()
    cal = db.scalars(select(CalendarItem).where(CalendarItem.date >= today, CalendarItem.date <= today + timedelta(days=10))
                     .order_by(CalendarItem.date)).all()
    coming = [{"symbol": companies[c.company_id].symbol, "company": companies[c.company_id].name, "date": c.date.isoformat(),
               "label": f"{short_name(companies[c.company_id].name)} {'results' if 'result' in c.purpose.lower() else 'board meeting'}",
               "purpose": c.purpose} for c in cal if c.company_id in companies and companies[c.company_id].is_holding]

    trip = db.scalars(select(Tripwire).where(Tripwire.status.in_(["near", "hit"]), Tripwire.enabled.is_(True))).all()
    trip_rows = [{"id": t.id, "symbol": companies[t.company_id].symbol, "company": companies[t.company_id].name,
                  "label": t.label, "status": t.status, "value": t.last_value, "threshold": t.threshold, "op": t.op}
                 for t in trip if t.company_id in holding_ids]

    last_ingest = db.scalar(select(JobRun.finished_at).where(JobRun.job == "ingest_filings", JobRun.ok.is_(True))
                            .order_by(JobRun.finished_at.desc()).limit(1))
    eod = latest_date(db)
    return {
        "window": {"name": wname, "from": a.isoformat() + "Z", "to": b.isoformat() + "Z"},
        "header": header(db, a, b),
        "attention": [card(e) for e in attention],
        "good_to_know": [card(e) for e in fyi],
        "routine": {"count": len(routine), "groups": routine_groups},
        "coming_up": coming,
        "tripwires": trip_rows,
        "counts": {"attention": len(attention), "good_to_know": len(fyi), "routine": len(routine),
                   "p0": sum(1 for e in attention if e.tier == "P0")},
        "freshness": {
            "filings_checked": (last_ingest.replace(tzinfo=timezone.utc).astimezone(IST).strftime("%H:%M, %d %b")
                                if last_ingest else None),
            "eod_date": eod.isoformat() if eod else None,
            "eod_label": f"EOD {eod.day} {eod.strftime('%b')}" if eod else None,
        },
        "settings": {"price_pct": settings.price_pct, "volume_x": settings.volume_x, "impact_pct": settings.impact_pct},
        "last_seen": settings.last_brief_seen_at.isoformat() + "Z" if settings.last_brief_seen_at else None,
    }


def short_name(name: str) -> str:
    for suffix in (" Limited", " Ltd", " Industries", " Company", " India", " Technologies"):
        name = name.replace(suffix, "")
    return name.strip()
