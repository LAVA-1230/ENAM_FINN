"""Section-aware chunking. Transcripts split by speaker turn (merged to ~1,500-2,500 characters, keeping the
page and speaker); annual reports only on selected pages (MD&A, segments, cash), one chunk per page part."""
import re

SPEAKER_RE = re.compile(r"^\s*((?:Mr\.?|Ms\.?|Mrs\.?|Dr\.?)?\s*[A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+){0,4})\s*:\s*(.*)$")
NOT_SPEAKER = {"Note", "Disclaimer", "Page", "Date", "Time", "Website", "Email", "Source", "Management", "Participants",
               "Moderator Note", "Safe Harbour", "Registered Office", "Tel", "Fax", "CIN", "Ref", "Subject", "Dear Sir"}
TARGET, MAX = 1800, 2800


def transcript_turns(pages: list[str]) -> list[dict]:
    """[{speaker, page, text}] in order."""
    turns, cur = [], None
    for pno, page in enumerate(pages, start=1):
        for line in page.split("\n"):
            m = SPEAKER_RE.match(line)
            if m and is_speaker_name(m.group(1).strip()):
                if cur and cur["text"].strip():
                    turns.append(cur)
                cur = {"speaker": m.group(1).strip(), "page": pno, "page_to": pno, "text": m.group(2).strip()}
            else:
                if cur is None:
                    cur = {"speaker": None, "page": pno, "page_to": pno, "text": ""}
                if re.match(r"^\s*Page \d+ of \d+\s*$", line):
                    continue
                cur["text"] += " " + line.strip()
                cur["page_to"] = pno
    if cur and cur["text"].strip():
        turns.append(cur)
    for t in turns:
        t["text"] = re.sub(r"\s+", " ", t["text"]).strip()
    return turns


def chunk_transcript(pages: list[str]) -> list[dict]:
    out, buf = [], None
    for t in transcript_turns(pages):
        text = f"{t['speaker']}: {t['text']}" if t["speaker"] else t["text"]
        if len(text) > MAX:  # long monologue: split by sentences
            for piece in _split(text, TARGET):
                out.append({"page_from": t["page"], "page_to": t["page_to"], "speaker": t["speaker"], "text": piece})
            continue
        if buf and len(buf["text"]) + len(text) <= TARGET:
            buf["text"] += "\n" + text
            buf["page_to"] = t["page_to"]
            if buf["speaker"] != t["speaker"]:
                buf["speaker"] = buf["speaker"] if buf["speaker"] == "multiple" else "multiple"
        else:
            if buf:
                out.append(buf)
            buf = {"page_from": t["page"], "page_to": t["page_to"], "speaker": t["speaker"], "text": text}
    if buf:
        out.append(buf)
    return out


def _split(text: str, size: int) -> list[str]:
    sents = re.split(r"(?<=[.!?])\s+", text)
    out, cur = [], ""
    for s in sents:
        if len(cur) + len(s) > size and cur:
            out.append(cur.strip())
            cur = ""
        cur += " " + s
    if cur.strip():
        out.append(cur.strip())
    return out


def chunk_pages(pages: list[str], selected: dict[str, list[int]]) -> list[dict]:
    out = []
    for section, nums in selected.items():
        for p in nums:
            if p - 1 >= len(pages):
                continue
            text = re.sub(r"\s+", " ", pages[p - 1]).strip()
            for piece in _split(text, TARGET) if len(text) > MAX else [text]:
                if len(piece) > 80:
                    out.append({"page_from": p, "page_to": p, "section": section, "speaker": None, "text": piece})
    return out


def is_speaker_name(name: str) -> bool:
    """'Sudhanshu Vats' or 'Moderator' yes; cover-letter labels ('Sub', 'CIN', 'MANAGEMENT') no."""
    if name in NOT_SPEAKER or len(name) > 45 or re.search(r"\d", name):
        return False
    if name.lower() == "moderator":
        return True
    words = re.sub(r"^(Mr|Ms|Mrs|Dr)\.?\s+", "", name).split()
    return len(words) >= 2 and not name.isupper()


def management_speakers(pages: list[str], turns: list[dict]) -> set[str]:
    """Everyone who speaks except the moderator and the analysts the moderator introduces
    ('The next question is from the line of Abneesh Roy from Nuvama')."""
    analysts = set()
    for t in turns:
        if (t["speaker"] or "").lower() != "moderator":
            continue
        for nm in re.findall(r"(?:line of|question (?:is )?from|comes from|joined by)\s+(?:Mr\.?\s+|Ms\.?\s+)?"
                             r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})", t["text"]):
            analysts.add(nm.split()[-1].lower())
    names = set()
    for t in turns:
        sp = t["speaker"]
        if sp and sp.lower() != "moderator":
            last = sp.split()[-1].lower()
            if last not in analysts:
                names.add(last)
    return names


def is_management(speaker: str | None, mgmt: set[str]) -> bool:
    return bool(speaker) and speaker.split()[-1].lower() in mgmt
