"""Priority scoring (spec 7.6 and Appendix 17.2). Pure function: easy to unit-test.

score = base(tier) + escalators - dampeners; tier from score; then the user's per-category
override; then the holding's mute / only-P0 setting. Reasons are short strings shown on the card."""
from dataclasses import dataclass, field
from datetime import datetime

BASE = {"P0": 90, "P1": 70, "P2": 40, "P3": 10}
DEFAULT_TIER = {
    "auditor_change": "P1", "default": "P0", "kmp_change": "P2", "results": "P1", "rating": "P2",
    "pledge_sast": "P1", "insider": "P2", "mna": "P1", "fundraise": "P1", "buyback": "P1",
    "order_win": "P2", "capex": "P2", "litigation": "P2", "clarification": "P2", "concall_doc": "P2",
    "dividend_corp": "P2", "board_meeting": "P3", "routine": "P3", "other": "P2",
    "price_move": "P1", "volume_spike": "P2", "sector_move": "P1", "tripwire": "P0",
}
CATEGORY_LABEL = {
    "auditor_change": "Auditor change", "default": "Payment default", "kmp_change": "Management change",
    "results": "Quarterly results", "rating": "Credit rating", "pledge_sast": "Promoter pledge",
    "insider": "Insider trade", "mna": "M&A or divestment", "fundraise": "Fund-raise", "buyback": "Buyback",
    "order_win": "Order win", "capex": "Capex or capacity", "litigation": "Litigation or regulator",
    "clarification": "Exchange clarification", "concall_doc": "Concall and investor documents",
    "dividend_corp": "Dividend, bonus or split", "board_meeting": "Board meeting notice",
    "routine": "Routine compliance", "other": "Other filings", "price_move": "Stock-specific price move",
    "volume_spike": "Unusual volume", "sector_move": "Sector move", "tripwire": "Tripwire hit",
}


@dataclass
class Signals:
    base_tier: str
    base_reason: str
    locked: bool = False              # auditor resignation, default, tripwire: never de-escalate
    cluster: str | None = None        # e.g. "2nd key exit in 5 months"
    weight_pct: float | None = None   # holding weight in the portfolio
    size_reason: str | None = None    # e.g. "Order is 12% of FY26 revenue"
    price_confirms: str | None = None  # e.g. "Stock fell 6.2% the same day"
    duplicate: bool = False
    extra_reasons: list[str] = field(default_factory=list)


def tier_for(score: int) -> str:
    return "P0" if score >= 85 else "P1" if score >= 60 else "P2" if score >= 30 else "P3"


def score_event(category: str, sig: Signals, tier_overrides: dict | None = None,
                muted_until: datetime | None = None, only_p0: bool = False,
                now: datetime | None = None) -> tuple[str, int, list[str]]:
    s = BASE[sig.base_tier]
    reasons = [sig.base_reason] if sig.base_reason else []
    if sig.cluster:
        s += 15
        reasons.append(sig.cluster)
    if sig.weight_pct is not None and sig.weight_pct > 8:
        s += 10
        reasons.append(f"{sig.weight_pct:.1f}% of your book")
    elif sig.weight_pct is not None and sig.base_tier in ("P0", "P1"):
        reasons.append(f"{sig.weight_pct:.1f}% of your book")
    if sig.size_reason:
        s += 10
        reasons.append(sig.size_reason)
    if sig.price_confirms:
        s += 10
        reasons.append(sig.price_confirms)
    if sig.duplicate:
        s -= 20
        reasons.append("Follow-up to an item already shown")
    reasons.extend(sig.extra_reasons)

    tier = tier_for(s)
    if sig.locked and BASE[tier] < BASE[sig.base_tier]:
        tier = sig.base_tier
    override = (tier_overrides or {}).get(category)
    if override in BASE:
        if override != tier:
            reasons.append(f"Your setting: {CATEGORY_LABEL.get(category, category).lower()} are {label(override)}")
        tier = override
    now = now or datetime.utcnow()
    if tier != "P0" and ((muted_until and muted_until > now) or only_p0):
        tier = "P3"
        reasons.append("Holding muted" if muted_until and muted_until > now else "Holding set to urgent only")
    return tier, max(0, min(100, s)), reasons


def label(tier: str) -> str:
    return {"P0": "urgent", "P1": "today", "P2": "for your information", "P3": "routine"}[tier]
