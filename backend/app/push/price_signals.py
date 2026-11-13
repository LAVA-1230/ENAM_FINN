"""EOD price and volume signals (spec 7.5). Volume is an observation, never a prediction."""
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import fmt, portfolio
from ..models import AppSettings, Event, Filing
from .score import Signals, score_event

CLOSE_UTC = time(10, 0)  # 15:30 IST


def _explained(db: Session, company_id: int, d: date, prev_d: date | None = None) -> Filing | None:
    """Any non-routine filing from a day before the previous session's close up to this session's close
    (48h on a normal day; it stretches over weekends and holidays)."""
    end = datetime.combine(d, CLOSE_UTC)
    start = datetime.combine(prev_d, CLOSE_UTC) - timedelta(hours=24) if prev_d else end - timedelta(hours=48)
    rows = db.scalars(select(Filing).where(Filing.company_id == company_id, Filing.published_at >= start,
                                           Filing.published_at <= end).order_by(Filing.published_at.desc())).all()
    for f in rows:
        ev = db.scalar(select(Event).where(Event.filing_id == f.id))
        if ev and ev.tier in ("P0", "P1", "P2"):
            return f
    return None


def evaluate(db: Session, settings: AppSettings, d: date | None = None) -> list[dict]:
    """Event dicts for one session (default: the latest stored)."""
    b = portfolio.book(db, d)
    out, by_sector = [], defaultdict(list)
    for sym, pos in b["positions"].items():
        c, h = pos["company"], pos["holding"]
        mv = portfolio.move_on(db, c, d)
        if not mv or (d and mv.d != d):
            continue
        impact_rs = h.quantity * (mv.close - mv.prev_close)
        impact_pct = pos["weight"] * mv.ret / 100
        idx = portfolio.index_name(mv.index_sym)
        metric = f"{fmt.signed_pct(mv.ret)} vs {idx} {fmt.signed_pct(mv.index_ret)}"
        impact = f"{pos['weight']:.1f}% of your book, {fmt.rupees(impact_rs, signed=True)} on {mv.d.day} {mv.d.strftime('%b')}"
        if mv.specific is not None and abs(mv.ret) >= settings.price_pct / 2:
            by_sector[c.sector].append((c, mv))
        if mv.specific is not None and abs(mv.specific) >= settings.price_pct:
            filing = _explained(db, c.id, mv.d, mv.prev_d)
            p0 = abs(impact_pct) >= settings.impact_pct
            sig = Signals(base_tier="P0" if p0 else "P1",
                          base_reason=f"{fmt.signed_pct(mv.specific)} stock-specific, beyond your {settings.price_pct:g}% limit",
                          weight_pct=pos["weight"])
            if p0:
                sig.extra_reasons.append(f"Moved your book {fmt.signed_pct(impact_pct, 2)}, above your {settings.impact_pct:g}% limit")
            sig.extra_reasons.append(f"Related filing: {filing.subject[:60]}" if filing else "No filing in the last 48h")
            out.append({"company": c, "kind": "price", "category": "price_move", "signals": sig,
                        "title": f"{'Rose' if mv.ret > 0 else 'Fell'} {abs(mv.ret):.1f}%, {abs(mv.specific):.1f} pts "
                                 f"{'better' if mv.specific > 0 else 'worse'} than {idx}",
                        "metric_line": metric, "impact_line": impact, "date": mv.d,
                        "enrichment": {"move": _move_dict(mv), "related_filing_id": filing.id if filing else None,
                                       "related_filing": filing.subject if filing else None},
                        "dedupe_key": f"price:{sym}:{mv.d.isoformat()}"})
        if mv.vol_ratio and mv.vol_ratio >= settings.volume_x:
            filing = _explained(db, c.id, mv.d, mv.prev_d)
            sig = Signals(base_tier="P2" if filing else "P1",
                          base_reason=f"Volume {mv.vol_ratio:.1f}x its 20-day average, above your {settings.volume_x:g}x limit",
                          weight_pct=pos["weight"])
            sig.extra_reasons.append(f"Related filing: {filing.subject[:60]}" if filing else "Unexplained: no filing in the last 48h")
            out.append({"company": c, "kind": "volume", "category": "volume_spike", "signals": sig,
                        "title": f"Volume {mv.vol_ratio:.1f}x the 20-day average" + ("" if filing else ", no filing"),
                        "metric_line": f"{mv.vol_ratio:.1f}x volume, price {fmt.signed_pct(mv.ret)}",
                        "impact_line": impact, "date": mv.d,
                        "enrichment": {"move": _move_dict(mv), "related_filing_id": filing.id if filing else None,
                                       "related_filing": filing.subject if filing else None},
                        "dedupe_key": f"volume:{sym}:{mv.d.isoformat()}"})
    # sector move: 3+ holdings in one sector moving the same way beyond half the threshold -> one grouped card
    for sector, items in by_sector.items():
        for sign in (1, -1):
            same = [(c, mv) for c, mv in items if mv.ret * sign > 0]
            if len(same) >= 3:
                d0 = same[0][1].d
                names = ", ".join(c.name for c, _ in same)
                avg = sum(mv.ret for _, mv in same) / len(same)
                idx = portfolio.index_name(same[0][1].index_sym)
                sig = Signals(base_tier="P1", base_reason=f"{len(same)} {sector} holdings moved together")
                out.append({"company": None, "kind": "sector", "category": "sector_move", "signals": sig,
                            "title": f"{sector}: {len(same)} holdings {'up' if sign > 0 else 'down'}, avg {fmt.signed_pct(avg)}",
                            "metric_line": f"{idx} {fmt.signed_pct(same[0][1].index_ret)}",
                            "impact_line": names, "date": d0,
                            "enrichment": {"members": [{"symbol": c.symbol, "name": c.name, "ret": mv.ret} for c, mv in same]},
                            "dedupe_key": f"sector:{sector}:{d0.isoformat()}:{sign}"})
    return out


def _move_dict(mv: portfolio.Move) -> dict:
    return {"date": mv.d.isoformat(), "ret": mv.ret, "index": portfolio.index_name(mv.index_sym), "index_ret": mv.index_ret,
            "nifty_ret": mv.nifty_ret, "specific": mv.specific, "vol_ratio": mv.vol_ratio, "close": mv.close,
            "prev_close": mv.prev_close}


def store(db: Session, settings: AppSettings, items: list[dict]) -> list[Event]:
    created = []
    for it in items:
        c = it["company"]
        h = c.holding if c else None
        tier, score, reasons = score_event(it["category"], it["signals"], settings.tier_overrides,
                                           h.muted_until if h else None, h.only_p0 if h else False)
        ev = db.scalar(select(Event).where(Event.dedupe_key == it["dedupe_key"]))
        fields = dict(company_id=c.id if c else None, kind=it["kind"], category=it["category"], tier=tier, score=score,
                      reasons=reasons, title=it["title"], metric_line=it["metric_line"], impact_line=it["impact_line"],
                      enrichment=it["enrichment"], context=[], facts=[], verify_ok=True,
                      event_date=datetime.combine(it["date"], CLOSE_UTC))
        if ev:
            for k, v in fields.items():
                setattr(ev, k, v)
        else:
            ev = Event(dedupe_key=it["dedupe_key"], **fields)
            db.add(ev)
            created.append(ev)
    db.flush()
    return created


def clear_stale(db: Session, settings: AppSettings, sessions: list[date]):
    """When thresholds change, events that no longer qualify are removed (they were never 'news')."""
    keep = {it["dedupe_key"] for d in sessions for it in evaluate(db, settings, d)}
    for ev in db.scalars(select(Event).where(Event.kind.in_(["price", "volume", "sector"]))).all():
        if ev.event_date.date() in sessions and ev.dedupe_key not in keep:
            db.delete(ev)
    db.flush()
