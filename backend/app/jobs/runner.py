"""Job functions. Called by the CLI (laptop / cron) and by POST /api/jobs/{name} (token-protected)."""
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import yaml
from sqlalchemy import func, select

from .. import fmt, portfolio
from ..config import get_settings
from ..db import SessionLocal, init_db
from ..models import Company, Event, Holding, JobRun, PriceDaily, Tripwire
from ..push import ingest, notify, price_signals, tripwires
from ..push.ingest import get_settings_row
from ..sources import prices

log = logging.getLogger(__name__)


STALE_AFTER = timedelta(hours=2)


def run(job: str, fn, **kw) -> dict:
    db = SessionLocal()
    _close_stale(db, job)
    jr = JobRun(job=job, started_at=datetime.utcnow())
    db.add(jr)
    db.commit()
    jr_id = jr.id
    try:
        stats = fn(db, **kw) or {}
        jr.ok, jr.stats, jr.finished_at = True, stats, datetime.utcnow()
        db.commit()
        return {"ok": True, "job": job, "stats": stats}
    except Exception as e:  # noqa: BLE001
        log.exception("job %s failed", job)
        _mark_failed(jr_id, f"{e}\n{traceback.format_exc()[-1500:]}")
        return {"ok": False, "job": job, "error": str(e)}
    finally:
        db.close()


def _mark_failed(jr_id: int, error: str):
    """Fresh session: the job's own connection may be the thing that broke."""
    with SessionLocal() as s:
        jr = s.get(JobRun, jr_id)
        jr.ok, jr.error, jr.finished_at = False, error, datetime.utcnow()
        s.commit()


def _close_stale(db, job: str):
    """A run with no finish time after 2h was killed (server stopped or hung); say so instead of 'running'."""
    cutoff = datetime.utcnow() - STALE_AFTER
    for jr in db.scalars(select(JobRun).where(JobRun.job == job, JobRun.finished_at.is_(None),
                                              JobRun.started_at < cutoff)).all():
        jr.ok, jr.error, jr.finished_at = False, "Did not finish (server stopped or job hung)", datetime.utcnow()
    db.commit()


def seed(db, **_) -> dict:
    init_db()
    data = yaml.safe_load((portfolio.SEED / "portfolio.yaml").read_text(encoding="utf-8"))
    sectors = portfolio.sector_config()["sectors"]
    n = 0
    for h in data["holdings"]:
        c = db.scalar(select(Company).where(Company.symbol == h["symbol"]))
        if not c:
            c = Company(symbol=h["symbol"], name=h["name"])
            db.add(c)
            n += 1
        c.name, c.sector, c.is_holding = h["name"], h["sector"], True
        c.sector_index = h.get("sector_index") or sectors.get(h["sector"], portfolio.NIFTY)
        db.flush()
        hold = db.scalar(select(Holding).where(Holding.company_id == c.id))
        if not hold:
            db.add(Holding(company_id=c.id, quantity=h["quantity"], avg_cost=h.get("avg_cost")))
    for r in data.get("research", []):
        c = db.scalar(select(Company).where(Company.symbol == r["symbol"]))
        if not c:
            c = Company(symbol=r["symbol"], name=r["name"], is_research=True, sector_index=portfolio.NIFTY)
            db.add(c)
            n += 1
        c.is_research = True
    get_settings_row(db)
    db.flush()
    return {"companies_added": n}


def index_keys(db) -> set[str]:
    keys = {portfolio.NIFTY}
    keys.update(c.sector_index for c in db.scalars(select(Company)).all() if c.sector_index)
    return keys


def eod_prices(db, days: int = 120, signals_sessions: int | None = None, **_) -> dict:
    rng = "6mo" if days > 60 else "3mo" if days > 25 else "1mo"
    keys = [c.symbol for c in db.scalars(select(Company)).all()] + sorted(index_keys(db))
    if signals_sessions is None:  # a fresh DB needs the full lookback; a daily run only the last week (late fixes, holidays)
        signals_sessions = 5 if prices.latest_date(db, portfolio.NIFTY) else 25
    stored, failed = 0, []

    def fetch(k):
        try:
            return k, prices.fetch_history(k, rng)
        except Exception as e:  # noqa: BLE001
            log.warning("prices %s failed: %s", k, e)
            return k, None

    with ThreadPoolExecutor(max_workers=6) as ex:
        for k, rows in ex.map(fetch, keys):
            if rows is None:
                failed.append(k)
            else:
                stored += prices.store(db, k, rows)
    db.commit()
    s = get_settings_row(db)
    sessions = db.scalars(select(PriceDaily.date).where(PriceDaily.key == portfolio.NIFTY)
                          .order_by(PriceDaily.date.desc()).limit(signals_sessions)).all()
    created = 0
    for d in sorted(sessions):
        evs = price_signals.store(db, s, price_signals.evaluate(db, s, d))
        created += len(evs)
        if sessions and d == sessions[0]:  # only the latest session notifies; older ones are backfill
            for ev in evs:
                if ev.tier == "P0":
                    notify.notify_event(db, ev, db.get(Company, ev.company_id) if ev.company_id else None)
    db.commit()
    tw = tripwires.evaluate_all(db)
    return {"rows_added": stored, "failed": failed, "price_events": created, "tripwires": tw}


def ingest_filings(db, days: int = 2, symbols: list[str] | None = None, **_) -> dict:
    stats = ingest.ingest_filings(db, days=days, symbols=symbols)
    stats["calendar_added"] = ingest.refresh_calendar(db)
    db.commit()
    stats["tripwires"] = tripwires.evaluate_all(db)
    db.commit()
    return stats


def load_financials(db, **_) -> dict:
    """screener.in tables for every company (needed for results cross-checks and size-vs-company)."""
    from ..pull import financials
    return financials.load_all(db)


def build_digest(db, **_) -> dict:
    from ..push.digest import build_brief
    b = build_brief(db, "24h")
    return {"attention": b["counts"]["attention"], "routine": b["counts"]["routine"]}


def run_tripwires(db, **_) -> dict:
    return tripwires.evaluate_all(db)


def docs_refresh(db, **_) -> dict:
    """New transcripts -> promise ledger update for every company whose research is ready."""
    from ..pull import ingest as pull_ingest
    from ..models import CompanyResearch
    done = []
    for r in db.scalars(select(CompanyResearch).where(CompanyResearch.status == "ready")).all():
        c = db.get(Company, r.company_id)
        pull_ingest.run_research(c.symbol, refresh=True)
        done.append(c.symbol)
    return {"refreshed": done}


def checkin(db, force: bool = False, **_) -> dict:
    """Optional portfolio summary to the inbox, phone push and Telegram every CHECKIN_HOURS (0 = off), so the
    user can see the alert channels work on quiet days. Runs after each scheduled ingest/eod; `force` sends now."""
    hours = get_settings().checkin_hours
    if not force:
        if hours <= 0:
            return {"sent": False, "reason": "off (CHECKIN_HOURS=0)"}
        if notify.in_quiet_hours(get_settings_row(db)):
            return {"sent": False, "reason": "quiet hours"}
        runs = db.scalars(select(JobRun).where(JobRun.job == "checkin", JobRun.ok.is_(True))
                          .order_by(JobRun.started_at.desc()).limit(50)).all()
        last = next((r.started_at for r in runs if (r.stats or {}).get("sent")), None)
        if last and datetime.utcnow() - last < timedelta(hours=hours) - timedelta(minutes=10):
            return {"sent": False, "reason": f"last sent {last.isoformat()}Z"}
    title, body = "FINN check-in", checkin_text(db)
    n = notify.send(db, title, body, "/portfolio", force=True)  # quiet hours were checked above
    return {"sent": True, "channel": n.channel, "body": body}


def checkin_text(db) -> str:
    b = portfolio.book(db)
    day, moves = 0.0, []
    for pos in b["positions"].values():
        mv = portfolio.move_on(db, pos["company"])
        if mv:
            day += pos["qty"] * (mv.close - mv.prev_close)
            moves.append((mv.ret, pos["company"].name, mv.d))
    if not moves:
        return "No prices stored yet. Alerts still work; the next price run fills this in."
    eod = max(m[2] for m in moves)
    prev_total = b["total"] - day
    day_pct = day / prev_total * 100 if prev_total else None
    top = sorted(moves, key=lambda m: abs(m[0]), reverse=True)[:3]
    hits = db.scalar(select(func.count()).select_from(Tripwire).where(Tripwire.enabled.is_(True), Tripwire.status == "hit"))
    since = datetime.utcnow() - timedelta(hours=24)
    urgent = db.scalar(select(func.count()).select_from(Event).where(Event.created_at >= since, Event.tier == "P0"))
    last_ingest = db.scalars(select(JobRun).where(JobRun.job == "ingest_filings", JobRun.ok.is_(True))
                             .order_by(JobRun.started_at.desc()).limit(1)).first()
    checked = (last_ingest.finished_at or last_ingest.started_at) if last_ingest else None
    lines = [f"Portfolio {fmt.rupees(b['total'])}, {fmt.signed_pct(day_pct)} ({fmt.rupees(day, signed=True)}) "
             f"at the {eod.day} {eod.strftime('%b')} close.",
             "Biggest moves: " + ", ".join(f"{name} {fmt.signed_pct(ret)}" for ret, name, _ in top) + ".",
             f"Tripwires hit: {hits}. Urgent items in the last 24h: {urgent}."]
    if checked:
        ist = checked + timedelta(hours=5, minutes=30)
        lines.append(f"Filings last checked {ist.strftime('%H:%M')} IST. Prices are end-of-day, never real-time.")
    return "\n".join(lines)


def snapshot(db, label: str = "demo", **_) -> dict:
    from ..api.replay import write_snapshot
    return write_snapshot(db, label)


JOBS = {"seed": seed, "eod_prices": eod_prices, "financials": load_financials, "ingest_filings": ingest_filings, "build_digest": build_digest,
        "tripwires": run_tripwires, "docs_refresh": docs_refresh, "snapshot": snapshot, "checkin": checkin}
