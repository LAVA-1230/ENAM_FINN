"""P0 delivery: Web Push to every subscription plus an inbox row (the inbox works without push permission).
Everything below P0 waits for the brief. Quiet hours are respected unless the user lets P0 through."""
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import AppSettings, Company, Event, Notification, PushSub

log = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))


def in_quiet_hours(s: AppSettings, now: datetime | None = None) -> bool:
    now = (now or datetime.now(IST)).astimezone(IST)
    hm = now.strftime("%H:%M")
    a, b = s.quiet_start, s.quiet_end
    return (a <= hm or hm < b) if a > b else (a <= hm < b)


def notify_event(db: Session, ev: Event, company: Company | None) -> Notification | None:
    if db.scalar(select(Notification.id).where(Notification.event_id == ev.id)):
        return None
    title = f"Urgent: {company.name if company else 'Your portfolio'}"
    body = ev.title + (f". {ev.metric_line}" if ev.metric_line else "")
    return send(db, title, body, f"/event/{ev.id}", ev.id)


def send(db: Session, title: str, body: str, url: str, event_id: int | None = None, force: bool = False) -> Notification:
    s = db.get(AppSettings, 1)
    n = Notification(event_id=event_id, title=title, body=body, url=url, channel="inbox", delivered=True)
    db.add(n)
    db.flush()
    if s and in_quiet_hours(s) and not s.p0_in_quiet and not force:
        return n
    cfg = get_settings()
    if not (cfg.vapid_private_key and cfg.vapid_public_key):
        return n
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        return n
    payload = json.dumps({"title": title, "body": body, "url": url})
    sent = 0
    for sub in db.scalars(select(PushSub)).all():
        try:
            webpush(subscription_info={"endpoint": sub.endpoint, "keys": sub.keys}, data=payload,
                    vapid_private_key=cfg.vapid_private_key, vapid_claims={"sub": cfg.vapid_subject}, ttl=86400)
            sent += 1
        except WebPushException as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            if code in (404, 410):
                db.delete(sub)  # subscription expired
            log.info("webpush failed: %s", e)
        except Exception as e:  # noqa: BLE001
            log.info("webpush error: %s", e)
    if sent:
        n.channel = "webpush"
    return n
