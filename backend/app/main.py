"""FastAPI app: routers under /api, CORS for the frontend, replay middleware, DB init (and seed on an empty DB)."""
import json
import logging
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func, select

from .api import ask, brief, companies, decisions, events, jobs, portfolio, push, replay, research, settings, system
from .config import get_settings
from .db import SessionLocal, init_db

log = logging.getLogger("finn")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    from .models import Company
    with SessionLocal() as db:
        empty = not db.scalar(select(func.count()).select_from(Company))
    if empty:  # fresh Postgres: the portfolio exists before the first cron run
        from .jobs import runner
        runner.run("seed", runner.seed)
    yield


app = FastAPI(title="FINN API", version="1.0", lifespan=lifespan)
cfg = get_settings()
origins = [o.strip() for o in cfg.frontend_origin.split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_origin_regex=r"https://.*\.vercel\.app",
                   allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Finn-Replay"])


@app.middleware("http")
async def replay_mode(request: Request, call_next):
    """Serve GETs from the snapshot when replay is on. Writes, jobs and Ask always run live."""
    path = request.url.path
    if (request.method != "GET" or not path.startswith("/api/") or request.headers.get("X-Finn-Live")
            or re.match(r"^/api/(health|settings|jobs|admin|sources|research/[^/]+/status)", path)):
        return await call_next(request)
    label = request.query_params.get("replay")
    if label in ("0", "false", "live"):
        return await call_next(request)
    if not label:
        from .push.ingest import get_settings_row
        with SessionLocal() as db:
            on = get_settings_row(db).replay or cfg.replay_default
        if not on:
            return await call_next(request)
        label = "demo"
    snap = replay.load(label)
    if not snap:
        return await call_next(request)
    body = snap["responses"].get(replay.key_of(path, dict(request.query_params)))
    if body is None:
        resp = await call_next(request)  # not in the snapshot (e.g. a new company): live
    else:
        resp = Response(json.dumps(body, ensure_ascii=False), media_type="application/json")
    resp.headers["X-Finn-Replay"] = replay.banner(snap["meta"])
    return resp


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    log.exception("unhandled error: %s", exc)
    return JSONResponse({"detail": "FINN hit an error on this request. Stored data is unchanged."}, status_code=500)


for r in (system.router, brief.router, events.router, portfolio.router, companies.router, research.router, ask.router,
          settings.router, decisions.router, push.router, jobs.router):
    app.include_router(r, prefix="/api")


@app.get("/")
def root():
    return {"app": "FINN", "docs": "/docs", "health": "/api/health"}
