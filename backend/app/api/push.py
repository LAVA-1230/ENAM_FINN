from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Notification, PushSub
from ..push import notify
from .common import DB, iso

router = APIRouter(tags=["push"])


@router.get("/push/key")
def key():
    k = get_settings().vapid_public_key
    return {"public_key": k or None, "enabled": bool(k)}


class SubIn(BaseModel):
    endpoint: str
    keys: dict


@router.post("/push/subscribe")
def subscribe(body: SubIn, db: Session = DB):
    sub = db.scalar(select(PushSub).where(PushSub.endpoint == body.endpoint))
    if sub:
        sub.keys = body.keys
    else:
        db.add(PushSub(endpoint=body.endpoint, keys=body.keys))
    db.commit()
    return {"ok": True}


@router.post("/push/test")
def test(db: Session = DB):
    n = notify.send(db, "Test alert from FINN", "This is how an urgent item will reach you.", "/inbox", force=True)
    db.commit()
    return {"ok": True, "channel": n.channel,
            "note": None if n.channel != "inbox" else
            "Saved to your inbox only. Phone push needs VAPID keys and Enable push; Telegram needs TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID."}


@router.get("/notifications")
def notifications(limit: int = 50, db: Session = DB):
    rows = db.scalars(select(Notification).order_by(Notification.sent_at.desc()).limit(min(limit, 200))).all()
    return {"unread": sum(1 for n in rows if not n.read),
            "items": [{"id": n.id, "title": n.title, "body": n.body, "url": n.url, "channel": n.channel,
                       "sent_at": iso(n.sent_at), "read": n.read, "event_id": n.event_id} for n in rows]}


@router.post("/notifications/read")
def mark_read(db: Session = DB):
    db.execute(update(Notification).where(Notification.read.is_(False)).values(read=True))
    db.commit()
    return {"ok": True}
