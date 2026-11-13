"""Positions, weights and moves, computed from stored EOD prices. Pure Python, no LLM."""
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .models import Company, Holding, PriceDaily

SEED = Path(__file__).resolve().parent.parent / "seed"
NIFTY = "^NSEI"


@lru_cache
def sector_config() -> dict:
    return yaml.safe_load((SEED / "sector_index.yaml").read_text(encoding="utf-8"))


def index_name(sym: str | None) -> str:
    return sector_config()["index_names"].get(sym or NIFTY, "Nifty 50")


@dataclass
class Move:
    d: date
    prev_d: date
    close: float
    prev_close: float
    ret: float                # %
    volume: float | None
    vol_ratio: float | None   # volume / mean(previous 20 sessions)
    index_sym: str
    index_ret: float | None   # % sector index (fallback Nifty)
    nifty_ret: float | None
    specific: float | None    # ret - index_ret


def _closes(db: Session, key: str, upto: date | None, n: int) -> list[PriceDaily]:
    """Last n closes on/before upto. Each key's history is loaded once per session (one query, not one per call):
    the DB can be a long round trip away. prices.store clears this cache."""
    cache = db.info.setdefault("closes", {})
    if key not in cache:
        cache[key] = db.scalars(select(PriceDaily).where(PriceDaily.key == key).order_by(PriceDaily.date)).all()
    rows = cache[key]
    if upto:
        rows = [r for r in rows if r.date <= upto]
    return list(rows[-n:]) if n > 0 else []


def index_return(db: Session, key: str, d: date) -> float | None:
    rows = _closes(db, key, d, 2)
    if len(rows) < 2 or rows[-1].date != d:
        return None
    return (rows[-1].close / rows[-2].close - 1) * 100


def move_on(db: Session, company: Company, d: date | None = None) -> Move | None:
    """The move on session d (default: latest stored session)."""
    rows = _closes(db, company.symbol, d, 22)
    if len(rows) < 2:
        return None
    cur, prev = rows[-1], rows[-2]
    ret = (cur.close / prev.close - 1) * 100
    hist = [r.volume for r in rows[:-1][-20:] if r.volume]
    vol_ratio = cur.volume / (sum(hist) / len(hist)) if cur.volume and hist else None
    idx = company.sector_index or NIFTY
    iret = index_return(db, idx, cur.date)
    if iret is None and idx != NIFTY:
        idx, iret = NIFTY, index_return(db, NIFTY, cur.date)
    nret = index_return(db, NIFTY, cur.date)
    return Move(d=cur.date, prev_d=prev.date, close=cur.close, prev_close=prev.close, ret=ret,
                volume=cur.volume, vol_ratio=vol_ratio, index_sym=idx, index_ret=iret, nifty_ret=nret,
                specific=ret - iret if iret is not None else None)


def holdings(db: Session) -> list[Holding]:
    return db.scalars(select(Holding).options(joinedload(Holding.company))).all()


def latest_close(db: Session, key: str, upto: date | None = None) -> PriceDaily | None:
    rows = _closes(db, key, upto, 1)
    return rows[-1] if rows else None


def book(db: Session, upto: date | None = None) -> dict:
    """{symbol: {value, weight, qty, close, avg_cost}} and the total, at the close on/before `upto`."""
    out, total = {}, 0.0
    for h in holdings(db):
        p = latest_close(db, h.company.symbol, upto)
        if not p:
            continue
        v = h.quantity * p.close
        out[h.company.symbol] = {"value": v, "qty": h.quantity, "close": p.close, "avg_cost": h.avg_cost,
                                 "company": h.company, "holding": h}
        total += v
    for v in out.values():
        v["weight"] = v["value"] / total * 100 if total else 0
    return {"positions": out, "total": total}


def weight_of(db: Session, symbol: str) -> float | None:
    b = book(db)
    p = b["positions"].get(symbol)
    return p["weight"] if p else None


def window_change(db: Session, start: date, end: date) -> dict:
    """Portfolio change between the closes on/before `start` and `end`, with attribution."""
    contrib, total_start, total_end = [], 0.0, 0.0
    for h in holdings(db):
        a = latest_close(db, h.company.symbol, start)
        b = latest_close(db, h.company.symbol, end)
        if not a or not b:
            continue
        total_start += h.quantity * a.close
        total_end += h.quantity * b.close
        contrib.append({"symbol": h.company.symbol, "name": h.company.name,
                        "rs": h.quantity * (b.close - a.close), "ret": (b.close / a.close - 1) * 100})
    n_a, n_b = latest_close(db, NIFTY, start), latest_close(db, NIFTY, end)
    rs = total_end - total_start
    return {
        "from_date": n_a.date if n_a else start, "to_date": n_b.date if n_b else end,
        "value": total_end, "rs": rs, "ret": rs / total_start * 100 if total_start else 0,
        "nifty_ret": (n_b.close / n_a.close - 1) * 100 if n_a and n_b and n_a.date != n_b.date else 0.0,
        "contributors": sorted(contrib, key=lambda c: abs(c["rs"]), reverse=True),
    }
