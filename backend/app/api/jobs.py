"""Token-protected job endpoints, called by the GitHub Actions cron (spec 13.2). Jobs run in a background
thread so the cron request returns at once; the result lands in job_run."""
import hmac
import threading

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..jobs import runner
from ..models import JobRun
from .common import DB, iso

router = APIRouter(tags=["jobs"])
ALLOWED = ("ingest_filings", "eod_prices", "build_digest", "docs_refresh", "tripwires", "snapshot", "financials", "seed")


def _check(authorization: str | None):
    token = get_settings().job_token
    given = (authorization or "").removeprefix("Bearer ").strip()
    if not token or token == "change-me" or not hmac.compare_digest(given, token):
        raise HTTPException(401, "Job token missing or wrong")


@router.post("/jobs/{name}", status_code=202)
def run_job(name: str, days: int | None = None, label: str | None = None, authorization: str | None = Header(None)):
    _check(authorization)
    if name not in ALLOWED:
        raise HTTPException(404, f"Unknown job. Use one of: {', '.join(ALLOWED)}")
    kw = {k: v for k, v in {"days": days, "label": label}.items() if v is not None}
    threading.Thread(target=runner.run, args=(name, runner.JOBS[name]), kwargs=kw, daemon=True).start()
    return {"accepted": True, "job": name}


@router.get("/jobs")
def recent(limit: int = 20, db: Session = DB):
    rows = db.scalars(select(JobRun).order_by(JobRun.started_at.desc()).limit(min(limit, 100))).all()
    return {"runs": [{"id": r.id, "job": r.job, "started_at": iso(r.started_at), "finished_at": iso(r.finished_at),
                      "ok": r.ok, "stats": r.stats, "error": (r.error or "")[:300] or None} for r in rows]}
