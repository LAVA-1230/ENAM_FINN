"""SQLAlchemy models (spec section 6). All timestamps are naive UTC."""
from datetime import date, datetime

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.utcnow().replace(microsecond=0)


class Company(Base):
    __tablename__ = "company"
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    isin: Mapped[str | None] = mapped_column(String(20))
    bse_code: Mapped[str | None] = mapped_column(String(12))
    sector: Mapped[str | None] = mapped_column(String(80))
    sector_index: Mapped[str | None] = mapped_column(String(40))
    is_holding: Mapped[bool] = mapped_column(Boolean, default=False)
    is_research: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    holding: Mapped["Holding | None"] = relationship(back_populates="company", uselist=False)


class Holding(Base):
    __tablename__ = "holding"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), unique=True)
    quantity: Mapped[float] = mapped_column(Float)
    avg_cost: Mapped[float | None] = mapped_column(Float)
    thesis: Mapped[str | None] = mapped_column(Text)
    thesis_source: Mapped[str | None] = mapped_column(String(16))
    muted_until: Mapped[datetime | None] = mapped_column(DateTime)
    only_p0: Mapped[bool] = mapped_column(Boolean, default=False)

    company: Mapped[Company] = relationship(back_populates="holding")


class PriceDaily(Base):
    __tablename__ = "price_daily"
    __table_args__ = (UniqueConstraint("key", "date"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(40), index=True)  # NSE symbol or index symbol
    date: Mapped[date] = mapped_column(Date, index=True)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)


class Filing(Base):
    __tablename__ = "filing"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), index=True)
    exchange: Mapped[str] = mapped_column(String(8), default="NSE")
    exchange_category: Mapped[str | None] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(Text)
    attachment_url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    raw: Mapped[dict | None] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    pdf_text_path: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str | None] = mapped_column(Text)  # first pages of the PDF, kept in the DB for Ask


class Event(Base):
    __tablename__ = "event"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("company.id"), index=True)
    filing_id: Mapped[int | None] = mapped_column(ForeignKey("filing.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # filing|price|volume|tripwire|sector|cluster
    category: Mapped[str] = mapped_column(String(40))
    tier: Mapped[str] = mapped_column(String(4))
    score: Mapped[int] = mapped_column(Integer)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    title: Mapped[str] = mapped_column(Text)
    metric_line: Mapped[str | None] = mapped_column(Text)
    impact_line: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    facts: Mapped[list] = mapped_column(JSON, default=list)
    context: Mapped[list] = mapped_column(JSON, default=list)
    enrichment: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(12), default="new")
    dismiss_reason: Mapped[str | None] = mapped_column(Text)
    thesis_tag: Mapped[str | None] = mapped_column(String(16))
    verify_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(120), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    event_date: Mapped[datetime] = mapped_column(DateTime, index=True)


class FinancialQ(Base):
    __tablename__ = "financial_q"
    __table_args__ = (UniqueConstraint("company_id", "fiscal_label", "source"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), index=True)
    fiscal_label: Mapped[str] = mapped_column(String(16))
    period_end: Mapped[date] = mapped_column(Date)
    revenue: Mapped[float | None] = mapped_column(Float)
    expenses: Mapped[float | None] = mapped_column(Float)
    ebitda: Mapped[float | None] = mapped_column(Float)
    opm: Mapped[float | None] = mapped_column(Float)
    other_income: Mapped[float | None] = mapped_column(Float)
    interest: Mapped[float | None] = mapped_column(Float)
    depreciation: Mapped[float | None] = mapped_column(Float)
    pbt: Mapped[float | None] = mapped_column(Float)
    tax: Mapped[float | None] = mapped_column(Float)
    pat: Mapped[float | None] = mapped_column(Float)
    basis: Mapped[str] = mapped_column(String(16), default="consolidated")
    source: Mapped[str] = mapped_column(String(16), default="screener")


class FinancialY(Base):
    __tablename__ = "financial_y"
    __table_args__ = (UniqueConstraint("company_id", "fy"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), index=True)
    fy: Mapped[str] = mapped_column(String(8))
    revenue: Mapped[float | None] = mapped_column(Float)
    ebitda: Mapped[float | None] = mapped_column(Float)
    opm: Mapped[float | None] = mapped_column(Float)
    pat: Mapped[float | None] = mapped_column(Float)
    cfo: Mapped[float | None] = mapped_column(Float)
    capex: Mapped[float | None] = mapped_column(Float)
    fcf: Mapped[float | None] = mapped_column(Float)
    total_debt: Mapped[float | None] = mapped_column(Float)
    cash: Mapped[float | None] = mapped_column(Float)
    net_worth: Mapped[float | None] = mapped_column(Float)
    fixed_assets: Mapped[float | None] = mapped_column(Float)
    receivable_days: Mapped[float | None] = mapped_column(Float)
    inventory_days: Mapped[float | None] = mapped_column(Float)
    wc_days: Mapped[float | None] = mapped_column(Float)
    roce: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(16), default="screener")


class Document(Base):
    __tablename__ = "document"
    __table_args__ = (UniqueConstraint("company_id", "url"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    period_label: Mapped[str | None] = mapped_column(String(20))
    doc_date: Mapped[date | None] = mapped_column(Date)
    url: Mapped[str] = mapped_column(Text)
    local_path: Mapped[str | None] = mapped_column(Text)
    pages: Mapped[int | None] = mapped_column(Integer)
    selected_pages: Mapped[dict | None] = mapped_column(JSON)
    page_texts: Mapped[dict | None] = mapped_column(JSON)  # {page_no: text}; transcripts whole, reports selected pages
    content_hash: Mapped[str | None] = mapped_column(String(64))
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime)


class Chunk(Base):
    __tablename__ = "chunk"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("document.id"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), index=True)
    page_from: Mapped[int] = mapped_column(Integer)
    page_to: Mapped[int] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(120))
    speaker: Mapped[str | None] = mapped_column(String(120))
    text: Mapped[str] = mapped_column(Text)


class Promise(Base):
    __tablename__ = "promise"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), index=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("document.id"))
    made_in: Mapped[str] = mapped_column(String(16))
    metric: Mapped[str] = mapped_column(String(160))
    metric_key: Mapped[str] = mapped_column(String(24))
    target_text: Mapped[str] = mapped_column(Text)
    target_low: Mapped[float | None] = mapped_column(Float)
    target_high: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(24))
    horizon: Mapped[str | None] = mapped_column(String(40))
    quote: Mapped[str] = mapped_column(Text)
    page: Mapped[int | None] = mapped_column(Integer)
    speaker: Mapped[str | None] = mapped_column(String(120))
    repeats: Mapped[list] = mapped_column(JSON, default=list)  # [{made_in, target_text, page, doc_id}]
    extractor: Mapped[str] = mapped_column(String(12), default="llm")  # llm|heuristic


class PromiseVerdict(Base):
    __tablename__ = "promise_verdict"
    id: Mapped[int] = mapped_column(primary_key=True)
    promise_id: Mapped[int] = mapped_column(ForeignKey("promise.id"), unique=True)
    status: Mapped[str] = mapped_column(String(12))
    actual_text: Mapped[str | None] = mapped_column(Text)
    actual_value: Mapped[float | None] = mapped_column(Float)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    method: Mapped[str] = mapped_column(String(8))
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CompanyResearch(Base):
    __tablename__ = "company_research"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), unique=True)
    status: Mapped[str] = mapped_column(String(12), default="queued")
    progress: Mapped[list] = mapped_column(JSON, default=list)
    cards: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    error: Mapped[str | None] = mapped_column(Text)


class Tripwire(Base):
    __tablename__ = "tripwire"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # metric|event_count|drawdown|weight
    metric_key: Mapped[str] = mapped_column(String(32))
    op: Mapped[str] = mapped_column(String(2))
    threshold: Mapped[float] = mapped_column(Float)
    window_days: Mapped[int | None] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(8), default="auto")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_value: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(8), default="ok")


class Decision(Base):
    __tablename__ = "decision"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("event.id"))
    action: Mapped[str] = mapped_column(String(8))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AppSettings(Base):
    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    price_pct: Mapped[float] = mapped_column(Float, default=3.0)
    volume_x: Mapped[float] = mapped_column(Float, default=2.0)
    impact_pct: Mapped[float] = mapped_column(Float, default=0.5)
    tier_overrides: Mapped[dict] = mapped_column(JSON, default=dict)
    tripwire_defaults: Mapped[dict] = mapped_column(JSON, default=dict)
    push_p0_only: Mapped[bool] = mapped_column(Boolean, default=True)
    show_routine: Mapped[bool] = mapped_column(Boolean, default=False)
    quiet_start: Mapped[str] = mapped_column(String(5), default="22:00")
    quiet_end: Mapped[str] = mapped_column(String(5), default="07:00")
    p0_in_quiet: Mapped[bool] = mapped_column(Boolean, default=True)
    brief_times: Mapped[list] = mapped_column(JSON, default=lambda: ["07:30", "19:00"])
    replay: Mapped[bool] = mapped_column(Boolean, default=False)
    last_brief_seen_at: Mapped[datetime | None] = mapped_column(DateTime)


class CalendarItem(Base):
    """Upcoming board meetings / results dates from NSE intimations (feeds 'Coming up')."""
    __tablename__ = "calendar_item"
    __table_args__ = (UniqueConstraint("company_id", "date", "purpose"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    purpose: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16), default="NSE")


class PushSub(Base):
    __tablename__ = "push_sub"
    id: Mapped[int] = mapped_column(primary_key=True)
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    keys: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Notification(Base):
    __tablename__ = "notification"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("event.id"))
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(10))
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    delivered: Mapped[bool] = mapped_column(Boolean, default=False)
    read: Mapped[bool] = mapped_column(Boolean, default=False)


class LlmCache(Base):
    __tablename__ = "llm_cache"
    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    output: Mapped[dict | list | str] = mapped_column(JSON)
    model: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LlmUsage(Base):
    __tablename__ = "llm_usage"
    id: Mapped[int] = mapped_column(primary_key=True)
    job: Mapped[str | None] = mapped_column(String(40))
    prompt_name: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    cached: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class JobRun(Base):
    __tablename__ = "job_run"
    id: Mapped[int] = mapped_column(primary_key=True)
    job: Mapped[str] = mapped_column(String(40))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    ok: Mapped[bool | None] = mapped_column(Boolean)
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
