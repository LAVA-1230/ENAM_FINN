from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..models import Event
from ..pull import ask as ask_engine
from .common import DB

router = APIRouter(tags=["ask"])


class AskIn(BaseModel):
    question: str
    symbol: str | None = None
    event_id: int | None = None


@router.post("/ask")
def ask(body: AskIn, db: Session = DB):
    if not body.question.strip():
        raise HTTPException(422, "Type a question")
    return ask_engine.answer(db, body.question, body.symbol, body.event_id)


@router.get("/ask/suggested")
def suggested(symbol: str | None = None, event_id: int | None = None, db: Session = DB):
    ev = db.get(Event, event_id) if event_id else None
    return {"suggested": ask_engine.suggested(ev.category if ev else None, symbol)}
