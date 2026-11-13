"""Audio brief script (spec 9.4): 60-120 seconds, built by template from the brief. The phone reads it
with speechSynthesis, so there is no server audio and no cost. Each part carries the item id it is about,
so the UI can highlight the item being read."""
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def _spoken_pct(x: float) -> str:
    return f"{abs(x):.1f} percent"


def _spoken_rupees(x: float) -> str:
    a = abs(x)
    if a >= 1e7:
        return f"{a / 1e7:.2f} crore rupees"
    if a >= 1e5:
        return f"{a / 1e5:.1f} lakh rupees"
    if a >= 1e3:
        return f"{a / 1e3:.0f} thousand rupees"
    return f"{a:.0f} rupees"


def script(brief: dict) -> dict:
    hour = datetime.now(IST).hour
    greeting = "Good morning." if hour < 12 else "Good afternoon." if hour < 17 else "Good evening."
    parts = [{"id": None, "text": greeting}]
    h = brief.get("header")
    if h:
        verb = "rose" if h["ret"] >= 0 else "fell"
        line = f"Your portfolio {verb} {_spoken_pct(h['ret'])}, {_spoken_rupees(h['rs'])}."
        parts.append({"id": None, "text": line + " " + h["sentence"].replace("%", " percent")})
    att = brief.get("attention", [])
    n = len(att)
    if n == 0:
        parts.append({"id": None, "text": "Nothing needs you today."})
    else:
        parts.append({"id": None, "text": f"{'One item needs' if n == 1 else f'{n} items need'} you."})
        ordinals = ["First", "Second", "Third", "Fourth", "Fifth"]
        for i, e in enumerate(att[:5]):
            what = e["title"].replace("%", " percent").replace("−", "minus ")
            urgent = "Urgent. " if e["tier"] == "P0" else ""
            parts.append({"id": e["id"], "text": f"{ordinals[i]}: {urgent}{e['company'] or 'Your portfolio'}. {what}."})
        if n > 5:
            parts.append({"id": None, "text": f"And {n - 5} more in the app."})
    fyi, routine = len(brief.get("good_to_know", [])), brief.get("routine", {}).get("count", 0)
    if fyi or routine:
        parts.append({"id": None, "text": f"{fyi} smaller updates are in the brief, and {routine} routine filings are hidden."})
    cu = brief.get("coming_up", [])[:3]
    if cu:
        items = ", ".join(f"{c['label']} on {datetime.fromisoformat(c['date']).strftime('%A %d %B').replace(' 0', ' ')}" for c in cu)
        parts.append({"id": None, "text": f"Coming up: {items}."})
    text = " ".join(p["text"] for p in parts)
    return {"text": text, "parts": parts, "words": len(text.split()), "seconds": round(len(text.split()) / 2.5)}
