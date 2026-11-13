"""Health, LLM usage and the 'tap to verify' source redirects."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..llm import client as llm
from ..llm import usage
from ..models import Chunk, Company, Document, Event, Filing, JobRun
from ..push.ingest import get_settings_row
from ..sources.prices import latest_date
from . import replay
from .common import DB, iso, ist_label

router = APIRouter(tags=["system"])


@router.get("/health")
def health(db: Session = DB):
    last = {}
    for job in ("ingest_filings", "eod_prices", "snapshot"):
        t = db.scalar(select(JobRun.finished_at).where(JobRun.job == job, JobRun.ok.is_(True))
                      .order_by(JobRun.finished_at.desc()).limit(1))
        last[job] = {"at": iso(t), "label": ist_label(t)}
    s = get_settings_row(db)
    eod = latest_date(db)
    cfg = get_settings()
    return {
        "ok": True, "replay": s.replay or cfg.replay_default, "snapshots": replay.available(),
        "last": last, "eod_date": eod.isoformat() if eod else None,
        "llm": {"provider": cfg.llm_provider if llm.available() else None, "enabled": llm.available(),
                "fast": llm.model_for("fast") if llm.available() else None,
                "smart": llm.model_for("smart") if llm.available() else None},
        "websearch": cfg.websearch_provider != "none" and bool(cfg.websearch_api_key),
        "push": bool(cfg.vapid_public_key and cfg.vapid_private_key),
        "counts": {"companies": db.scalar(select(func.count()).select_from(Company)),
                   "filings": db.scalar(select(func.count()).select_from(Filing)),
                   "events": db.scalar(select(func.count()).select_from(Event))},
    }


@router.get("/admin/usage")
def admin_usage():
    return usage.summary()


@router.get("/sources/{kind}/{item_id}")
def source(kind: str, item_id: int, page: int | None = None, redirect: bool = False, db: Session = DB):
    """filing / document / chunk -> the original PDF (at the page when known) plus the cited excerpt."""
    if kind == "filing":
        f = db.get(Filing, item_id)
        if not f:
            raise HTTPException(404, "Filing not found")
        out = {"title": f.subject, "label": f"{f.exchange} filing, {ist_label(f.published_at)}", "url": f.attachment_url,
               "page": page, "excerpt": (f.text or "")[:600] or None}
    elif kind in ("document", "chunk"):
        ch = db.get(Chunk, item_id) if kind == "chunk" else None
        doc = db.get(Document, ch.document_id if ch else item_id)
        if not doc:
            raise HTTPException(404, "Document not found")
        page = page or (ch.page_from if ch else None)
        kind_label = {"transcript": "Concall transcript", "annual_report": "Annual report"}.get(doc.kind, doc.kind)
        excerpt = ch.text[:900] if ch else (doc.page_texts or {}).get(str(page), "")[:900] if page else None
        out = {"title": f"{kind_label} {doc.period_label or ''}".strip(), "label": f"Page {page}" if page else None,
               "url": doc.url, "page": page, "excerpt": excerpt or None, "speaker": ch.speaker if ch else None}
    else:
        raise HTTPException(404, "kind must be filing, document or chunk")
    if out["url"] and out["page"]:
        out["url"] = f"{out['url']}#page={out['page']}"
    if redirect and out["url"]:
        return RedirectResponse(out["url"])
    return out
