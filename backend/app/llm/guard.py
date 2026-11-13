"""Guardrails on generated text (spec 10.5).

- citation check: every sentence must end with [n] markers that exist in the provided sources;
- number check: every number in a sentence must appear in a cited source (after normalising);
- banned-phrase filter for the copy rules."""
import re

NOT_FOUND = "Not found in this company's filings and transcripts."
BANNED = ["significant", "significantly", "notably", "robust", "it is worth noting", "this announcement",
          "overall", "in conclusion", "game-changer", "game changer", "stellar", "seamless", "leverage",
          "empower", "unlock"]
CITE_RE = re.compile(r"\[(\d+)\]")
NUM_RE = re.compile(r"(?<![\w.])[-−]?\d[\d,]*(?:\.\d+)?")


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text.strip())
    # split after ". " / "! " / "? " or after citation groups "[1][2] "; keep the markers with the sentence
    parts = re.split(r"(?<=[.!?\]])\s+(?=[A-Z₹(\"'])", text)
    return [p.strip() for p in parts if p.strip()]


def normalise_number(s: str) -> float | None:
    s = s.replace(",", "").replace("−", "-")
    try:
        return float(s)
    except ValueError:
        return None


def numbers_in(text: str) -> list[float]:
    out = []
    for m in NUM_RE.finditer(CITE_RE.sub(" ", text)):
        v = normalise_number(m.group(0))
        if v is not None:
            out.append(abs(v))
    return out


def number_supported(v: float, source_numbers: set[float]) -> bool:
    if v in source_numbers:
        return True
    # tolerate rounding: 21.84 -> 21.8, 1,234.5 -> 1,235, and crore/lakh unit shifts are out of scope
    return any(abs(v - s) <= max(0.051, abs(s) * 0.005) for s in source_numbers)


def check_cited(text: str, sources: dict[int, str], extra_numbers: set[float] | None = None) -> dict:
    """Keep only sentences with at least one valid citation and only supported numbers.
    sources: {citation_id: source_text}. Returns {text, kept, dropped, used_ids}."""
    kept, dropped, used = [], [], set()
    extra = extra_numbers or set()
    for sent in split_sentences(text):
        ids = [int(x) for x in CITE_RE.findall(sent)]
        valid = [i for i in ids if i in sources]
        if not valid:
            dropped.append({"sentence": sent, "why": "no valid citation"})
            continue
        src_nums = set(extra)
        for i in valid:
            src_nums.update(numbers_in(sources[i]))
        bad = [n for n in numbers_in(sent) if not number_supported(n, src_nums) and not _is_trivial(n)]
        if bad:
            dropped.append({"sentence": sent, "why": f"number not in source: {bad[0]:g}"})
            continue
        kept.append(sent)
        used.update(valid)
    return {"text": " ".join(kept), "kept": len(kept), "dropped": dropped, "used_ids": sorted(used)}


def _is_trivial(n: float) -> bool:
    # citation-like small integers and years in references are not claims
    return n in (1, 2, 3, 4) or 1990 <= n <= 2035


def has_banned(text: str) -> str | None:
    low = text.lower()
    for b in BANNED:
        if re.search(rf"\b{re.escape(b)}\b", low):
            return b
    return None


def scrub_banned(text: str) -> str:
    """Last-resort cleanup when a regenerate still hits the filter."""
    for b in BANNED:
        text = re.sub(rf"\b{re.escape(b)}\b\s*,?\s*", "", text, flags=re.I)
    return re.sub(r"\s{2,}", " ", text).strip()
