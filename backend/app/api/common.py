"""Helpers shared by the routers."""
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import portfolio
from ..db import get_db
from ..models import Company, CompanyResearch, Decision, Document, Event, Holding

IST = timezone(timedelta(hours=5, minutes=30))
DB = Depends(get_db)


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() + "Z" if dt else None


def ist_label(dt: datetime | None) -> str | None:
    if not dt:
        return None
    return dt.replace(tzinfo=timezone.utc).astimezone(IST).strftime("%H:%M, %d %b")


def company_or_404(db: Session, symbol: str) -> Company:
    c = db.scalar(select(Company).where(Company.symbol == symbol.upper()))
    if not c:
        raise HTTPException(404, f"{symbol.upper()} is not in FINN yet. Open Research to read its filings.")
    return c


def research_row(db: Session, company: Company) -> CompanyResearch | None:
    return db.scalar(select(CompanyResearch).where(CompanyResearch.company_id == company.id))


def doc_link(doc: Document | None, page: int | None) -> str | None:
    if not doc:
        return None
    return doc.url + (f"#page={page}" if page else "")


def last_decision(db: Session, company_id: int, before: datetime | None = None, exclude_event: int | None = None) -> Decision | None:
    q = select(Decision).where(Decision.company_id == company_id)
    if before:
        q = q.where(Decision.created_at < before)
    if exclude_event:
        q = q.where((Decision.event_id.is_(None)) | (Decision.event_id != exclude_event))
    return db.scalars(q.order_by(Decision.created_at.desc()).limit(1)).first()


def thesis_health(db: Session, company_id: int) -> str:
    """green: no weakens / hits in 90 days; amber: one; red: a tripwire hit or two or more weakens (spec 9.2)."""
    from ..models import Tripwire
    since = datetime.utcnow() - timedelta(days=90)
    weakens = db.scalars(select(Event.id).where(Event.company_id == company_id, Event.thesis_tag == "weakens",
                                                Event.event_date >= since)).all()
    hits = db.scalars(select(Tripwire.id).where(Tripwire.company_id == company_id, Tripwire.status == "hit",
                                                Tripwire.enabled.is_(True))).all()
    near = db.scalars(select(Tripwire.id).where(Tripwire.company_id == company_id, Tripwire.status == "near",
                                                Tripwire.enabled.is_(True))).all()
    if hits or len(weakens) >= 2:
        return "red"
    if weakens or near:
        return "amber"
    return "green"


def exposure(db: Session, company: Company, book: dict | None = None) -> dict | None:
    """Weight, latest move split and the position's rupee P&L, for a held company."""
    book = book or portfolio.book(db)
    pos = book["positions"].get(company.symbol)
    mv = portfolio.move_on(db, company)
    out = {"held": bool(pos), "weight": pos["weight"] if pos else None, "value": pos["value"] if pos else None,
           "qty": pos["qty"] if pos else None, "avg_cost": pos["avg_cost"] if pos else None}
    if mv:
        out["move"] = {"date": mv.d.isoformat(), "ret": mv.ret, "close": mv.close, "index": portfolio.index_name(mv.index_sym),
                       "index_ret": mv.index_ret, "nifty_ret": mv.nifty_ret, "specific": mv.specific,
                       "vol_ratio": mv.vol_ratio}
        if pos:
            out["day_rs"] = pos["qty"] * (mv.close - mv.prev_close)
    if pos and pos["avg_cost"]:
        out["pnl_rs"] = pos["qty"] * (pos["close"] - pos["avg_cost"])
        out["pnl_pct"] = (pos["close"] / pos["avg_cost"] - 1) * 100
    return out


def holding_of(db: Session, company: Company) -> Holding | None:
    return db.scalar(select(Holding).where(Holding.company_id == company.id))
