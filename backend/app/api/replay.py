"""Replay mode (spec 13.5): the snapshot job records the API's own responses for a window into
snapshots/<label>.json; when replay is on (?replay=<label> or the settings toggle), GET requests are served
from that file and carry an X-Finn-Replay header so the UI can show its banner. Live mode is the default."""
import json
import logging
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Company, CompanyResearch, Event

log = logging.getLogger(__name__)
SNAPSHOTS = Path(__file__).resolve().parent.parent.parent / "snapshots"
WINDOWS = ("24h", "3d", "7d", "30d", "since_last_visit")
COMPANY_PARTS = ("", "/promises", "/financials", "/cash", "/story", "/timeline", "/tripwires", "/prep")


def key_of(path: str, params: dict) -> str:
    q = {k: v for k, v in sorted(params.items()) if k not in ("replay", "_")}
    return path + ("?" + urlencode(q) if q else "")


def snapshot_paths(db: Session) -> list[str]:
    paths = [f"/api/brief?window={w}" for w in WINDOWS] + [f"/api/brief/audio-script?window={w}" for w in WINDOWS[:3]]
    paths += ["/api/portfolio", "/api/research/ready", "/api/notifications", "/api/decisions", "/api/ask/suggested"]
    since = datetime.utcnow() - timedelta(days=31)
    paths += [f"/api/events/{i}" for i in db.scalars(select(Event.id).where(Event.event_date >= since))]
    ready = set(db.scalars(select(CompanyResearch.company_id).where(CompanyResearch.status == "ready")))
    for c in db.scalars(select(Company)).all():
        if c.is_holding or c.id in ready:
            paths += [f"/api/companies/{c.symbol}{p}" for p in COMPANY_PARTS]
    return paths


def write_snapshot(db: Session, label: str = "demo") -> dict:
    from fastapi.testclient import TestClient

    from ..main import app
    payload, failed = {}, 0
    with TestClient(app) as client:
        for p in snapshot_paths(db):
            r = client.get(p, headers={"X-Finn-Live": "1"})
            if r.status_code == 200:
                path, _, qs = p.partition("?")
                params = dict(x.split("=", 1) for x in qs.split("&") if x) if qs else {}
                payload[key_of(path, params)] = r.json()
            else:
                failed += 1
    brief = payload.get(key_of("/api/brief", {"window": "7d"}), {})
    meta = {"label": label, "created_at": datetime.utcnow().isoformat() + "Z",
            "window_from": brief.get("window", {}).get("from"), "window_to": brief.get("window", {}).get("to")}
    SNAPSHOTS.mkdir(exist_ok=True)
    (SNAPSHOTS / f"{label}.json").write_text(json.dumps({"meta": meta, "responses": payload}, ensure_ascii=False),
                                             encoding="utf-8")
    load.cache_clear()
    return {"label": label, "responses": len(payload), "failed": failed}


@lru_cache(maxsize=4)
def load(label: str) -> dict | None:
    f = SNAPSHOTS / f"{Path(label).name}.json"
    if not f.exists():
        return None
    return json.loads(f.read_text(encoding="utf-8"))


def available() -> list[str]:
    return sorted(p.stem for p in SNAPSHOTS.glob("*.json")) if SNAPSHOTS.exists() else []


def banner(meta: dict) -> str:
    def d(s: str | None) -> str:
        if not s:
            return "?"
        x = datetime.fromisoformat(s.rstrip("Z"))
        return f"{x.day} {x:%b %Y}"
    return f"Replay: {d(meta.get('window_from'))} to {d(meta.get('window_to'))} data"
