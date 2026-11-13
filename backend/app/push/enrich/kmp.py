"""Management / director / auditor change card (spec 7.4.2).

Who, role, change, stated reason (verbatim), successor, cluster check (other key exits in 365 days),
timing check (days to the next board meeting), and a short bio of the incoming person.
The subject line usually names the person and role, so a regex pass works without any LLM;
the fast model reads the filing for the stated reason and the profile when a key is configured."""
import logging
import re
from datetime import datetime, timedelta

from sqlalchemy import select

from ...llm import client as llm
from ...llm.schemas import BioOut, KmpExtract
from ...models import CalendarItem, Event, Filing
from ...sources import websearch
from ..score import Signals
from .base import Ctx, EnrichResult, day, filing_text, free_one_liner, impact_line, nse_summary, price_reaction

log = logging.getLogger(__name__)

TOP = r"chief executive|\bceo\b|managing director|\bmd\b|chief financial|\bcfo\b|group ceo|global ceo"
KEY = TOP + r"|company secretary|compliance officer|auditor|independent director|chairman|chairperson|whole[- ]?time director"
NAME_RE = re.compile(r"\b(?:Mr|Ms|Mrs|Dr|Shri|Smt)\.?\s+([A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+){0,4})")
ROLE_RE = re.compile(r"\bas\s+(?:the\s+|an?\s+)?(.+?)(?:\s+(?:of|in)\s+the\s+company|\s+w\.?\s?e\.?\s?f\.?|\s+with effect|,|\.(?:\s|$)|;|$)", re.I)


def change_type(text: str) -> str:
    t = text.lower()
    for word, kind in (("resign", "resignation"), ("cessation", "cessation"), ("retire", "retirement"),
                       ("relinquish", "resignation"), ("step down", "resignation"), ("re-appoint", "re-appointment"),
                       ("appoint", "appointment")):
        if word in t:
            return kind
    return "change"


ROLE_WORDS = re.compile(r"\b(Managing|Director|Chief|Chairman|Chairperson|Company|Independent|Non|Executive|Whole|"
                        r"Officer|Secretary|Compliance|Group|Global|Additional|President|Head|Vice|Joint)\b.*$")
ADDRESS_WORDS = re.compile(r"\b(Road|Marg|Nagar|Street|Lane|Chowk|Bhavan|Bhawan|House|Tower|Floor)\b", re.I)


def find_person(text: str) -> tuple[str | None, int]:
    for m in NAME_RE.finditer(text):
        tail = text[m.end():m.end() + 25]
        name = ROLE_WORDS.sub("", m.group(1)).strip()
        name = re.sub(r"\s+(as|and|from|who|w)$", "", name).strip()
        if not name or ADDRESS_WORDS.search(m.group(1) + " " + tail):
            continue
        return name, m.end()
    return None, 0


def regex_extract(subject: str, body: str, auditor: bool = False) -> dict:
    person, end = (None, 0) if auditor else find_person(subject)
    src = subject
    if not person and not auditor:
        person, end = find_person(body[:2500])
        src = body[:2500]
    role = None
    rm = ROLE_RE.search(src[end:]) if person else None
    if rm:
        role = rm.group(1).strip()[:80]
    if not role:
        km = re.search(KEY, subject + " " + body[:1500], re.I)
        role = km.group(0).title() if km else None
    reason = None
    rr = re.search(r"(?:due to|owing to|on account of|reason[s]? (?:for (?:the )?resignation )?(?:is|being|:))\s+([^.\n]{3,140})", body, re.I)
    if rr:
        reason = rr.group(1).strip()
    profile = None
    pm = re.search(r"(brief profile|profile of|brief resume|details of .*appointment)[^\n]*\n(.{80,700}?)(?:\n\n|$)", body, re.I | re.S)
    if pm:
        profile = re.sub(r"\s+", " ", pm.group(2)).strip()[:600]
    return {"person": person, "role": role, "change": change_type(subject + " " + body[:400]),
            "reason_stated": reason, "successor": None, "profile_text": profile, "effective_date": None}


def sibling_successor(ctx: Ctx, role: str | None) -> dict | None:
    """A same-day appointment filing for the same role names the successor (companies file them separately)."""
    if not role:
        return None
    short = role_short(role)
    day0 = datetime.combine(ctx.filing.published_at.date(), datetime.min.time())
    for f in ctx.db.scalars(select(Filing).where(Filing.company_id == ctx.company.id, Filing.id != ctx.filing.id,
                                                 Filing.published_at >= day0, Filing.published_at < day0 + timedelta(days=1))):
        if change_type(f.subject) != "appointment":
            continue
        person, end = find_person(f.subject)
        rm = ROLE_RE.search(f.subject[end:]) if person else None
        if person and rm and role_short(rm.group(1)) == short:
            return {"name": person, "role": rm.group(1).strip()[:80], "interim": "interim" in f.subject.lower()}
    return None


def is_key(role: str | None) -> bool:
    return bool(role and re.search(KEY, role, re.I))


def tier_for(role: str | None, change: str, has_successor: bool, subject: str) -> tuple[str, str, bool]:
    """(tier, reason, locked)"""
    r = (role or subject).lower()
    if "auditor" in r and change in ("resignation", "cessation"):
        return "P0", "Statutory auditor resigned", True
    if "auditor" in r:
        return "P1", "Statutory auditor change", False
    top = bool(re.search(TOP, r))
    short = role_short(role or subject)
    if top and change in ("resignation", "cessation"):
        return "P0", f"{short} exit", False
    if top and change == "retirement":
        return ("P1", f"{short} retiring, successor named", False) if has_successor else ("P0", f"{short} retiring", False)
    if top and change in ("appointment", "re-appointment", "change"):
        return ("P2" if change == "re-appointment" else "P1"), f"New {short}" if change == "appointment" else f"{short} change", False
    if re.search(r"chairman|chairperson", r):
        return "P1", f"Chair {change}", False
    if re.search(r"company secretary|compliance officer|independent director|whole[- ]?time director", r):
        return "P2", f"{short} {change}", False
    return "P3", f"Board change: {short.lower()}", False


def role_short(role: str) -> str:
    r = role.lower()
    for pat, s in ((r"chief financial|\bcfo\b", "CFO"), (r"chief executive|\bceo\b", "CEO"),
                   (r"managing director|\bmd\b", "MD"), (r"company secretary", "Company Secretary"),
                   (r"compliance officer", "Compliance officer"), (r"independent director", "Independent director"),
                   (r"whole[- ]?time director", "Whole-time director"), (r"chairman|chairperson", "Chair"),
                   (r"auditor", "Auditor")):
        if re.search(pat, r):
            return s
    return role.strip().capitalize()[:40]


def cluster_check(ctx: Ctx) -> dict | None:
    since = ctx.filing.published_at - timedelta(days=365)
    prior = ctx.db.scalars(select(Event).where(Event.company_id == ctx.company.id, Event.category.in_(["kmp_change", "auditor_change"]),
                                               Event.event_date >= since, Event.event_date < ctx.filing.published_at - timedelta(hours=1))
                           .order_by(Event.event_date.desc())).all()
    exits = [e for e in prior if (e.enrichment or {}).get("change") in ("resignation", "cessation")
             and (e.enrichment or {}).get("key_role")]
    if not exits:
        return None
    last = exits[0]
    months = max(1, round((ctx.filing.published_at - last.event_date).days / 30))
    n = len(exits) + 1
    ordinal = {2: "2nd", 3: "3rd"}.get(n, f"{n}th")
    return {"label": f"{ordinal} key exit in {months} month{'s' if months != 1 else ''}",
            "line": f"{(last.enrichment or {}).get('role_short') or 'A key person'} left on {day(last.event_date.date())}",
            "event_id": last.id, "items": [{"date": e.event_date.date().isoformat(), "title": e.title, "id": e.id} for e in exits]}


def timing_check(ctx: Ctx) -> str | None:
    d0 = ctx.filing.published_at.date()
    nxt = ctx.db.scalar(select(CalendarItem).where(CalendarItem.company_id == ctx.company.id, CalendarItem.date > d0,
                                                   CalendarItem.date <= d0 + timedelta(days=45))
                        .order_by(CalendarItem.date).limit(1))
    if not nxt:
        return None
    n = (nxt.date - d0).days
    what = "results" if "result" in nxt.purpose.lower() else "board meeting"
    return f"Comes {n} day{'s' if n != 1 else ''} before the {what} on {day(nxt.date)}"


def bio(ctx: Ctx, name: str | None, role: str | None, profile_text: str | None) -> dict | None:
    if not name:
        return None
    sources, lines = [], []
    if profile_text:
        sources.append({"id": "filing", "label": "Appointment filing", "url": ctx.filing.attachment_url, "text": profile_text})
    hits = websearch.search(f"\"{name}\" {ctx.company.name} {role or ''}".strip())
    for i, h in enumerate(hits[:3]):
        sources.append({"id": f"web{i + 1}", "label": h["title"], "url": h["url"], "text": h["snippet"]})
    if not sources:
        return {"name": name, "role": role, "lines": [], "sources": [],
                "note": "No public profile found in the filing. LinkedIn-style background needs a web-search key."}
    if llm.available():
        try:
            out = llm.complete("bio_summarise", "fast", {
                "name": name, "role": role or "", "company": ctx.company.name,
                "sources": "\n\n".join(f"[{s['id']}] {s['label']}\n{s['text']}" for s in sources)},
                schema=BioOut, job="enrich_kmp")
            lines = [{"text": ln["text"], "source": ln.get("source")} for ln in out["lines"][:3]]
        except Exception as e:  # noqa: BLE001
            log.info("bio llm failed: %s", e)
    if not lines and profile_text:
        # verbatim from the filing: split the profile into up to three sentences
        sents = re.split(r"(?<=[.;])\s+", profile_text)
        lines = [{"text": s.strip()[:160], "source": "filing", "verbatim": True} for s in sents[:3] if len(s.strip()) > 20]
    return {"name": name, "role": role, "lines": lines,
            "sources": [{"id": s["id"], "label": s["label"], "url": s["url"]} for s in sources]}


def enrich(ctx: Ctx) -> EnrichResult:
    f = ctx.filing
    body = filing_text(f, max_pages=3)
    data = None
    if llm.available() and body:
        try:
            data = llm.complete("kmp_extract", "fast", {"subject": f.subject, "text": body[:20000]},
                                schema=KmpExtract, job="enrich_kmp")
        except Exception as e:  # noqa: BLE001
            log.info("kmp llm failed: %s", e)
    is_auditor = f.exchange_category.lower().startswith("change in auditor") or bool(
        re.search(r"statutory auditor|resignation of (the )?auditor", f.subject, re.I))
    rx = regex_extract(f.subject + " " + (nse_summary(f) or ""), body, auditor=is_auditor)
    if not data or not data.get("person"):
        data = rx
    else:
        data["change"] = (data.get("change") or rx["change"] or "change").lower()
    person, role, change = data.get("person"), data.get("role"), data.get("change") or "change"
    succ = data.get("successor") or None
    if is_auditor:
        role = "Statutory auditor"
    if change in ("retirement", "resignation", "cessation") and not (succ and succ.get("name")):
        succ = sibling_successor(ctx, role)
    subject_for_role = f"{f.exchange_category} {f.subject} {nse_summary(f) or ''}"
    tier, reason, locked = tier_for(role, change, bool(succ and succ.get("name")), subject_for_role)
    key_role = is_key(role) or is_key(subject_for_role)

    reaction, mv = price_reaction(ctx)
    sig = Signals(base_tier=tier, base_reason=reason, locked=locked, weight_pct=ctx.weight_pct, price_confirms=reaction)
    context, enrichment = [], {"person": person, "role": role, "role_short": role_short(role or "Director"),
                               "change": change, "key_role": key_role, "effective_date": data.get("effective_date"),
                               "successor": succ, "tenure": data.get("tenure_text")}
    if change in ("resignation", "cessation") and key_role:
        cl = cluster_check(ctx)
        if cl:
            sig.cluster = cl["label"]
            context.append(cl["line"])
            enrichment["cluster"] = cl
            if tier in ("P2", "P3"):
                sig.base_tier = "P1"
    t = timing_check(ctx)
    if t:
        context.append(t)

    facts = []
    if data.get("reason_stated"):
        facts.append({"k": "Reason stated", "v": data["reason_stated"], "src": "filing", "quote": True})
    if data.get("effective_date"):
        facts.append({"k": "Effective", "v": data["effective_date"], "src": "filing"})
    if succ and succ.get("name"):
        facts.append({"k": "Successor", "v": f"{succ['name']}{', ' + succ['role'] if succ.get('role') else ''}"
                      f"{' (interim)' if succ.get('interim') else ''}", "src": "filing"})
    if data.get("tenure_text"):
        facts.append({"k": "Tenure", "v": data["tenure_text"], "src": "filing"})

    incoming = None
    if change in ("appointment", "re-appointment"):
        incoming = (person, role, data.get("profile_text"))
    elif succ and succ.get("name"):
        incoming = (succ["name"], succ.get("role") or role, data.get("profile_text"))
    if incoming and tier in ("P0", "P1", "P2"):
        enrichment["bio"] = bio(ctx, *incoming)

    who = person or "A director"
    verb = {"resignation": "resigns", "cessation": "ceases", "retirement": "retires", "appointment": "appointed",
            "re-appointment": "re-appointed"}.get(change, "changes")
    short = role_short(role or "director")
    title = f"{short} {who} {verb}" if change != "appointment" else f"{who} appointed {short}"
    if is_auditor and not person:
        title = "Statutory auditor change"
    if sig.cluster:
        title += f", {sig.cluster}"
    return EnrichResult(title=title[:120], summary=free_one_liner(f, ctx.company.name), signals=sig, facts=facts,
                        context=context, enrichment=enrichment, impact_line=impact_line(ctx, mv),
                        metric_line=None, verify_ok=True, dedupe_key=f"kmp:{ctx.company.id}:{enrichment['role_short']}:{f.published_at.date()}:{(person or f.subject).split()[0]}")
