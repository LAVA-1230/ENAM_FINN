"""JSON schemas for LLM outputs (spec Appendix 17.4)."""
from typing import Literal

from pydantic import BaseModel, Field


class ClassifyOut(BaseModel):
    category: str
    confidence: float = 0.0


class ResultsColumn(BaseModel):
    label: str | None = None
    revenue: float | None = None
    other_income: float | None = None
    total_expenses: float | None = None
    finance_costs: float | None = None
    depreciation: float | None = None
    exceptional_items: float | None = None
    pbt: float | None = None
    tax: float | None = None
    pat: float | None = None
    interest_earned: float | None = None
    operating_profit: float | None = None
    provisions: float | None = None


class ResultsExtract(BaseModel):
    basis: Literal["consolidated", "standalone"] = "consolidated"
    unit: Literal["lakh", "crore", "million", "thousand"] = "crore"
    is_bank_format: bool = False
    current: ResultsColumn
    previous_quarter: ResultsColumn
    year_ago_quarter: ResultsColumn
    page: int | None = None


class Successor(BaseModel):
    name: str | None = None
    role: str | None = None
    interim: bool | None = None


class KmpExtract(BaseModel):
    person: str | None = None
    role: str | None = None
    change: str | None = None
    reason_stated: str | None = None
    effective_date: str | None = None
    successor: Successor | None = None
    profile_text: str | None = None
    tenure_text: str | None = None


class BioLine(BaseModel):
    text: str
    source: str | None = None


class BioOut(BaseModel):
    lines: list[BioLine] = Field(default_factory=list)


class OneLiner(BaseModel):
    line: str


class EventExtract(BaseModel):
    amount_text: str | None = None
    amount_crore: float | None = None
    counterparty: str | None = None
    rating_old: str | None = None
    rating_new: str | None = None
    outlook: str | None = None
    agency: str | None = None
    instrument: str | None = None
    direction: str | None = None
    pledge_before_pct: float | None = None
    pledge_after_pct: float | None = None
    key_quote: str | None = None


class PromiseItem(BaseModel):
    metric: str
    metric_key: Literal["revenue_growth", "ebitda_margin", "pat_growth", "capex", "net_debt", "volume",
                        "plant", "launch", "market_share", "other"] = "other"
    target_text: str
    target_low: float | None = None
    target_high: float | None = None
    unit: str | None = None
    horizon: str | None = None
    quote: str
    page: int | None = None
    speaker: str | None = None


class PromiseExtract(BaseModel):
    period_label: str | None = None
    promises: list[PromiseItem] = Field(default_factory=list)


class JudgeItem(BaseModel):
    promise_id: int
    status: Literal["kept", "missed", "late", "on_track", "behind", "dropped", "pending"] = "pending"
    actual_text: str | None = None
    citations: list[int] = Field(default_factory=list)


class JudgeOut(BaseModel):
    verdicts: list[JudgeItem] = Field(default_factory=list)


class SourcedPoint(BaseModel):
    text: str
    source: str | None = None


class BullBear(BaseModel):
    bull: list[SourcedPoint] = Field(default_factory=list)
    bear: list[SourcedPoint] = Field(default_factory=list)


class Segment(BaseModel):
    name: str
    revenue: float | None = None
    share_pct: float | None = None
    line: str | None = None
    page: int | None = None


class Geo(BaseModel):
    region: str
    share_pct: float | None = None
    page: int | None = None


class PageText(BaseModel):
    text: str
    page: int | None = None


class BusinessOut(BaseModel):
    segments: list[Segment] = Field(default_factory=list)
    unit: str | None = None
    period: str | None = None
    geography: list[Geo] = Field(default_factory=list)
    description: PageText | None = None


class ThesisOut(BaseModel):
    thesis: str
    page: int | None = None


class PrepOut(BaseModel):
    questions: list[str] = Field(default_factory=list)
