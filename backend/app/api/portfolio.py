from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import portfolio
from ..models import Event
from ..sources.prices import latest_date
from .common import DB, company_or_404, exposure, holding_of, iso, thesis_health

router = APIRouter(tags=["portfolio"])


@router.get("/portfolio")
def get_portfolio(db: Session = DB):
    book = portfolio.book(db)
    since = datetime.utcnow() - timedelta(days=7)
    rows = []
    for h in portfolio.holdings(db):
        c = h.company
        ev = db.scalars(select(Event).where(Event.company_id == c.id, Event.tier.in_(["P0", "P1"]), Event.event_date >= since,
                                            Event.status != "dismissed")
                        .order_by(Event.score.desc(), Event.event_date.desc()).limit(1)).first()
        ex = exposure(db, c, book)
        rows.append({
            "symbol": c.symbol, "name": c.name, "sector": c.sector,
            "weight": ex.get("weight"), "value": ex.get("value"), "qty": h.quantity, "avg_cost": h.avg_cost,
            "move": ex.get("move"), "day_rs": ex.get("day_rs"), "pnl_rs": ex.get("pnl_rs"), "pnl_pct": ex.get("pnl_pct"),
            "health": thesis_health(db, c.id), "thesis": h.thesis, "thesis_source": h.thesis_source,
            "muted_until": iso(h.muted_until) if h.muted_until and h.muted_until > datetime.utcnow() else None,
            "only_p0": h.only_p0,
            "note": {"text": ev.title, "tier": ev.tier, "event_id": ev.id} if ev else None,
        })
    rows.sort(key=lambda r: -(r["weight"] or 0))
    eod = latest_date(db)
    return {"total": book["total"], "count": len(rows), "holdings": rows,
            "eod_label": f"EOD {eod.day} {eod.strftime('%b')}" if eod else None}


class HoldingPatch(BaseModel):
    thesis: str | None = None
    mute_days: int | None = None
    only_p0: bool | None = None
    quantity: float | None = None


@router.patch("/portfolio/{symbol}")
def patch_holding(symbol: str, body: HoldingPatch, db: Session = DB):
    c = company_or_404(db, symbol)
    h = holding_of(db, c)
    if not h:
        raise HTTPException(404, f"{c.symbol} is not in your portfolio")
    if body.thesis is not None:
        h.thesis, h.thesis_source = body.thesis.strip()[:600] or None, "user"
    if body.mute_days is not None:
        h.muted_until = datetime.utcnow() + timedelta(days=body.mute_days) if body.mute_days > 0 else None
    if body.only_p0 is not None:
        h.only_p0 = body.only_p0
    if body.quantity is not None:
        if body.quantity <= 0:
            raise HTTPException(422, "quantity must be positive")
        h.quantity = body.quantity
    db.commit()
    return {"ok": True, "symbol": c.symbol, "thesis": h.thesis, "muted_until": iso(h.muted_until), "only_p0": h.only_p0,
            "quantity": h.quantity}
