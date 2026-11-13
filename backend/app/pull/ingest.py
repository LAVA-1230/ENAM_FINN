"""Any-ticker research cold start (spec 8.1). Runs in a background thread; progress is stored in
company_research.progress and polled by the UI.

Everything the Ask chatbot needs ends up in the database: document page texts and chunks (Postgres in
production), so a redeploy loses nothing. PDFs on disk are only a download cache."""
import logging
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from sqlalchemy import delete, select

from .. import portfolio
from ..db import SessionLocal
from ..llm import client as llm
from ..llm.schemas import ThesisOut
from ..models import Chunk, Company, CompanyResearch, Document, Promise, PromiseVerdict
from ..push import tripwires
from ..sources import pdf, prices, screener
from . import cards, chunks, financials, promises, verdict

log = logging.getLogger(__name__)
STEPS = [
    ("resolve", "Check the ticker on NSE and screener.in"),
    ("financials", "Read 12 quarters and 6 years of financials"),
    ("documents", "Download the last 4 concall transcripts and the latest annual report"),
    ("chunk", "Split documents into cited passages"),
    ("promises", "Extract management's promises"),
    ("verdicts", "Check each promise against reported numbers"),
    ("cards", "Build cash quality, business and bull vs bear"),
    ("index", "Index passages for Ask"),
]
_running: set[str] = set()
_lock = threading.Lock()


def _set(db, r: CompanyResearch, step: str, state: str, note: str | None = None):
    prog = [dict(p) for p in (r.progress or [])]
    for p in prog:
        if p["key"] == step:
            p["state"] = state
            if note:
                p["note"] = note
    r.progress = prog
    r.updated_at = datetime.utcnow()
    db.commit()


def start(symbol: str) -> dict:
    """Kick off research in the background; returns immediately."""
    symbol = symbol.upper().strip()
    with _lock:
        if symbol in _running:
            return {"status": "running", "symbol": symbol}
        _running.add(symbol)
    threading.Thread(target=_thread, args=(symbol,), daemon=True).start()
    return {"status": "running", "symbol": symbol}


def _thread(symbol: str):
    try:
        run_research(symbol)
    finally:
        with _lock:
            _running.discard(symbol)


def is_running(symbol: str) -> bool:
    return symbol.upper() in _running


def run_research(symbol: str, refresh: bool = False) -> dict:
    db = SessionLocal()
    symbol = symbol.upper().strip()
    try:
        return _run(db, symbol, refresh)
    except Exception as e:  # noqa: BLE001
        log.exception("research %s failed", symbol)
        db.rollback()
        c = db.scalar(select(Company).where(Company.symbol == symbol))
        if c:
            r = db.scalar(select(CompanyResearch).where(CompanyResearch.company_id == c.id))
            if r:
                r.status, r.error = "failed", f"{e}"[:500]
                log.debug(traceback.format_exc())
                db.commit()
        return {"ok": False, "symbol": symbol, "error": str(e)}
    finally:
        db.close()


def _run(db, symbol: str, refresh: bool) -> dict:
    t0 = datetime.utcnow()
    company = db.scalar(select(Company).where(Company.symbol == symbol))
    # 1. resolve: must have NSE prices and a screener page
    parsed = None
    if not company:
        meta = prices.validate_symbol(symbol)
        if not meta:
            return {"ok": False, "symbol": symbol, "error": f"{symbol} has no NSE price history. Check the ticker."}
        try:
            parsed = screener.parse(symbol)
        except screener.NotFound:
            return {"ok": False, "symbol": symbol, "error": f"screener.in has no page for {symbol}."}
        company = Company(symbol=symbol, name=parsed["name"], is_research=True)
        db.add(company)
        db.flush()
        prices.store(db, symbol, meta["rows"])
    r = db.scalar(select(CompanyResearch).where(CompanyResearch.company_id == company.id))
    if not r:
        r = CompanyResearch(company_id=company.id)
        db.add(r)
    r.status, r.error = "running", None
    r.progress = [{"key": k, "label": label, "state": "todo"} for k, label in STEPS]
    db.commit()
    _set(db, r, "resolve", "done", company.name)

    # 2. financials
    _set(db, r, "financials", "running")
    parsed = parsed or screener.parse(symbol)
    fin = financials.load(db, company, parsed)
    if not company.sector_index:
        company.sector_index = portfolio.sector_config()["sectors"].get(company.sector or "", portfolio.NIFTY)
    try:
        if not prices.latest_close_exists(db, symbol):
            prices.store(db, symbol, prices.fetch_history(symbol, "6mo"))
    except Exception:  # noqa: BLE001
        pass
    db.commit()
    _set(db, r, "financials", "done", f"{fin['basis'].capitalize()} figures, {len(parsed['quarters'])} quarters")

    # 3. documents: last 4 transcripts + latest annual report, downloaded in parallel
    _set(db, r, "documents", "running")
    docs = parsed["documents"]
    transcripts = sorted(docs["transcripts"], key=lambda d: d["date"], reverse=True)[:4]
    ar = docs["annual_reports"][0] if docs["annual_reports"] else None
    urls = [t["url"] for t in transcripts] + ([ar["url"]] if ar else [])
    with ThreadPoolExecutor(max_workers=5) as ex:
        texts = dict(zip(urls, ex.map(pdf.pages_text, urls)))
    doc_rows = []
    for t in transcripts:
        pages = texts.get(t["url"]) or []
        if not pages:
            continue
        doc_rows.append(_doc(db, company, "transcript", t["period_label"], t["date"], t["url"],
                             {str(i + 1): p for i, p in enumerate(pages)}, len(pages)))
    ar_doc = None
    if ar and texts.get(ar["url"]):
        pages = texts[ar["url"]]
        sel = pdf.select_pages(pages)
        keep = sorted({p for nums in sel.values() for p in nums})
        ar_doc = _doc(db, company, "annual_report", ar["fy"], None, ar["url"],
                      {str(p): pages[p - 1] for p in keep}, len(pages), sel)
    db.commit()
    n_tr = len(doc_rows)
    _set(db, r, "documents", "done" if n_tr else "warn",
         f"{n_tr} transcript{'s' if n_tr != 1 else ''}" + (f", annual report {ar['fy']} ({ar_doc.pages} pages, "
                                                           f"{len(ar_doc.page_texts)} read)" if ar_doc else ", no annual report"))

    # 4. chunk (only documents that changed)
    _set(db, r, "chunk", "running")
    n_chunks = 0
    for d in doc_rows + ([ar_doc] if ar_doc else []):
        if refresh or not db.scalar(select(Chunk.id).where(Chunk.document_id == d.id).limit(1)):
            db.execute(delete(Chunk).where(Chunk.document_id == d.id))
            pages = [d.page_texts.get(str(i), "") for i in range(1, (d.pages or 0) + 1)]
            parts = chunks.chunk_transcript(pages) if d.kind == "transcript" else chunks.chunk_pages(pages, d.selected_pages or {})
            for p in parts:
                db.add(Chunk(document_id=d.id, company_id=company.id, page_from=p["page_from"], page_to=p["page_to"],
                             section=p.get("section"), speaker=p.get("speaker"), text=p["text"]))
            n_chunks += len(parts)
    db.commit()
    _set(db, r, "chunk", "done", f"{n_chunks} new passages")

    # 5. promises (one fast-model call per transcript, cached by document)
    _set(db, r, "promises", "running")
    calls, methods = [], set()
    for d in sorted(doc_rows, key=lambda x: x.doc_date):
        pages = [d.page_texts.get(str(i), "") for i in range(1, (d.pages or 0) + 1)]
        items, method = promises.extract(pages, d.period_label, company.name)
        methods.add(method)
        calls.append((d.period_label, d.id, items))
    merged = promises.merge(calls)
    old = [p.id for p in db.scalars(select(Promise).where(Promise.company_id == company.id))]
    if old:
        db.execute(delete(PromiseVerdict).where(PromiseVerdict.promise_id.in_(old)))
        db.execute(delete(Promise).where(Promise.id.in_(old)))
    for m in merged:
        db.add(Promise(company_id=company.id, document_id=m["document_id"], made_in=m["made_in"], metric=m["metric"][:160],
                       metric_key=m["metric_key"], target_text=m["target_text"][:300], target_low=m.get("target_low"),
                       target_high=m.get("target_high"), unit=(m.get("unit") or "")[:24] or None,
                       horizon=(m.get("horizon") or "")[:40] or None, quote=m["quote"], page=m.get("page"),
                       speaker=(m.get("speaker") or "")[:120] or None, repeats=m.get("repeats", []),
                       extractor="llm" if "llm" in methods else "heuristic"))
    db.commit()
    _set(db, r, "promises", "done", f"{len(merged)} commitments" + ("" if "llm" in methods else " (keyword rules; add an LLM key for better recall)"))

    # 6. verdicts
    _set(db, r, "verdicts", "running")
    score = verdict.run(db, company, fin["url"])
    db.commit()
    _set(db, r, "verdicts", "done", score["sentence"])

    # 7. cards (Should: failures here never block 'ready')
    _set(db, r, "cards", "running")
    out_cards = {"scorecard": score, "screener_url": fin["url"], "basis": fin["basis"], "is_bank": fin.get("is_bank")}
    for name, fn in (("cash", lambda: cards.cash_card(db, company, fin["url"])),
                     ("trajectory", lambda: cards.trajectory(db, company)),
                     ("business", lambda: cards.business_card(db, company))):
        try:
            out_cards[name] = fn()
        except Exception as e:  # noqa: BLE001
            log.warning("card %s failed for %s: %s", name, symbol, e)
            out_cards[name] = {"available": False}
    try:
        out_cards["bullbear"] = cards.bull_bear(db, company, out_cards.get("cash", {}), out_cards.get("trajectory", {}), score)
    except Exception as e:  # noqa: BLE001
        log.warning("bullbear failed: %s", e)
        out_cards["bullbear"] = {"bull": [], "bear": []}
    _thesis_and_tripwires(db, company, doc_rows)
    r.cards = out_cards
    db.commit()
    _set(db, r, "cards", "done")

    # 8. index: BM25 is built from the stored chunks on first use
    _set(db, r, "index", "done")
    r.status = "ready"
    company.is_research = company.is_research or not company.is_holding
    db.commit()
    return {"ok": True, "symbol": symbol, "seconds": (datetime.utcnow() - t0).seconds, "promises": len(merged),
            "scorecard": score["sentence"], "chunks": n_chunks}


def _doc(db, company, kind, period, d, url, page_texts, n_pages, selected=None) -> Document:
    doc = db.scalar(select(Document).where(Document.company_id == company.id, Document.url == url))
    if not doc:
        doc = Document(company_id=company.id, url=url, kind=kind)
        db.add(doc)
    doc.period_label, doc.doc_date, doc.pages = period, d, n_pages
    doc.page_texts, doc.selected_pages, doc.fetched_at = page_texts, selected, datetime.utcnow()
    db.flush()
    return doc


def _thesis_and_tripwires(db, company: Company, doc_rows: list[Document]):
    h = company.holding
    rows = db.execute(select(Promise, PromiseVerdict).join(PromiseVerdict, PromiseVerdict.promise_id == Promise.id)
                      .where(Promise.company_id == company.id)).all()
    if h:
        for p, v in rows:
            if v.status in ("missed", "behind") and p.target_low is not None:
                tripwires.add_promise_tripwire(db, company, p.metric_key, p.target_low, f"{p.made_in} guidance {p.target_text}")
        tripwires.ensure_standard(db, company)
    if not h or h.thesis or not doc_rows:
        return
    latest = max(doc_rows, key=lambda d: d.doc_date)
    top = [f"{p.metric}: {p.target_text} ({p.horizon})" for p, _ in rows][:5]
    if llm.available():
        try:
            opening = "\n".join(latest.page_texts.get(str(i), "") for i in range(1, 5))[:12000]
            out = llm.complete("thesis_prefill", "fast", {"company": company.name, "text": opening, "promises": top},
                               schema=ThesisOut, job="research")
            h.thesis = f"{out['thesis']} ({latest.period_label} call, p.{out.get('page') or 2})"
            h.thesis_source = "concall"
            return
        except Exception as e:  # noqa: BLE001
            log.info("thesis prefill failed: %s", e)
    if top:
        h.thesis = f"Management's stated targets ({latest.period_label} call): " + "; ".join(top[:2])
        h.thesis_source = "concall"
