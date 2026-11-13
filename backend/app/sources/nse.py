"""NSE corporate announcements and board-meeting calendar.

Field names verified on live responses (12 Nov 2026):
  an_dt "12-Nov-2026 18:45:52" (IST), desc (NSE category), attchmntText (subject),
  attchmntFile (PDF), seq_id, sm_name, sm_isin, smIndustry, voiceSummary (NSE's own summary).
All mapping to our model happens in normalise()."""
import hashlib
import logging
from datetime import date, datetime, timedelta, timezone

from .. import http

log = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))
BASE = "https://www.nseindia.com"
HEADERS = {"Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
           "Accept": "application/json, text/plain, */*"}
_warmed = False


def _warm():
    """NSE sometimes wants its cookies first. The home page may 403 from some IPs; that's fine."""
    global _warmed
    if _warmed:
        return
    try:
        http.client().get(BASE + "/", headers={"Accept": "text/html"})
    except Exception:  # noqa: BLE001
        pass
    _warmed = True


def _api(path: str, params: dict) -> list | dict:
    _warm()
    try:
        return http.get(BASE + path, params=params, headers=HEADERS, min_gap=1.0).json()
    except Exception:
        global _warmed
        _warmed = False  # refresh the session once, then give up
        _warm()
        return http.get(BASE + path, params=params, headers=HEADERS, min_gap=1.0).json()


def parse_ist(s: str) -> datetime:
    """'12-Nov-2026 18:45:52' (IST) -> naive UTC."""
    for f in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%d-%b-%Y"):
        try:
            return datetime.strptime(s.strip(), f).replace(tzinfo=IST).astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            continue
    raise ValueError(s)


def fetch_announcements(symbol: str, frm: date, to: date) -> list[dict]:
    data = _api("/api/corporate-announcements", {
        "index": "equities", "symbol": symbol,
        "from_date": frm.strftime("%d-%m-%Y"), "to_date": to.strftime("%d-%m-%Y")})
    return data if isinstance(data, list) else data.get("data", [])


def normalise(a: dict) -> dict:
    published = parse_ist(a.get("an_dt") or a.get("sort_date"))
    url = a.get("attchmntFile") or None
    subject = (a.get("attchmntText") or "").strip()
    key = f"{a.get('symbol')}|{url or subject}|{published.date().isoformat()}"
    return {
        "symbol": a.get("symbol"),
        "exchange": "NSE",
        "exchange_category": (a.get("desc") or "").strip(),
        "subject": subject,
        "attachment_url": url,
        "published_at": published,
        "content_hash": hashlib.sha1(key.encode()).hexdigest(),
        "raw": {k: a.get(k) for k in ("seq_id", "desc", "attchmntText", "an_dt", "sm_name", "sm_isin",
                                      "smIndustry", "voiceSummary", "attFileSize")},
    }


def fetch_calendar() -> list[dict]:
    """Upcoming board meetings across all NSE companies: [{symbol, purpose, desc, date}]."""
    data = _api("/api/event-calendar", {"index": "equities"})
    rows = data if isinstance(data, list) else data.get("data", [])
    out = []
    for r in rows:
        try:
            d = datetime.strptime(r["date"], "%d-%b-%Y").date()
        except (KeyError, ValueError):
            continue
        out.append({"symbol": r.get("symbol"), "purpose": r.get("purpose") or "",
                    "desc": r.get("bm_desc") or "", "date": d})
    return out


def fetch_board_meetings(symbol: str) -> list[dict]:
    rows = _api("/api/corporate-board-meetings", {"index": "equities", "symbol": symbol})
    rows = rows if isinstance(rows, list) else rows.get("data", [])
    out = []
    for r in rows:
        try:
            d = datetime.strptime(r["bm_date"], "%d-%b-%Y").date()
        except (KeyError, ValueError):
            continue
        out.append({"symbol": symbol, "purpose": r.get("bm_purpose") or "", "desc": r.get("bm_desc") or "", "date": d})
    return out
