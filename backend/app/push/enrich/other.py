"""Enrichment for the remaining categories (spec 7.4.3 - 7.4.6).

Ratings, pledges, M&A, fund-raises, orders, capex, buybacks, litigation: extract the amount (fast model,
or a regex on the subject and NSE's own summary), then compute size vs company in Python
("Order is 12% of FY26 revenue"). Everything else gets a one-line summary (NSE's summary, free) or,
for routine items, just the title."""
import logging
import re

from ... import fmt
from ...llm import client as llm
from ...llm.schemas import EventExtract, OneLiner
from ...llm.guard import has_banned
from ..score import DEFAULT_TIER, Signals
from .base import (Ctx, EnrichResult, filing_text, first_sentence, free_one_liner, impact_line, latest_fy,
                   nse_summary, price_reaction, strip_company)

log = logging.getLogger(__name__)
AMOUNT_RE = re.compile(r"(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d+)?)\s*(crores?|cr\.?|lakhs?|lacs?|million|mn|billion|bn)?"
                       r"|(?:usd|us\$|\$)\s*([\d,]+(?:\.\d+)?)\s*(million|mn|billion|bn)?", re.I)
USD_INR = 88.0  # for size estimates only; labelled "approx." on the card
RATING_SCALE = ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-", "B+", "B", "B-",
                "C", "D"]

TITLES = {
    "rating": "Credit rating update", "pledge_sast": "Promoter pledge or SAST filing", "insider": "Insider trade disclosure",
    "mna": "M&A or divestment", "fundraise": "Fund-raise", "buyback": "Buyback", "order_win": "Order win",
    "capex": "Capex or capacity update", "litigation": "Litigation or regulatory action", "default": "Payment default or delay",
    "clarification": "Clarification to the exchange", "concall_doc": "Concall or investor document",
    "dividend_corp": "Dividend, bonus or split", "board_meeting": "Board meeting notice", "routine": "Routine filing",
    "other": "Filing",
}


def regex_amount(text: str) -> tuple[str | None, float | None]:
    best = None
    for m in AMOUNT_RE.finditer(text or ""):
        if m.group(1):
            v = float(m.group(1).replace(",", ""))
            u = (m.group(2) or "").lower()
            cr = v if u.startswith("cr") else v / 100 if u.startswith(("lakh", "lac")) else v / 10 if u in ("million", "mn") \
                else v * 100 if u in ("billion", "bn") else None
        else:
            v = float(m.group(3).replace(",", ""))
            u = (m.group(4) or "million").lower()
            cr = v * USD_INR / 10 if u in ("million", "mn") else v * USD_INR * 100
        if cr is not None and (best is None or cr > best[1]):
            best = (m.group(0).strip(), cr)
    return best if best else (None, None)


def rating_direction(old: str | None, new: str | None) -> str | None:
    def rank(r):
        m = re.search(r"(AAA|AA[+-]?|A[+-]?|BBB[+-]?|BB[+-]?|B[+-]?|C|D)\b", (r or "").upper())
        return RATING_SCALE.index(m.group(1)) if m and m.group(1) in RATING_SCALE else None
    a, b = rank(old), rank(new)
    if a is None or b is None:
        return None
    return "upgrade" if b < a else "downgrade" if b > a else "reaffirm"


def clean_subject(subject: str, company_name: str) -> str:
    """'Titan Company Limited has informed the Exchange about Redemption of CP' -> 'Redemption of CP'."""
    s = re.sub(r"^.*?has (informed|submitted to) the exchange(,)?\s*(about|regarding|that|the)?\s*", "", subject, flags=re.I)
    s = strip_company(s, company_name).strip(" .")
    return s[:1].upper() + s[1:] if s else subject


def one_liner(ctx: Ctx, tier: str) -> str | None:
    """P2 gets a one-liner; NSE's own summary first (free), the fast model only if NSE has none. P3: none."""
    if tier == "P3":
        return None
    free = free_one_liner(ctx.filing, ctx.company.name)
    if free:
        return free
    if not llm.available():
        return None
    text = filing_text(ctx.filing, max_pages=2)
    if not text:
        return None
    try:
        out = llm.complete("one_liner", "fast", {"company": ctx.company.name, "subject": ctx.filing.subject,
                                                 "text": text[:8000]}, schema=OneLiner, job="enrich_generic")
        line = out["line"].strip()
        return None if has_banned(line) else line[:140]
    except Exception as e:  # noqa: BLE001
        log.info("one_liner failed: %s", e)
        return None


def enrich(ctx: Ctx, category: str) -> EnrichResult:
    f = ctx.filing
    base_tier = DEFAULT_TIER.get(category, "P2")
    summary_src = f"{f.subject} {nse_summary(f) or ''}"
    reaction, mv = price_reaction(ctx)
    sig = Signals(base_tier=base_tier, base_reason=TITLES.get(category, "Filing"), weight_pct=ctx.weight_pct,
                  price_confirms=reaction if base_tier in ("P0", "P1", "P2") else None,
                  locked=category == "default")
    facts, context, enrichment = [], [], {}
    data = {}
    needs_extract = category in ("rating", "pledge_sast", "mna", "fundraise", "order_win", "capex", "litigation", "buyback")
    if needs_extract and llm.available():
        text = filing_text(f, max_pages=3)
        if text:
            try:
                data = llm.complete("event_extract", "fast", {"category": category, "subject": f.subject,
                                                              "text": text[:15000]}, schema=EventExtract, job="enrich_action")
            except Exception as e:  # noqa: BLE001
                log.info("event_extract failed: %s", e)
    if needs_extract and not data.get("amount_crore"):
        amt_text, amt_cr = regex_amount(summary_src)
        if amt_cr:
            data["amount_text"], data["amount_crore"] = amt_text, amt_cr

    fy = latest_fy(ctx.db, ctx.company.id)
    amt = data.get("amount_crore")
    if amt:
        facts.append({"k": "Amount", "v": data.get("amount_text") or fmt.crore(amt), "src": "filing"})
        enrichment["amount_crore"] = amt
    if data.get("counterparty"):
        facts.append({"k": "Counterparty", "v": data["counterparty"], "src": "filing"})
    if data.get("key_quote"):
        facts.append({"k": "From the filing", "v": data["key_quote"], "src": "filing", "quote": True})

    # size vs company (thresholds from Appendix 17.2)
    if amt and fy:
        if category == "order_win" and fy.revenue:
            share = amt / fy.revenue * 100
            context.append(f"Order is {share:.1f}% of {fy.fy} revenue ({fmt.crore(fy.revenue)})")
            enrichment["size_vs_company"] = {"pct": share, "base": f"{fy.fy} revenue"}
            if share > 10:
                sig.size_reason = f"Order is {share:.0f}% of {fy.fy} revenue"
                sig.base_tier = "P1"
        elif category in ("mna", "fundraise", "capex", "litigation", "buyback") and fy.net_worth:
            share = amt / fy.net_worth * 100
            base = {"capex": fy.fixed_assets or fy.net_worth}.get(category, fy.net_worth)
            base_name = f"{fy.fy} gross block" if category == "capex" and fy.fixed_assets else f"{fy.fy} net worth"
            share = amt / base * 100
            context.append(f"Amount is {share:.1f}% of {base_name}")
            enrichment["size_vs_company"] = {"pct": share, "base": base_name}
            limit = {"mna": 10, "fundraise": 10, "capex": 25, "litigation": 5, "buyback": 100}[category]
            if share > limit:
                sig.size_reason = f"{share:.0f}% of {base_name}"
                sig.base_tier = "P0" if category in ("mna", "fundraise") else "P1"
            elif category == "fundraise" and share < 5:
                sig.base_tier = "P2"

    if category == "rating":
        direction = (data.get("direction") or rating_direction(data.get("rating_old"), data.get("rating_new"))
                     or ("downgrade" if re.search(r"downgrad", summary_src, re.I) else
                         "upgrade" if re.search(r"upgrad", summary_src, re.I) else
                         "reaffirm" if re.search(r"reaffirm", summary_src, re.I) else None))
        enrichment["rating"] = {k: data.get(k) for k in ("agency", "instrument", "rating_old", "rating_new", "outlook")}
        enrichment["rating"]["direction"] = direction
        if direction == "downgrade":
            lender = (ctx.company.sector or "") in ("Banks", "Financials")
            de = (fy.total_debt / fy.net_worth) if fy and fy.total_debt and fy.net_worth else 0
            sig.base_tier = "P0" if lender or de > 1 else "P1"
            sig.base_reason = "Credit rating downgraded"
        elif direction == "upgrade":
            sig.base_tier, sig.base_reason = "P2", "Credit rating upgraded"
        else:
            sig.base_tier, sig.base_reason = "P3", "Rating reaffirmed" if direction == "reaffirm" else "Rating update"

    if category == "pledge_sast":
        b, a = data.get("pledge_before_pct"), data.get("pledge_after_pct")
        if a is not None:
            enrichment["pledge"] = {"before": b, "after": a}
            facts.append({"k": "Promoter pledge", "v": f"{b if b is not None else '?'}% to {a}% of promoter holding", "src": "filing"})
            if a > 40 or (b is not None and a > b and mv and mv.ret < 0):
                sig.base_tier = "P0"
                sig.base_reason = "Promoter pledge above 40%" if a > 40 else "Pledge rising as the stock falls"
            elif b is not None and a < b:
                sig.base_tier, sig.base_reason = "P2", "Pledge released"
        elif re.search(r"\b(release|revocation)\b", summary_src, re.I):
            sig.base_tier, sig.base_reason = "P2", "Pledge released"

    if category == "concall_doc":
        if re.search(r"transcript", f.subject, re.I):
            sig.base_reason = "Concall transcript filed"
            context.append("FINN re-reads transcripts nightly to update the promise ledger")
        elif re.search(r"schedule|intimation|recording|participation|conclusion", f.subject, re.I):
            sig.base_tier, sig.base_reason = "P3", "Investor meeting schedule"

    tier_guess = sig.base_tier
    line = one_liner(ctx, tier_guess)
    if line and tier_guess in ("P0", "P1", "P2"):
        title = first_sentence(line, 90)
    else:
        title = first_sentence(clean_subject(f.subject, ctx.company.name), 90) or TITLES.get(category, "Filing")
    return EnrichResult(title=title, summary=line, signals=sig, facts=facts, context=context, enrichment=enrichment,
                        impact_line=impact_line(ctx, mv) if tier_guess in ("P0", "P1") else None, verify_ok=True,
                        dedupe_key=f"filing:{f.id}")
