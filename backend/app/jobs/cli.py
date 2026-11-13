"""CLI for local runs and laptop ingestion (when NSE blocks the cloud host, point DATABASE_URL at
production Postgres and run these from a laptop: same code, same DB).

  python -m app.jobs.cli seed
  python -m app.jobs.cli eod --days 120
  python -m app.jobs.cli ingest --days 30 [--symbols TITAN,DABUR]
  python -m app.jobs.cli research PIDILITIND
  python -m app.jobs.cli snapshot --label demo
  python -m app.jobs.cli bootstrap        # seed + prices + 30 days of filings + research demo set
"""
import argparse
import json
import logging
import sys

from ..db import init_db
from . import runner


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    p = argparse.ArgumentParser(prog="finn")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed")
    e = sub.add_parser("eod")
    e.add_argument("--days", type=int, default=120)
    i = sub.add_parser("ingest")
    i.add_argument("--days", type=int, default=2)
    i.add_argument("--symbols", type=str, default=None)
    r = sub.add_parser("research")
    r.add_argument("symbol")
    r.add_argument("--refresh", action="store_true")
    s = sub.add_parser("snapshot")
    s.add_argument("--label", default="demo")
    sub.add_parser("tripwires")
    sub.add_parser("financials")
    b = sub.add_parser("bootstrap")
    b.add_argument("--days", type=int, default=30)
    b.add_argument("--skip-research", action="store_true")
    a = p.parse_args(argv)

    init_db()
    out = None
    if a.cmd == "seed":
        out = runner.run("seed", runner.seed)
    elif a.cmd == "eod":
        out = runner.run("eod_prices", runner.eod_prices, days=a.days)
    elif a.cmd == "ingest":
        syms = [x.strip().upper() for x in a.symbols.split(",")] if a.symbols else None
        out = runner.run("ingest_filings", runner.ingest_filings, days=a.days, symbols=syms)
    elif a.cmd == "research":
        from ..pull.ingest import run_research
        out = run_research(a.symbol.upper(), refresh=a.refresh)
    elif a.cmd == "snapshot":
        out = runner.run("snapshot", runner.snapshot, label=a.label)
    elif a.cmd == "financials":
        out = runner.run("financials", runner.load_financials)
    elif a.cmd == "tripwires":
        out = runner.run("tripwires", runner.run_tripwires)
    elif a.cmd == "bootstrap":
        import time
        out = []
        for name, fn, kw in (("seed", runner.seed, {}), ("eod_prices", runner.eod_prices, {"days": 120}),
                             ("financials", runner.load_financials, {}),
                             ("ingest_filings", runner.ingest_filings, {"days": a.days}),
                             # re-run price signals now that filings can explain moves
                             ("eod_prices", runner.eod_prices, {"days": 10})):
            t0 = time.time()
            r = runner.run(name, fn, **kw)
            r["seconds"] = round(time.time() - t0, 1)
            print(f"{name}: {'ok' if r['ok'] else 'FAILED'} in {r['seconds']}s", flush=True)
            out.append(r)
        if not a.skip_research:
            from ..pull.ingest import run_research
            from ..db import SessionLocal
            from ..models import Company
            from sqlalchemy import select
            with SessionLocal() as db:
                syms = [c.symbol for c in db.scalars(select(Company).where(Company.is_research.is_(True))).all()]
            for sym in syms:
                out.append(run_research(sym))
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
