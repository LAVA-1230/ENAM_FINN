"""screener.in: financial tables + document links (annual reports, concall transcripts).

Layout verified 12 Nov 2026: <section id="quarters|profit-loss|balance-sheet|cash-flow|ratios|documents">,
tables with a thead of period labels ("Sep 2026", "Mar 2026", "TTM") and tbody rows whose first cell is
the row name. Cash and capex come from the schedules API (/api/company/<id>/schedules/).
Numbers are in Rs crore. Cached 24h: it is a small site."""
import logging
import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from .. import fiscal, http

log = logging.getLogger(__name__)
BASE = "https://www.screener.in"


class NotFound(Exception):
    pass


def _num(s: str) -> float | None:
    s = (s or "").replace(",", "").replace("%", "").replace("+", "").strip()
    if s in ("", "-", "--"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _table(soup, section_id: str) -> tuple[list[str], dict[str, list[float | None]]]:
    t = soup.select_one(f"section#{section_id} table.data-table") or soup.select_one(f"section#{section_id} table")
    if not t:
        return [], {}
    heads = [th.get_text(strip=True) for th in t.select("thead th")][1:]
    rows = {}
    for tr in t.select("tbody tr"):
        tds = tr.select("td")
        if not tds:
            continue
        name = re.sub(r"\s*\+$", "", tds[0].get_text(" ", strip=True)).strip()
        name = name.split("Share of operating")[0].strip()
        rows[name] = [_num(td.get_text(strip=True)) for td in tds[1:]]
    return heads, rows


def fetch_page(symbol: str) -> tuple[str, str]:
    """Returns (html, basis). Consolidated first; standalone if consolidated has no quarters."""
    sym = symbol.upper().replace("&", "%26")
    for basis, path in (("consolidated", f"/company/{sym}/consolidated/"), ("standalone", f"/company/{sym}/")):
        try:
            html = http.get_cached_text(BASE + path, max_age_h=24, kind="screener", min_gap=1.5)
        except Exception as e:  # noqa: BLE001
            if getattr(getattr(e, "response", None), "status_code", None) == 404:
                raise NotFound(symbol) from e
            raise
        soup = BeautifulSoup(html, "lxml")
        heads, rows = _table(soup, "quarters")
        if heads and any(v is not None for v in rows.get("Sales", rows.get("Revenue", []))):
            return html, basis
    raise NotFound(symbol)


def _schedule(company_id: str, parent: str, section: str, consolidated: bool, referer: str) -> dict:
    try:
        return http.get_cached_json(f"{BASE}/api/company/{company_id}/schedules/",
                                    params={"parent": parent, "section": section,
                                            "consolidated": "true" if consolidated else ""},
                                    max_age_h=24, kind="screener", headers={"Referer": referer}, min_gap=1.5)
    except Exception as e:  # noqa: BLE001
        log.info("schedule %s/%s failed: %s", parent, section, e)
        return {}


def parse(symbol: str) -> dict:
    html, basis = fetch_page(symbol)
    soup = BeautifulSoup(html, "lxml")
    name = soup.select_one("h1").get_text(strip=True) if soup.select_one("h1") else symbol
    m = re.search(r'data-company-id="(\d+)"', html)
    company_id = m.group(1) if m else None
    bse = None
    a = soup.select_one("a[href*='bseindia.com/stock-share-price']")
    if a:
        mm = re.search(r"/(\d{6})/?$", a["href"])
        bse = mm.group(1) if mm else None
    sector_links = [x.get_text(strip=True) for x in soup.select("section#peers a[href^='/market/']")]
    about = soup.select_one(".about")
    about_text = re.sub(r"\[\d+\]", "", about.get_text(" ", strip=True)).strip() if about else None

    quarters = _parse_quarters(soup)
    years = _parse_years(soup, company_id, basis == "consolidated",
                         BASE + f"/company/{symbol.upper()}/" + ("consolidated/" if basis == "consolidated" else ""))
    docs = _parse_documents(soup)
    return {"symbol": symbol.upper(), "name": name, "bse_code": bse, "basis": basis,
            "sector_path": sector_links[:4], "about": about_text, "quarters": quarters,
            "years": years, "documents": docs,
            "url": BASE + f"/company/{symbol.upper()}/" + ("consolidated/" if basis == "consolidated" else "")}


def _row(rows: dict, *names):
    for n in names:
        if n in rows:
            return rows[n]
    return []


def _parse_quarters(soup) -> list[dict]:
    heads, rows = _table(soup, "quarters")
    out = []
    is_bank = "Revenue" in rows and "Financing Profit" in rows
    for i, h in enumerate(heads):
        lbl = fiscal.month_year_to_label(h)
        if not lbl:
            continue

        def v(*names):
            r = _row(rows, *names)
            return r[i] if i < len(r) else None

        rev = v("Sales", "Revenue")
        exp = v("Expenses")
        op = v("Operating Profit", "Financing Profit")
        pbt, taxp, pat = v("Profit before tax"), v("Tax %"), v("Net Profit")
        out.append({
            "fiscal_label": lbl, "period_end": fiscal.quarter_end(lbl), "revenue": rev, "expenses": exp,
            "ebitda": op, "opm": v("OPM %", "Financing Margin %"), "other_income": v("Other Income"),
            "interest": v("Interest"), "depreciation": v("Depreciation"), "pbt": pbt,
            "tax": round(pbt * taxp / 100, 2) if pbt is not None and taxp is not None else None,
            "pat": pat, "is_bank": is_bank,
        })
    return out


def _parse_years(soup, company_id, consolidated, referer) -> list[dict]:
    ph, pl = _table(soup, "profit-loss")
    bh, bs = _table(soup, "balance-sheet")
    ch, cf = _table(soup, "cash-flow")
    rh, ra = _table(soup, "ratios")
    other_assets = _schedule(company_id, "Other Assets", "balance-sheet", consolidated, referer) if company_id else {}
    investing = _schedule(company_id, "Cash from Investing Activity", "cash-flow", consolidated, referer) if company_id else {}

    def col(heads, rows, h, *names):
        if h not in heads:
            return None
        i = heads.index(h)
        r = _row(rows, *names)
        return r[i] if i < len(r) else None

    def sched(d, key, h):
        return _num((d.get(key) or {}).get(h, "")) if isinstance(d.get(key), dict) else None

    out = []
    for h in ph:
        if not h.startswith("Mar"):
            continue  # skip TTM; FY ends in March
        fy = fiscal.parse_fy(h)
        cash = sched(other_assets, "Cash Equivalents", h)
        capex = sched(investing, "Fixed assets purchased", h)
        eq, res = col(bh, bs, h, "Equity Capital"), col(bh, bs, h, "Reserves")
        out.append({
            "fy": fiscal.fy_label(fy),
            "revenue": col(ph, pl, h, "Sales", "Revenue"),
            "ebitda": col(ph, pl, h, "Operating Profit", "Financing Profit"),
            "opm": col(ph, pl, h, "OPM %", "Financing Margin %"),
            "pat": col(ph, pl, h, "Net Profit"),
            "cfo": col(ch, cf, h, "Cash from Operating Activity"),
            "fcf": col(ch, cf, h, "Free Cash Flow"),
            "capex": abs(capex) if capex is not None else None,
            "total_debt": col(bh, bs, h, "Borrowings", "Borrowing"),
            "cash": cash,
            "net_worth": (eq or 0) + (res or 0) if eq is not None or res is not None else None,
            "fixed_assets": col(bh, bs, h, "Fixed Assets"),
            "receivable_days": col(rh, ra, h, "Debtor Days"),
            "inventory_days": col(rh, ra, h, "Inventory Days"),
            "wc_days": col(rh, ra, h, "Working Capital Days"),
            "roce": col(rh, ra, h, "ROCE %"),
        })
    return out


MONTH_RE = re.compile(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})")


def _parse_documents(soup) -> dict:
    docs = {"annual_reports": [], "transcripts": [], "presentations": []}
    sec = soup.select_one("section#documents")
    if not sec:
        return docs
    for li in sec.select(".annual-reports li"):
        a = li.select_one("a")
        if not a:
            continue
        m = re.search(r"(\d{4})", a.get_text(" ", strip=True))
        if m:
            docs["annual_reports"].append({"fy": f"FY{int(m.group(1)) % 100:02d}", "url": a["href"],
                                           "title": a.get_text(" ", strip=True)})
    for li in sec.select(".concalls li"):
        txt = li.get_text(" ", strip=True)
        m = MONTH_RE.search(txt)
        if not m:
            continue
        d = datetime.strptime(f"{m.group(1)} {m.group(2)}", "%b %Y").date()
        for a in li.select("a"):
            kind = a.get_text(strip=True).lower()
            if kind == "transcript":
                docs["transcripts"].append({"date": d, "url": a["href"], "period_label": call_period(d)})
            elif kind == "ppt":
                docs["presentations"].append({"date": d, "url": a["href"], "period_label": call_period(d)})
    return docs


def call_period(call_month: date) -> str:
    """A results call in Nov 2026 discusses Q2 FY27 (the quarter that just ended).
    Calls held in the first month after a quarter-end, or the second, both map to that quarter."""
    m, y = call_month.month, call_month.year
    # quarter-end months: 3, 6, 9, 12. Find the latest quarter-end strictly before this month.
    qe_month = ((m - 1) // 3) * 3
    if qe_month == 0:
        qe_month, y = 12, y - 1
    return fiscal.quarter_label(date(y, qe_month, 1))
