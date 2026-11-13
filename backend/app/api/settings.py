from types import SimpleNamespace

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import portfolio
from ..models import Event, PriceDaily
from ..push import price_signals
from ..push.ingest import get_settings_row
from ..push.score import CATEGORY_LABEL, DEFAULT_TIER
from .common import DB, iso

router = APIRouter(tags=["settings"])
FIELDS = ("price_pct", "volume_x", "impact_pct", "push_p0_only", "show_routine", "quiet_start", "quiet_end",
          "p0_in_quiet", "brief_times", "replay")
EDITABLE_CATEGORIES = ["auditor_change", "default", "kmp_change", "results", "rating", "pledge_sast", "insider", "mna",
                       "fundraise", "buyback", "order_win", "capex", "litigation", "concall_doc", "dividend_corp",
                       "board_meeting", "routine", "other", "price_move", "volume_spike", "sector_move", "tripwire"]
TRIPWIRE_DEFAULTS = {"key_exits": "Another key person exits within 12 months", "weight": "Position weight above 10%",
                     "drawdown": "Drawdown from your average cost above 25%", "wc_days": "Working-capital days 10 above last year"}


def _sessions(db: Session, n: int) -> list:
    return sorted(db.scalars(select(PriceDaily.date).where(PriceDaily.key == portfolio.NIFTY)
                             .order_by(PriceDaily.date.desc()).limit(n)).all())


def preview_count(db: Session, price_pct: float, volume_x: float, impact_pct: float, sessions: int = 5) -> dict:
    """How many price/volume alerts the last week would have produced with these thresholds."""
    s = SimpleNamespace(price_pct=price_pct, volume_x=volume_x, impact_pct=impact_pct, tier_overrides={})
    items = [it for d in _sessions(db, sessions) for it in price_signals.evaluate(db, s, d)]
    return {"alerts": len(items), "price": sum(1 for i in items if i["kind"] == "price"),
            "volume": sum(1 for i in items if i["kind"] == "volume"), "sessions": sessions}


def payload(db: Session, with_preview: bool = True) -> dict:
    s = get_settings_row(db)
    out = {k: getattr(s, k) for k in FIELDS}
    out["last_brief_seen_at"] = iso(s.last_brief_seen_at)
    out["tier_overrides"] = s.tier_overrides or {}
    out["tripwire_defaults"] = {k: (s.tripwire_defaults or {}).get(k, True) for k in TRIPWIRE_DEFAULTS}
    out["tripwire_labels"] = TRIPWIRE_DEFAULTS
    out["categories"] = [{"key": c, "label": CATEGORY_LABEL.get(c, c), "default": DEFAULT_TIER.get(c, "P2"),
                          "tier": (s.tier_overrides or {}).get(c) or DEFAULT_TIER.get(c, "P2")} for c in EDITABLE_CATEGORIES]
    if with_preview:  # the costly part (re-evaluates a week of price signals); skipped when thresholds did not move
        out["preview"] = preview_count(db, s.price_pct, s.volume_x, s.impact_pct)
    return out


@router.get("/settings")
def get_settings_(db: Session = DB):
    return payload(db)


@router.get("/settings/preview")
def preview(price_pct: float, volume_x: float, impact_pct: float, db: Session = DB):
    return preview_count(db, price_pct, volume_x, impact_pct)


class SettingsIn(BaseModel):
    price_pct: float | None = None
    volume_x: float | None = None
    impact_pct: float | None = None
    push_p0_only: bool | None = None
    show_routine: bool | None = None
    quiet_start: str | None = None
    quiet_end: str | None = None
    p0_in_quiet: bool | None = None
    brief_times: list[str] | None = None
    replay: bool | None = None
    tier_overrides: dict[str, str | None] | None = None
    tripwire_defaults: dict[str, bool] | None = None


@router.put("/settings")
def put_settings(body: SettingsIn, db: Session = DB):
    s = get_settings_row(db)
    thresholds_before = (s.price_pct, s.volume_x, s.impact_pct)
    for k in FIELDS:
        v = getattr(body, k)
        if v is not None:
            setattr(s, k, v)
    if not (0.5 <= s.price_pct <= 20 and 1 <= s.volume_x <= 10 and 0.05 <= s.impact_pct <= 5):
        raise HTTPException(422, "Price move 0.5–20%, volume 1–10x, portfolio impact 0.05–5%")
    if body.tripwire_defaults is not None:
        s.tripwire_defaults = {**(s.tripwire_defaults or {}), **body.tripwire_defaults}
    if body.tier_overrides is not None:
        new = {k: v for k, v in {**(s.tier_overrides or {}), **body.tier_overrides}.items()
               if v in ("P0", "P1", "P2", "P3") and v != DEFAULT_TIER.get(k)}
        _apply_overrides(db, s.tier_overrides or {}, new)
        s.tier_overrides = new
    db.commit()
    if (s.price_pct, s.volume_x, s.impact_pct) != thresholds_before:
        # thresholds changed: rebuild price/volume alerts so the brief reflects them at once
        sessions = _sessions(db, 25)
        price_signals.clear_stale(db, s, sessions)
        for d in sessions:
            price_signals.store(db, s, price_signals.evaluate(db, s, d))
        db.commit()
        return payload(db)
    return payload(db, with_preview=False)


def _apply_overrides(db: Session, old: dict, new: dict):
    """The user's tier wins over the computed one. The computed tier is kept so removing the override restores it."""
    for cat in set(old) | set(new):
        if old.get(cat) == new.get(cat):
            continue
        for ev in db.scalars(select(Event).where(Event.category == cat)).all():
            enr = dict(ev.enrichment or {})
            base = enr.get("_computed_tier") or ev.tier
            if new.get(cat):
                enr["_computed_tier"] = base
                ev.tier = new[cat]
            else:
                ev.tier = base
                enr.pop("_computed_tier", None)
            ev.enrichment = enr
