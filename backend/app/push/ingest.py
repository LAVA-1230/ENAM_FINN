"""Filings pipeline (spec 7.1): fetch -> normalise -> dedupe -> classify -> enrich -> score -> store -> notify (P0).

Three phases for speed: (1) fetch every company's announcements in parallel, (2) classify and download only
the PDFs that a card actually reads, in parallel, (3) enrich and score in order (oldest first, so cluster
checks see history)."""
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import portfolio
from ..llm import client as llm
from ..models import AppSettings, CalendarItem, Company, Event, Filing
from ..sources import nse, pdf
from . import classify, notify
from .enrich import kmp, other, results
from .enrich.base import Ctx, EnrichResult
from .score import score_event

log = logging.getLogger(__name__)
HANDLERS = {"results": results.enrich, "kmp_change": kmp.enrich, "auditor_change": kmp.enrich}
EXTRACT_CATEGORIES = ("rating", "pledge_sast", "mna", "fundraise", "order_win", "capex", "litigation", "buyback")


def get_settings_row(db: Session) -> AppSettings:
    s = db.get(AppSettings, 1)
    if not s:
        s = AppSettings(id=1, tier_overrides={}, tripwire_defaults={})
        db.add(s)
        db.flush()
    return s


def store_filing(db: Session, company: Company, n: dict) -> Filing | None:
    if db.scalar(select(Filing.id).where(Filing.content_hash == n["content_hash"])):
        return None
    # cross-exchange / repeat dedupe: same company, same day, same attachment or near-identical subject
    day_start = datetime.combine(n["published_at"].date(), datetime.min.time())
    same_day = db.scalars(select(Filing).where(Filing.company_id == company.id, Filing.published_at >= day_start,
                                               Filing.published_at < day_start + timedelta(days=1))).all()
    for f in same_day:
        if f.attachment_url and f.attachment_url == n["attachment_url"]:
            return None
        if fuzz.ratio(f.subject.lower(), n["subject"].lower()) >= 90 and f.exchange != n["exchange"]:
            return None
    f = Filing(company_id=company.id, exchange=n["exchange"], exchange_category=n["exchange_category"],
               subject=n["subject"], attachment_url=n["attachment_url"], published_at=n["published_at"],
               raw=n["raw"], content_hash=n["content_hash"])
    db.add(f)
    db.flush()
    return f


def needs_pdf(category: str, f: Filing) -> bool:
    """Only the cards that read the filing download it; routine paperwork is never downloaded."""
    if not f.attachment_url or not f.attachment_url.lower().endswith(".pdf"):
        return False
    if category in ("results", "kmp_change", "auditor_change"):
        return True
    if not llm.available():
        return False
    if category in EXTRACT_CATEGORIES:
        return True
    return category not in ("routine", "board_meeting") and not (f.raw or {}).get("voiceSummary")


def process_filing(db: Session, settings: AppSettings, company: Company, f: Filing, weight: float | None,
                   classified: tuple[str, str] | None = None) -> Event | None:
    category, method = classified or classify.classify(f.exchange_category, f.subject, (f.raw or {}).get("voiceSummary"))
    ctx = Ctx(db=db, company=company, filing=f, weight_pct=weight, price_pct=settings.price_pct, settings=settings)
    try:
        handler = HANDLERS.get(category)
        res: EnrichResult = handler(ctx) if handler else other.enrich(ctx, category)
    except Exception as e:  # noqa: BLE001  (a bad PDF must never stop the pipeline)
        log.exception("enrich failed for %s %s: %s", company.symbol, f.subject[:60], e)
        res = other.enrich(ctx, "other")
    if res.skip:
        return None
    existing = db.scalar(select(Event).where(Event.dedupe_key == res.dedupe_key)) if res.dedupe_key else None
    if existing:
        # same results quarter / same person filed twice: keep the first, remember the extra source
        srcs = list((existing.enrichment or {}).get("extra_sources", []))
        srcs.append({"filing_id": f.id, "subject": f.subject, "url": f.attachment_url})
        existing.enrichment = {**(existing.enrichment or {}), "extra_sources": srcs}
        if category == "results" and not existing.verify_ok and res.verify_ok:
            existing.filing_id = f.id
            _apply(existing, res, category, company, settings, method)
        return None
    # follow-ups: a press release or presentation on a results day is not news on its own
    if category == "concall_doc":
        near = db.scalar(select(Event.id).where(Event.company_id == company.id, Event.category == "results",
                                                Event.event_date >= f.published_at - timedelta(days=2),
                                                Event.event_date <= f.published_at + timedelta(days=1)))
        if near:
            res.signals.duplicate = True
    ev = Event(company_id=company.id, filing_id=f.id, kind="filing", dedupe_key=res.dedupe_key, event_date=f.published_at,
               category=category, tier="P3", score=0, title="")
    _apply(ev, res, category, company, settings, method)
    db.add(ev)
    db.flush()
    return ev


def _apply(ev: Event, res: EnrichResult, category: str, company: Company, settings: AppSettings, method: str):
    h = company.holding
    tier, score, reasons = score_event(category, res.signals, settings.tier_overrides,
                                       h.muted_until if h else None, h.only_p0 if h else False)
    ev.tier, ev.score, ev.reasons = tier, score, reasons
    ev.title, ev.summary, ev.metric_line, ev.impact_line = res.title, res.summary, res.metric_line, res.impact_line
    ev.facts, ev.context, ev.verify_ok = res.facts, res.context, res.verify_ok
    ev.enrichment = {**res.enrichment, "classified_by": method}


def _fetch(symbol: str, frm: date, to: date) -> tuple[str, list | None, str | None]:
    try:
        return symbol, nse.fetch_announcements(symbol, frm, to), None
    except Exception as e:  # noqa: BLE001
        log.warning("NSE fetch failed for %s: %s", symbol, e)
        return symbol, None, str(e)[:200]


def ingest_filings(db: Session, days: int = 2, symbols: list[str] | None = None) -> dict:
    settings = get_settings_row(db)
    to = date.today()
    frm = to - timedelta(days=days)
    q = select(Company).where((Company.is_holding.is_(True)) | (Company.is_research.is_(True)))
    if symbols:
        q = select(Company).where(Company.symbol.in_(symbols))
    companies = {c.symbol: c for c in db.scalars(q).all()}
    weights = {s: p["weight"] for s, p in portfolio.book(db)["positions"].items()}
    total = {"companies": len(companies), "fetched": 0, "new": 0, "events": 0, "p0": 0, "errors": 0, "pdfs": 0}

    # phase 1: fetch in parallel (requests to NSE are still spaced by the polite per-host gap)
    with ThreadPoolExecutor(max_workers=4) as ex:
        fetched = list(ex.map(lambda s: _fetch(s, frm, to), companies))
    new: list[tuple[Company, Filing]] = []
    for sym, anns, err in fetched:
        c = companies[sym]
        if err is not None:
            total["errors"] += 1
            continue
        total["fetched"] += len(anns)
        if anns and not c.isin:
            c.isin = anns[0].get("sm_isin")
        for n in sorted((nse.normalise(a) for a in anns), key=lambda n: n["published_at"]):
            f = store_filing(db, c, n)  # whole batch stored first: handlers can see same-day sibling filings
            if f:
                new.append((c, f))
    db.commit()

    # phase 2: classify (rules first) and download only the PDFs a card reads, in parallel
    classified = {f.id: classify.classify(f.exchange_category, f.subject, (f.raw or {}).get("voiceSummary")) for _, f in new}
    urls = [f.attachment_url for _, f in new if needs_pdf(classified[f.id][0], f)]
    total["pdfs"] = len(urls)
    pdf.prefetch(urls, workers=4)

    # phase 3: enrich and score, oldest first so cluster checks see history
    new.sort(key=lambda cf: cf[1].published_at)
    for c, f in new:
        total["new"] += 1
        ev = process_filing(db, settings, c, f, weights.get(c.symbol), classified[f.id])
        if ev:
            total["events"] += 1
            if ev.tier == "P0":
                total["p0"] += 1
                if ev.event_date >= datetime.utcnow() - timedelta(hours=36):
                    notify.notify_event(db, ev, c)
        db.commit()
    total["classifier"] = dict(classify.STATS)
    return total


def refresh_calendar(db: Session) -> int:
    """Upcoming board meetings for our companies, from NSE's event calendar."""
    try:
        rows = nse.fetch_calendar()
    except Exception as e:  # noqa: BLE001
        log.warning("calendar fetch failed: %s", e)
        return 0
    by_sym = {c.symbol: c for c in db.scalars(select(Company)).all()}
    n = 0
    for r in rows:
        c = by_sym.get(r["symbol"])
        if not c:
            continue
        exists = db.scalar(select(CalendarItem).where(CalendarItem.company_id == c.id, CalendarItem.date == r["date"],
                                                      CalendarItem.purpose == r["purpose"][:200]))
        if not exists:
            db.add(CalendarItem(company_id=c.id, date=r["date"], purpose=r["purpose"][:200], detail=r["desc"][:500]))
            n += 1
    db.flush()
    return n
