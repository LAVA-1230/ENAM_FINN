"""Token and cost logging, the daily budget stop, and the /admin/usage summary."""
from datetime import datetime, timedelta

from sqlalchemy import func, select

from ..config import get_settings
from ..db import session_scope
from ..models import Company, LlmUsage

# USD per 1M tokens (input, output). Estimates for the cost story; free tiers cost 0 in practice.
PRICES = {
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.0-flash": (0.10, 0.40),
    "llama-3.1-8b-instant": (0.05, 0.08),
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet": (3.00, 15.00),
}


def price_of(model: str) -> tuple[float, float]:
    for k, v in PRICES.items():
        if model.startswith(k):
            return v
    return (0.5, 1.5)


def log(job, prompt_name, model, tin, tout, cached=False):
    pin, pout = price_of(model)
    cost = 0.0 if cached else (tin * pin + tout * pout) / 1e6
    with session_scope() as db:
        db.add(LlmUsage(job=job, prompt_name=prompt_name, model=model, input_tokens=tin,
                        output_tokens=tout, cost_usd=cost, cached=cached))


def spent_today() -> float:
    since = datetime.utcnow() - timedelta(hours=24)
    with session_scope() as db:
        return db.scalar(select(func.coalesce(func.sum(LlmUsage.cost_usd), 0.0))
                         .where(LlmUsage.created_at >= since)) or 0.0


def over_budget() -> bool:
    return spent_today() >= get_settings().llm_daily_budget_usd


def summary() -> dict:
    with session_scope() as db:
        rows = db.execute(select(LlmUsage.prompt_name, LlmUsage.model, func.count(),
                                 func.sum(LlmUsage.input_tokens), func.sum(LlmUsage.output_tokens),
                                 func.sum(LlmUsage.cost_usd))
                          .group_by(LlmUsage.prompt_name, LlmUsage.model)).all()
        cached = dict(db.execute(select(LlmUsage.prompt_name, func.count()).where(LlmUsage.cached.is_(True))
                                 .group_by(LlmUsage.prompt_name)).all())
        n_companies = db.scalar(select(func.count()).select_from(Company)) or 1
        first = db.scalar(select(func.min(LlmUsage.created_at)))
    by_prompt = []
    total_cost = total_calls = total_cached = 0
    for name, model, n, tin, tout, cost in rows:
        c = cached.get(name, 0)
        by_prompt.append({"prompt": name, "model": model, "calls": n, "cached": c,
                          "input_tokens": tin or 0, "output_tokens": tout or 0, "cost_usd": round(cost or 0, 5)})
        total_cost += cost or 0
        total_calls += n
        total_cached += c
    days = max(1.0, (datetime.utcnow() - first).total_seconds() / 86400) if first else 1.0
    return {
        "total_cost_usd": round(total_cost, 4),
        "calls": total_calls,
        "cache_hit_rate": round(total_cached / total_calls, 3) if total_calls else 0,
        "spent_last_24h_usd": round(spent_today(), 4),
        "budget_usd": get_settings().llm_daily_budget_usd,
        "cost_per_day_per_20_companies_usd": round(total_cost / days / n_companies * 20, 4),
        "by_prompt": sorted(by_prompt, key=lambda r: -r["cost_usd"]),
    }
