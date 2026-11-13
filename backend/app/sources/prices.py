"""EOD prices and volumes from Yahoo Finance's chart endpoint (the same data yfinance wraps).

Holdings use <SYMBOL>.NS; indices use their Yahoo symbols (seed/sector_index.yaml).
Called directly over HTTP so the server needs no pandas."""
import logging
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import http
from ..models import PriceDaily

log = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))
CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{}"
TIMEOUT = 15  # seconds; Yahoo answers in <1s when it is not throttling us, so fail fast


def yahoo_symbol(key: str) -> str:
    return key if key.startswith("^") or key.endswith(".NS") or key.endswith(".BO") else f"{key}.NS"


def fetch_history(key: str, range_: str = "6mo") -> list[tuple[date, float, float | None]]:
    """[(date, close, volume)] for completed sessions, oldest first."""
    data = http.get(CHART.format(quote(yahoo_symbol(key), safe="^.")),
                    params={"range": range_, "interval": "1d"}, min_gap=0.3, timeout=TIMEOUT).json()
    res = (data.get("chart") or {}).get("result") or []
    if not res:
        return []
    res = res[0]
    ts = res.get("timestamp") or []
    q = res["indicators"]["quote"][0]
    out = []
    for t, c, v in zip(ts, q.get("close") or [], q.get("volume") or []):
        if c is None:
            continue
        out.append((datetime.fromtimestamp(t, IST).date(), float(c), float(v) if v is not None else None))
    # Drop today's row while the session is still open (we never claim real-time).
    now = datetime.now(IST)
    if out and out[-1][0] == now.date() and (now.hour, now.minute) < (15, 45):
        out.pop()
    return out


def fetch_meta(key: str) -> dict:
    data = http.get(CHART.format(quote(yahoo_symbol(key), safe="^.")),
                    params={"range": "5d", "interval": "1d"}, min_gap=0.3, timeout=TIMEOUT).json()
    res = (data.get("chart") or {}).get("result") or []
    return res[0]["meta"] if res else {}


def store(db: Session, key: str, rows: list[tuple[date, float, float | None]]) -> int:
    if not rows:
        return 0
    db.info.pop("closes", None)  # portfolio._closes cache is stale once prices change
    # one query per key: the DB can be a long round trip away (Neon from a US runner), so no per-row selects
    existing = {r.date: r for r in db.scalars(select(PriceDaily).where(PriceDaily.key == key))}
    n = 0
    for d, c, v in rows:
        if d in existing:
            row = existing[d]
            row.close, row.volume = c, v
        else:
            db.add(PriceDaily(key=key, date=d, close=c, volume=v))
            n += 1
    db.flush()
    return n


def series(db: Session, key: str, limit: int = 60) -> list[PriceDaily]:
    rows = db.scalars(select(PriceDaily).where(PriceDaily.key == key)
                      .order_by(PriceDaily.date.desc()).limit(limit)).all()
    return list(reversed(rows))


def close_on_or_before(db: Session, key: str, d: date) -> PriceDaily | None:
    return db.scalar(select(PriceDaily).where(PriceDaily.key == key, PriceDaily.date <= d)
                     .order_by(PriceDaily.date.desc()).limit(1))


def latest_close_exists(db: Session, key: str) -> bool:
    return db.scalar(select(PriceDaily.id).where(PriceDaily.key == key).limit(1)) is not None


def latest_date(db: Session, key: str = "^NSEI") -> date | None:
    return db.scalar(select(PriceDaily.date).where(PriceDaily.key == key).order_by(PriceDaily.date.desc()).limit(1))


def validate_symbol(symbol: str) -> dict | None:
    """Returns Yahoo meta if <SYMBOL>.NS has recent history, else None."""
    try:
        rows = fetch_history(symbol, "1mo")
        if not rows:
            return None
        meta = fetch_meta(symbol)
        return {"name": meta.get("longName") or meta.get("shortName") or symbol, "rows": rows}
    except Exception as e:  # noqa: BLE001
        log.info("validate %s failed: %s", symbol, e)
        return None
