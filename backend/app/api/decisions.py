from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Company, Decision, Event
from ..push.digest import decision_dict
from .common import DB, company_or_404

router = APIRouter(tags=["decisions"])
ACTIONS = ("hold", "add", "trim", "exit", "note")


@router.get("/decisions")
def list_decisions(symbol: str | None = None, limit: int = 50, db: Session = DB):
    q = select(Decision)
    if symbol:
        q = q.where(Decision.company_id == company_or_404(db, symbol).id)
    rows = db.scalars(q.order_by(Decision.created_at.desc()).limit(min(limit, 200))).all()
    names = {c.id: c for c in db.scalars(select(Company)).all()}
    return {"decisions": [decision_dict(d) | {"symbol": names[d.company_id].symbol, "company": names[d.company_id].name}
                          for d in rows if d.company_id in names]}


class DecisionIn(BaseModel):
    symbol: str | None = None
    event_id: int | None = None
    action: str
    note: str | None = None


@router.post("/decisions")
def add_decision(body: DecisionIn, db: Session = DB):
    if body.action not in ACTIONS:
        raise HTTPException(422, f"action must be one of {', '.join(ACTIONS)}")
    ev = db.get(Event, body.event_id) if body.event_id else None
    if body.symbol:
        company_id = company_or_404(db, body.symbol).id
    elif ev and ev.company_id:
        company_id = ev.company_id
    else:
        raise HTTPException(422, "Give a symbol or an event about a company")
    d = Decision(company_id=company_id, event_id=ev.id if ev else None, action=body.action,
                 note=(body.note or "").strip()[:500] or None)
    db.add(d)
    db.commit()
    c = db.get(Company, company_id)
    return decision_dict(d) | {"symbol": c.symbol, "company": c.name}  # the app links "Saved" to this company's notes
