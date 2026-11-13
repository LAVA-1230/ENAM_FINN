"""Indian fiscal-year helpers. FY runs April-March; FY27 = Apr 2026 - Mar 2027.
Q1 = Apr-Jun, Q2 = Jul-Sep, Q3 = Oct-Dec, Q4 = Jan-Mar."""
import re
from datetime import date

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
QUARTER_END_MONTH = {1: 6, 2: 9, 3: 12, 4: 3}


def fy_of(d: date) -> int:
    """Nov 2026 -> 2027 (FY27)."""
    return d.year + 1 if d.month >= 4 else d.year


def quarter_of(d: date) -> tuple[int, int]:
    q = {4: 1, 5: 1, 6: 1, 7: 2, 8: 2, 9: 2, 10: 3, 11: 3, 12: 3, 1: 4, 2: 4, 3: 4}[d.month]
    return q, fy_of(d)


def label(q: int, fy: int) -> str:
    return f"Q{q} FY{fy % 100:02d}"


def quarter_label(d: date) -> str:
    return label(*quarter_of(d))


def parse_label(lbl: str) -> tuple[int, int]:
    m = re.match(r"Q([1-4])\s*FY\s*'?(\d{2,4})", lbl.strip(), re.I)
    if not m:
        raise ValueError(f"bad quarter label: {lbl}")
    fy = int(m.group(2))
    return int(m.group(1)), fy + 2000 if fy < 100 else fy


def prev_quarter(lbl: str) -> str:
    q, fy = parse_label(lbl)
    return label(4, fy - 1) if q == 1 else label(q - 1, fy)


def next_quarter(lbl: str) -> str:
    q, fy = parse_label(lbl)
    return label(1, fy + 1) if q == 4 else label(q + 1, fy)


def year_ago(lbl: str) -> str:
    q, fy = parse_label(lbl)
    return label(q, fy - 1)


def quarter_end(lbl: str) -> date:
    q, fy = parse_label(lbl)
    m = QUARTER_END_MONTH[q]
    y = fy if q == 4 else fy - 1
    return date(y, m, {3: 31, 6: 30, 9: 30, 12: 31}[m])


def _year(s: str) -> int:
    y = int(s)
    return y + 2000 if y < 100 else y


def month_year_to_label(text: str) -> str | None:
    """'Sep 2026' or 'Sep-26' -> 'Q2 FY27' (the quarter containing that month)."""
    m = re.search(r"([A-Za-z]{3})[a-z]*[\s\-]*(\d{2,4})", text)
    if not m or m.group(1).lower() not in MONTHS:
        return None
    return quarter_label(date(_year(m.group(2)), MONTHS[m.group(1).lower()], 1))


def parse_quarter_ended(text: str) -> str | None:
    """'Quarter ended 30.09.2026' / '30-Sep-2026' / 'September 30, 2026' -> 'Q2 FY27'."""
    m = re.search(r"(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})", text)
    if m:
        return quarter_label(date(int(m.group(3)), int(m.group(2)), 1))
    m = re.search(r"(\d{1,2})[\s\-]*([A-Za-z]{3})[a-z]*[\s\-,]*(\d{4})", text)
    if m and m.group(2).lower() in MONTHS:
        return quarter_label(date(int(m.group(3)), MONTHS[m.group(2).lower()], 1))
    m = re.search(r"([A-Za-z]{3})[a-z]*\s+\d{1,2},?\s+(\d{4})", text)
    if m and m.group(1).lower() in MONTHS:
        return quarter_label(date(int(m.group(2)), MONTHS[m.group(1).lower()], 1))
    return None


def fy_label(fy: int) -> str:
    return f"FY{fy % 100:02d}"


def parse_fy(text: str) -> int | None:
    """'FY27' / 'FY2027' / 'FY 26-27' / 'Mar 2026' -> 2027 / 2027 / 2027 / 2026."""
    m = re.search(r"FY\s*'?(\d{2})\s*[-/]\s*(\d{2})\b", text, re.I)
    if m:
        return 2000 + int(m.group(2))
    m = re.search(r"FY\s*'?(\d{2,4})", text, re.I)
    if m:
        return _year(m.group(1))
    m = re.search(r"Mar[a-z]*[\s\-]*(\d{2,4})", text, re.I)
    if m:
        return _year(m.group(1))
    return None


def quarters_of_fy(fy: int) -> list[str]:
    return [label(q, fy) for q in (1, 2, 3, 4)]
