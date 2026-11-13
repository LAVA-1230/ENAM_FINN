from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Company, Event, Filing
from ..pull.ask import suggested
from ..push.digest import decision_dict, event_card
from .common import DB, exposure, iso, last_decision

router = APIRouter(tags=["events"])


def event_payload(db: Session, ev: Event) -> dict:
    company = db.get(Company, ev.company_id) if ev.company_id else None
    ld = last_decision(db, company.id, before=ev.event_date, exclude_event=ev.id) if company else None
    out = event_card(ev, company, ld)
    filing = db.get(Filing, ev.filing_id) if ev.filing_id else None
    page = (ev.enrichment or {}).get("page")
    out.update({
        "facts": ev.facts or [], "context": ev.context or [], "enrichment": ev.enrichment or {},
        "dismiss_reason": ev.dismiss_reason, "sector": company.sector if company else None,
        "source": {"exchange": filing.exchange, "category": filing.exchange_category, "subject": filing.subject,
                   "url": filing.attachment_url, "page": page, "published_at": iso(filing.published_at),
                   "filing_id": filing.id} if filing else None,
        "exposure": exposure(db, company) if company and company.is_holding else None,
        "decisions": [decision_dict(d) for d in _decisions(db, ev)],
        "suggested": suggested(ev.category, company.symbol if company else None),
    })
    rel = (ev.enrichment or {}).get("related_filing_id")
    if rel:
        rf = db.get(Filing, rel)
        if rf:
            out["related_filing"] = {"id": rf.id, "subject": rf.subject, "url": rf.attachment_url,
                                     "published_at": iso(rf.published_at)}
    return out


def _decisions(db: Session, ev: Event):
    from ..models import Decision
    return db.scalars(select(Decision).where(Decision.event_id == ev.id).order_by(Decision.created_at.desc())).all()


@router.get("/events/{event_id}")
def get_event(event_id: int, db: Session = DB):
    ev = db.get(Event, event_id)
    if not ev:
        raise HTTPException(404, "Event not found")
    return event_payload(db, ev)


class EventPatch(BaseModel):
    status: str | None = None
    dismiss_reason: str | None = None
    thesis_tag: str | None = None


@router.patch("/events/{event_id}")
def patch_event(event_id: int, body: EventPatch, db: Session = DB):
    ev = db.get(Event, event_id)
    if not ev:
        raise HTTPException(404, "Event not found")
    if body.status is not None:
        if body.status not in ("new", "seen", "dismissed"):
            raise HTTPException(422, "status must be new, seen or dismissed")
        ev.status = body.status
    if body.dismiss_reason is not None:
        ev.dismiss_reason = body.dismiss_reason[:300]
    if body.thesis_tag is not None:
        if body.thesis_tag not in ("strengthens", "neutral", "weakens", ""):
            raise HTTPException(422, "thesis_tag must be strengthens, neutral or weakens")
        ev.thesis_tag = body.thesis_tag or None
    db.commit()
    return event_payload(db, ev)
