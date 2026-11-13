"""Shared types and helpers for enrichment handlers.

Each handler returns an EnrichResult: `facts` come from the filing, `context` is computed by FINN
in Python, `enrichment` holds card-specific data. The LLM never writes "why it matters"."""
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import fmt, portfolio
from ...models import Company, Filing, FinancialY, PriceDaily
from ...sources import pdf
from ..score import Signals

IST = timezone(timedelta(hours=5, minutes=30))


@dataclass
class Ctx:
    db: Session
    company: Company
    filing: Filing
    weight_pct: float | None
    price_pct: float  # user's threshold
    settings: object


@dataclass
class EnrichResult:
    title: str
    signals: Signals
    summary: str | None = None
    metric_line: str | None = None
    impact_line: str | None = None
    facts: list = field(default_factory=list)      # [{k, v, src, quote?}]
    context: list = field(default_factory=list)    # [str]
    enrichment: dict = field(default_factory=dict)
    verify_ok: bool = True
    dedupe_key: str | None = None
    skip: bool = False                              # drop this filing (merged into an existing event)


def filing_text(f: Filing, max_pages: int = 3) -> str:
    if not f.attachment_url or not f.attachment_url.lower().endswith(".pdf"):
        return ""
    pages = pdf.pages_text(f.attachment_url, max_pages=max_pages)
    text = "\n".join(f"=== page {i + 1} ===\n{t}" for i, t in enumerate(pages))
    if text and not f.text:
        f.text = text[:20000]  # kept in the DB so Ask can cite filings after a redeploy
    return text


def nse_summary(f: Filing) -> str | None:
    return ((f.raw or {}).get("voiceSummary") or "").strip() or None


def strip_company(text: str, company_name: str) -> str:
    """'Titan Company Limited has fully redeemed ...' -> 'Fully redeemed ...'."""
    base = re.escape(company_name.split(" Ltd")[0].split(" Limited")[0])
    t = re.sub(rf"^(the\s+)?{base}[\w\s.&()-]*?\s+(Limited|Ltd\.?)?\s*(has|have|is)?\s*", "", text, flags=re.I)
    t = re.sub(r"^(the company|it)\s+(has|have|is)\s+", "", t, flags=re.I)
    return t[:1].upper() + t[1:] if t else text


def first_sentence(text: str, limit: int = 140) -> str:
    s = re.split(r"(?<=[.!?])\s+", text.strip())[0]
    if len(s) <= limit:
        return s
    cut = s[:limit - 1].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"


def free_one_liner(f: Filing, company_name: str) -> str | None:
    """NSE's own summary, first sentence, company name stripped. Zero LLM cost."""
    s = nse_summary(f)
    return first_sentence(strip_company(s, company_name)) if s else None


def session_for(published_utc: datetime) -> date:
    """Filings after the 15:30 IST close are priced in by the next session."""
    ist = published_utc.replace(tzinfo=timezone.utc).astimezone(IST)
    d = ist.date()
    if (ist.hour, ist.minute) >= (15, 30):
        d += timedelta(days=1)
    return d


def price_reaction(ctx: Ctx) -> tuple[str | None, portfolio.Move | None]:
    """Same-session move after the filing. Returns (reason if it confirms, move)."""
    target = session_for(ctx.filing.published_at)
    d = ctx.db.scalar(select(PriceDaily.date).where(PriceDaily.key == ctx.company.symbol,
                                                     PriceDaily.date >= target)
                      .order_by(PriceDaily.date).limit(1))
    if not d or (d - target).days > 4:
        return None, None
    mv = portfolio.move_on(ctx.db, ctx.company, d)
    if not mv or mv.specific is None:
        return None, mv
    if abs(mv.specific) >= ctx.price_pct / 2:
        verb = "rose" if mv.ret > 0 else "fell"
        return (f"Stock {verb} {fmt.signed_pct(mv.ret)[1:]} vs {portfolio.index_name(mv.index_sym)} "
                f"{fmt.signed_pct(mv.index_ret)} on {day(mv.d)}"), mv
    return None, mv


def move_metric_line(mv: portfolio.Move | None) -> str | None:
    if not mv:
        return None
    idx = portfolio.index_name(mv.index_sym)
    return f"{fmt.signed_pct(mv.ret)} vs {idx} {fmt.signed_pct(mv.index_ret)}"


def impact_line(ctx: Ctx, mv: portfolio.Move | None) -> str | None:
    if ctx.weight_pct is None:
        return None
    h = ctx.company.holding
    parts = [f"{ctx.weight_pct:.1f}% of your book"]
    if mv and h:
        parts.append(f"{fmt.rupees(h.quantity * (mv.close - mv.prev_close), signed=True)} on {day(mv.d)}")
    return ", ".join(parts)


def day(d: date) -> str:
    return f"{d.day} {d.strftime('%b')}"


def latest_fy_revenue(db: Session, company_id: int) -> tuple[float | None, str | None]:
    row = db.scalar(select(FinancialY).where(FinancialY.company_id == company_id, FinancialY.revenue.is_not(None))
                    .order_by(FinancialY.fy.desc()).limit(1))
    return (row.revenue, row.fy) if row else (None, None)


def latest_fy(db: Session, company_id: int):
    return db.scalar(select(FinancialY).where(FinancialY.company_id == company_id, FinancialY.revenue.is_not(None))
                     .order_by(FinancialY.fy.desc()).limit(1))
