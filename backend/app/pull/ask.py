"""Ask (spec 8.7): answers grounded only in one company's transcripts, annual-report pages, filings and
tables computed from its filings. Portfolio-level questions are answered from computed data, no retrieval.

Smart model when a key is set; otherwise an extractive answer that quotes the best-matching passages.
Either way the guard keeps only sentences with a valid [n] citation and numbers found in the cited source."""
import logging
import re
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import fmt
from ..llm import client as llm
from ..llm.guard import NOT_FOUND, check_cited, has_banned, scrub_banned
from ..models import Company, Document, Event, Filing, FinancialQ, Promise, PromiseVerdict
from . import retrieval

log = logging.getLogger(__name__)
PORTFOLIO_Q = re.compile(r"\b(my (portfolio|book|holdings)|portfolio|what moved|biggest (mover|loser|gainer))\b", re.I)

SUGGESTED = {
    "results": ["What did management guide for margins this year?", "What drove revenue growth this quarter?",
                "What did they say about costs and raw materials?"],
    "kmp_change": ["What did management say about leadership and succession?", "Who runs finance at the company?",
                   "Has the company changed its plans recently?"],
    "auditor_change": ["What did the annual report say about internal controls?", "Who are the company's auditors?",
                       "Were there any qualifications in the audit report?"],
    "rating": ["How much debt does the company carry?", "What is the plan for borrowings?",
               "What did management say about cash flow?"],
    "price_move": ["What did management guide for this year?", "What are the main risks management mentioned?",
                   "What did the last concall say about demand?"],
    "company": ["What did management guide for this year?", "What are the plans for capex and capacity?",
                "What did they say about margins in the last call?"],
    "portfolio": ["What moved my portfolio?", "Which holdings need attention today?",
                  "Which holdings have results coming up?"],
}


def suggested(category: str | None, symbol: str | None) -> list[str]:
    if not symbol:
        return SUGGESTED["portfolio"]
    if category in ("volume_spike", "sector_move", "tripwire"):
        category = "price_move"
    return SUGGESTED.get(category or "company", SUGGESTED["company"])


def _source_label(doc: Document | None, page: int | None) -> str:
    if not doc:
        return "Source"
    kind = {"transcript": "Concall transcript", "annual_report": "Annual report", "presentation": "Investor presentation",
            "results": "Results"}.get(doc.kind, doc.kind)
    return f"{kind} {doc.period_label or ''}".strip() + (f", p.{page}" if page else "")


def _structured_rows(db: Session, company: Company) -> list[dict]:
    """Numbers computed from filings, as sources the model can cite."""
    out = []
    qs = db.scalars(select(FinancialQ).where(FinancialQ.company_id == company.id, FinancialQ.source == "screener")
                    .order_by(FinancialQ.period_end.desc()).limit(5)).all()
    if qs:
        lines = []
        for q in qs:
            margin = f", EBITDA margin {q.ebitda / q.revenue * 100:.1f}%" if q.ebitda is not None and q.revenue else ""
            lines.append(f"{q.fiscal_label}: revenue {fmt.crore(q.revenue)}, EBITDA {fmt.crore(q.ebitda)}, "
                         f"PAT {fmt.crore(q.pat)}{margin}")
        out.append({"kind": "table", "label": "Quarterly results table (screener.in, from company filings)",
                    "text": "\n".join(lines), "url": f"https://www.screener.in/company/{company.symbol}/consolidated/"})
    rows = db.execute(select(Promise, PromiseVerdict).outerjoin(PromiseVerdict, PromiseVerdict.promise_id == Promise.id)
                      .where(Promise.company_id == company.id)).all()
    if rows:
        lines = [f"{p.metric}: target {p.target_text} for {p.horizon or 'n/a'} (said in {p.made_in} call, p.{p.page or '?'})"
                 f"; status {v.status.replace('_', ' ') if v else 'pending'}{'; ' + v.actual_text if v and v.actual_text else ''}"
                 for p, v in rows[:10]]
        out.append({"kind": "promises", "label": "FINN promise ledger (from transcripts)", "text": "\n".join(lines), "url": None})
    return out


def _filings(db: Session, company: Company, query: str, event_id: int | None) -> list[dict]:
    q = select(Filing).where(Filing.company_id == company.id, Filing.text.is_not(None),
                             Filing.published_at >= datetime.utcnow() - timedelta(days=120))
    fl = db.scalars(q.order_by(Filing.published_at.desc()).limit(20)).all()
    want = set(retrieval.tokens(query))
    ev_filing = db.get(Event, event_id).filing_id if event_id and db.get(Event, event_id) else None
    scored = []
    for f in fl:
        toks = set(retrieval.tokens(f.subject + " " + (f.text or "")[:6000]))
        s = len(want & toks) + (100 if f.id == ev_filing else 0)
        if s:
            scored.append((s, f))
    out = []
    for _, f in sorted(scored, key=lambda x: -x[0])[:2]:
        out.append({"kind": "filing", "label": f"Filing {f.published_at:%d %b %Y}: {f.subject[:70]}",
                    "text": (f.text or "")[:2500], "url": f.attachment_url, "filing_id": f.id})
    return out


def _portfolio_answer(db: Session, question: str) -> dict:
    from ..push.digest import build_brief
    b = build_brief(db, "24h")
    h = b.get("header")
    sources, sents = [], []
    if h:
        sources.append({"n": 1, "label": f"Portfolio, {h['freshness']}", "kind": "computed", "url": None,
                        "excerpt": h["sentence"]})
        sents.append(f"Your book moved {fmt.signed_pct(h['ret'], 2)} ({fmt.rupees(h['rs'], signed=True)}). {h['sentence']} [1]")
        top = ", ".join(f"{c['name']} {fmt.rupees(c['rs'], signed=True)}" for c in h["contributors"][:3] if c["symbol"])
        if top:
            sents.append(f"Largest contributors: {top}. [1]")
    for e in b["attention"][:3]:
        n = len(sources) + 1
        sources.append({"n": n, "label": f"{e['company'] or 'Portfolio'}: {e['title']}", "kind": "event",
                        "event_id": e["id"], "url": f"/event/{e['id']}", "excerpt": e.get("metric_line") or e["title"]})
        sents.append(f"{e['company'] or 'Portfolio'}: {e['title']}. [{n}]")
    if "result" in question.lower() or "coming" in question.lower():
        for c in b["coming_up"][:3]:
            sents.append(f"{c['label']} on {c['date']}.")
    if not sents:
        return {"answer": "Nothing needs you today, and no prices are stored yet.", "found": False, "citations": []}
    return {"answer": " ".join(sents), "found": True, "citations": sources}


# words too common in investor questions to count as a match on their own
WEAK = set("management company guide guided guidance year quarter said say says tell about business plan plans last next "
           "think expect current fy".split())


def _extractive(question: str, sources: list[dict]) -> str:
    """No LLM: the 2-3 sentences from the sources that best match the question, cited."""
    want = set(retrieval.tokens(question))
    strong = want - WEAK or want

    def score(text: str) -> float:
        toks = set(retrieval.tokens(text))
        if not strong & toks:
            return 0
        return 2 * len(strong & toks) + 0.5 * len((want - strong) & toks) + (0.5 if re.search(r"\d", text) else 0)

    cands = []
    for s in sources:
        if s["kind"] in ("table", "promises"):
            for line in s["text"].splitlines():
                sc = score(line)
                if sc:
                    cands.append((sc + (1 if s["kind"] == "promises" else 0), f"{line.strip()}. [{s['n']}]"))
            continue
        bonus = 1 if s["kind"] == "chunk" and "transcript" in s["label"].lower() else 0
        for sent in re.split(r"(?<=[.?!])\s+", re.sub(r"\s+", " ", s["text"])):
            sent = sent.strip()
            if not (40 <= len(sent) <= 320) or sent.endswith("?") or not sent[0].isupper():
                continue
            sc = score(sent)
            if sc >= 2:
                cands.append((sc + bonus, f"{sent.rstrip('.')}. [{s['n']}]"))
    cands.sort(key=lambda x: -x[0])
    seen, out = set(), []
    for _, s in cands:
        k = s[:60]
        if k in seen:
            continue
        seen.add(k)
        out.append(s)
        if len(out) >= 3:
            break
    return " ".join(out)


def answer(db: Session, question: str, symbol: str | None = None, event_id: int | None = None) -> dict:
    question = question.strip()[:500]
    event = db.get(Event, event_id) if event_id else None
    company = None
    if symbol:
        company = db.scalar(select(Company).where(Company.symbol == symbol.upper()))
    elif event and event.company_id:
        company = db.get(Company, event.company_id)
    cat = event.category if event else None
    if not company:
        if PORTFOLIO_Q.search(question) or not symbol:
            out = _portfolio_answer(db, question)
            out.update({"context": "Your portfolio", "suggested": suggested(None, None), "method": "computed"})
            return out
        return {"answer": NOT_FOUND, "found": False, "citations": [], "context": symbol, "suggested": [], "method": "none"}

    hits = retrieval.search(db, company.id, question, k=8)
    docs = {d.id: d for d in db.scalars(select(Document).where(Document.id.in_({c.document_id for c, _ in hits}))).all()} if hits else {}
    sources = []
    for c, _ in hits:
        d = docs.get(c.document_id)
        sources.append({"kind": "chunk", "chunk_id": c.id, "document_id": c.document_id, "page": c.page_from,
                        "label": _source_label(d, c.page_from) + (f", {c.speaker}" if c.speaker else ""),
                        "text": c.text[:2400], "url": (d.url + f"#page={c.page_from}") if d else None})
    sources += _filings(db, company, question, event_id)
    sources += _structured_rows(db, company)
    for i, s in enumerate(sources, start=1):
        s["n"] = i
    ctx_label = company.name + (f", {event.title}" if event else "")
    if not [s for s in sources if s["kind"] in ("chunk", "filing")] and not hits:
        has_docs = db.scalar(select(Document.id).where(Document.company_id == company.id).limit(1))
        if not has_docs and not sources:
            return {"answer": f"FINN hasn't read {company.name}'s transcripts yet. Open Research to read them first.",
                    "found": False, "citations": [], "context": ctx_label, "suggested": suggested(cat, company.symbol),
                    "method": "none", "needs_research": True}

    text, method = "", "extractive"
    if llm.available() and sources:
        try:
            raw = llm.complete("ask_answer", "smart", {
                "question": question, "context_label": ctx_label,
                "sources": "\n\n".join(f"[{s['n']}] {s['label']}\n{s['text']}" for s in sources)}, job="ask")
            if has_banned(raw):
                raw = scrub_banned(raw)
            text, method = raw, "llm"
        except Exception as e:  # noqa: BLE001
            log.info("ask llm failed, using extractive answer: %s", e)
    if not text:
        text = _extractive(question, sources)
    if not text or text.strip().startswith("Not found"):
        return {"answer": NOT_FOUND, "found": False, "citations": [], "context": ctx_label,
                "suggested": suggested(cat, company.symbol), "method": method}
    checked = check_cited(text, {s["n"]: s["text"] for s in sources})
    if not checked["text"]:
        return {"answer": NOT_FOUND, "found": False, "citations": [], "context": ctx_label, "dropped": checked["dropped"],
                "suggested": suggested(cat, company.symbol), "method": method}
    used = set(checked["used_ids"])
    cites = [{"n": s["n"], "label": s["label"], "kind": s["kind"], "url": s.get("url"), "page": s.get("page"),
              "chunk_id": s.get("chunk_id"), "document_id": s.get("document_id"), "filing_id": s.get("filing_id"),
              "excerpt": _excerpt(s["text"], question)} for s in sources if s["n"] in used]
    return {"answer": checked["text"], "found": True, "citations": cites, "context": ctx_label, "method": method,
            "dropped": len(checked["dropped"]), "suggested": suggested(cat, company.symbol)}


def _excerpt(text: str, question: str, n: int = 320) -> str:
    """The part of a source that best matches the question, for the source viewer."""
    want = set(retrieval.tokens(question))
    flat = re.sub(r"\s+", " ", text)
    sents = re.split(r"(?<=[.?!])\s+", flat)
    best = max(sents, key=lambda s: len(want & set(retrieval.tokens(s))), default=flat)
    return best[:n]

