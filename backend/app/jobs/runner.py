"""Job functions. Called by the CLI (laptop / cron) and by POST /api/jobs/{name} (token-protected)."""
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import yaml
from sqlalchemy import select

from .. import portfolio
from ..db import SessionLocal, init_db
from ..models import Company, Holding, JobRun, PriceDaily
from ..push import ingest, price_signals, tripwires
from ..push.ingest import get_settings_row
from ..sources import prices

log = logging.getLogger(__name__)


def run(job: str, fn, **kw) -> dict:
    db = SessionLocal()
    jr = JobRun(job=job, started_at=datetime.utcnow())
    db.add(jr)
    db.commit()
    try:
        stats = fn(db, **kw) or {}
        jr.ok, jr.stats = True, stats
        db.commit()
        return {"ok": True, "job": job, "stats": stats}
    except Exception as e:  # noqa: BLE001
        db.rollback()
        jr = db.get(JobRun, jr.id)
        jr.ok, jr.error = False, f"{e}\n{traceback.format_exc()[-1500:]}"
        log.exception("job %s failed", job)
        db.commit()
        return {"ok": False, "job": job, "error": str(e)}
    finally:
        jr.finished_at = datetime.utcnow()
        db.commit()
        db.close()


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


def eod_prices(db, days: int = 120, signals_sessions: int = 25, **_) -> dict:
    rng = "6mo" if days > 60 else "3mo" if days > 25 else "1mo"
    keys = [c.symbol for c in db.scalars(select(Company)).all()] + sorted(index_keys(db))
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
        created += len(price_signals.store(db, s, price_signals.evaluate(db, s, d)))
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


def snapshot(db, label: str = "demo", **_) -> dict:
    from ..api.replay import write_snapshot
    return write_snapshot(db, label)


JOBS = {"seed": seed, "eod_prices": eod_prices, "financials": load_financials, "ingest_filings": ingest_filings, "build_digest": build_digest,
        "tripwires": run_tripwires, "docs_refresh": docs_refresh, "snapshot": snapshot}
