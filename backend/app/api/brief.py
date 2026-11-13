from datetime import datetime

from fastapi import APIRouter, Query
from sqlalchemy.orm import Session

from ..push import audio
from ..push.digest import build_brief
from ..push.ingest import get_settings_row
from .common import DB

router = APIRouter(tags=["brief"])


@router.get("/brief")
def brief(window: str = "24h", frm: str | None = Query(None, alias="from"), to: str | None = None, db: Session = DB):
    return build_brief(db, window, frm, to)


@router.post("/brief/seen")
def seen(db: Session = DB):
    s = get_settings_row(db)
    s.last_brief_seen_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "last_seen": s.last_brief_seen_at.isoformat() + "Z"}


@router.get("/brief/audio-script")
def audio_script(window: str = "24h", db: Session = DB):
    return audio.script(build_brief(db, window))
