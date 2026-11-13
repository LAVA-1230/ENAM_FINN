import re
import threading

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Company, CompanyResearch
from ..pull import ingest
from .common import DB, research_row

router = APIRouter(tags=["research"])
SYMBOL_RE = re.compile(r"^[A-Z0-9&\-]{1,20}$")
_errors: dict[str, str] = {}
_running: set[str] = set()
_lock = threading.Lock()


def _bg(symbol: str):
    try:
        out = ingest.run_research(symbol)
        if not out.get("ok"):
            _errors[symbol] = out.get("error") or "Research failed"
    finally:
        with _lock:
            _running.discard(symbol)


@router.post("/research/{symbol}")
def start(symbol: str):
    symbol = symbol.upper().strip()
    if not SYMBOL_RE.match(symbol):
        raise HTTPException(422, "Use the NSE symbol, e.g. PIDILITIND")
    with _lock:
        if symbol not in _running:
            _running.add(symbol)
            _errors.pop(symbol, None)
            threading.Thread(target=_bg, args=(symbol,), daemon=True).start()
    return {"status": "running", "symbol": symbol}


@router.get("/research/ready")
def ready(db: Session = DB):
    rows = db.execute(select(Company, CompanyResearch).join(CompanyResearch, CompanyResearch.company_id == Company.id)
                      .where(CompanyResearch.status == "ready").order_by(CompanyResearch.updated_at.desc())).all()
    known = db.scalars(select(Company).order_by(Company.symbol)).all()
    return {"ready": [{"symbol": c.symbol, "name": c.name, "sector": c.sector, "is_holding": c.is_holding,
                       "scorecard": (r.cards or {}).get("scorecard", {}).get("sentence"),
                       "updated_at": r.updated_at.isoformat() + "Z"} for c, r in rows],
            "known": [{"symbol": c.symbol, "name": c.name} for c in known]}


@router.get("/research/{symbol}/status")
def status(symbol: str, db: Session = DB):
    symbol = symbol.upper().strip()
    c = db.scalar(select(Company).where(Company.symbol == symbol))
    r = research_row(db, c) if c else None
    running = symbol in _running
    if r:
        st = r.status if not (running and r.status in ("ready", "failed")) else "running"
        return {"symbol": symbol, "name": c.name, "status": st, "progress": r.progress or [],
                "error": r.error or _errors.get(symbol)}
    if symbol in _errors:
        return {"symbol": symbol, "status": "failed", "progress": [], "error": _errors[symbol]}
    return {"symbol": symbol, "status": "running" if running else "none",
            "progress": [{"key": k, "label": label, "state": "running" if i == 0 and running else "todo"}
                         for i, (k, label) in enumerate(ingest.STEPS)], "error": None}
