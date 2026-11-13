"""P0 delivery: an inbox row (works without any permission), plus Web Push and Telegram when set up.
Everything below P0 waits for the brief. Quiet hours are respected unless the user lets P0 through."""
import json
import logging
from datetime import datetime, timedelta, timezone

import httpx
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
    """Inbox row always; then Web Push and Telegram, each independent so one failing never blocks the other."""
    s = db.get(AppSettings, 1)
    n = Notification(event_id=event_id, title=title, body=body, url=url, channel="inbox", delivered=True)
    db.add(n)
    db.flush()
    if s and in_quiet_hours(s) and not s.p0_in_quiet and not force:
        return n
    pushed = _webpush(db, title, body, url)
    telegrammed = _telegram(title, body, url)
    n.channel = "both" if pushed and telegrammed else "webpush" if pushed else "telegram" if telegrammed else "inbox"
    return n


def _webpush(db: Session, title: str, body: str, url: str) -> bool:
    cfg = get_settings()
    if not (cfg.vapid_private_key and cfg.vapid_public_key):
        return False
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        return False
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
    return sent > 0


def app_link(url: str) -> str | None:
    """Absolute link for messages that leave the app; the first non-localhost FRONTEND_ORIGIN."""
    for o in get_settings().frontend_origin.split(","):
        o = o.strip().rstrip("/")
        if o.startswith("http") and "localhost" not in o and "127.0.0.1" not in o:
            return o + url
    return None


def _telegram(title: str, body: str, url: str) -> bool:
    cfg = get_settings()
    chats = [c.strip() for c in cfg.telegram_chat_id.split(",") if c.strip()]
    if not (cfg.telegram_bot_token and chats):
        return False
    link = app_link(url)
    text = "\n".join(x for x in (title, body, link) if x)
    sent = 0
    for chat in chats:
        try:
            r = httpx.post(f"https://api.telegram.org/bot{cfg.telegram_bot_token}/sendMessage",
                           json={"chat_id": chat, "text": text[:4000], "disable_web_page_preview": True}, timeout=15)
            if r.status_code == 200 and r.json().get("ok"):
                sent += 1
            else:
                log.warning("telegram failed for chat %s: %s %s", chat, r.status_code, r.text[:200])
        except Exception as e:  # noqa: BLE001
            log.warning("telegram error: %s", e)
    return sent > 0
