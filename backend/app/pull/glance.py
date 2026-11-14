"""Three more research views from the challenge brief's menu, all computed in Python from screener.in's tables
(compiled from the company's own filings): the financial snapshot, the multi-year trajectory and the balance sheet.

Read-only and additive: nothing here writes to the database or changes the stored research cards. Lenders
(banks, NBFCs) are detected from the data, not from a list: borrowed money is their raw material,
so leverage and margin ratios are left out instead of shown as red flags."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import fmt
from ..models import Company, FinancialQ, FinancialY
from .cards import _years, cash_card

HEADLINE_METRICS = ("revenue_growth", "ebitda_margin", "pat_growth", "capex")  # what the brief calls guidance


def _quarters(db: Session, company_id: int) -> list[FinancialQ]:
    return db.scalars(select(FinancialQ).where(FinancialQ.company_id == company_id, FinancialQ.source == "screener")
                      .order_by(FinancialQ.period_end)).all()


def is_lender(ys: list[FinancialY], qs: list[FinancialQ]) -> bool:
    """Screener gives no ROCE or working-capital days for banks and NBFCs, and interest is a large cost of sales."""
    if not ys:
        return False
    y = ys[-1]
    if y.roce is not None or y.receivable_days is not None or y.wc_days is not None:
        return False
    q = next((x for x in reversed(qs) if x.revenue), None)
    return q is None or (q.interest or 0) > 0.25 * q.revenue


def _total(rows: list[FinancialQ], key: str) -> float | None:
    vals = [getattr(r, key) for r in rows]
    return sum(vals) if vals and all(v is not None for v in vals) else None


def _growth(cur: float | None, prev: float | None) -> float | None:
    return (cur - prev) / prev * 100 if cur is not None and prev and prev > 0 else None


def snapshot_card(db: Session, company: Company) -> dict:
    """Headline numbers at a glance: last twelve months from the quarterly table, ratios from the last full year."""
    ys, qs = _years(db, company.id), _quarters(db, company.id)
    if not ys and len(qs) < 4:
        return {"available": False}
    lender = is_lender(ys, qs)
    items = []
    if len(qs) >= 4:
        cur, prev = qs[-4:], qs[-8:-4] if len(qs) >= 8 else []
        period = f"12 months to {cur[-1].fiscal_label}"
        rev, pat, ebitda = _total(cur, "revenue"), _total(cur, "pat"), _total(cur, "ebitda")
        p_rev, p_pat, p_ebitda = (_total(prev, k) if prev else None for k in ("revenue", "pat", "ebitda"))
        vs = "vs the 12 months before"
    else:
        y, py = ys[-1], ys[-2] if len(ys) >= 2 else None
        period = y.fy
        rev, pat, ebitda = y.revenue, y.pat, y.ebitda
        p_rev, p_pat, p_ebitda = (py.revenue, py.pat, py.ebitda) if py else (None, None, None)
        vs = f"vs {py.fy}" if py else ""
    if rev is not None:
        g = _growth(rev, p_rev)
        items.append({"key": "revenue", "label": "Revenue", "value": fmt.crore(rev), "change": g,
                      "detail": f"{fmt.signed_pct(g)} {vs}" if g is not None else None})
    if not lender and rev and ebitda is not None:
        m = ebitda / rev * 100
        pm = p_ebitda / p_rev * 100 if p_rev and p_ebitda is not None else None
        d = m - pm if pm is not None else None
        items.append({"key": "margin", "label": "EBITDA margin", "value": f"{m:.1f}%", "change": d,
                      "detail": f"{fmt.pts(d)} {vs}" if d is not None else None})
    if pat is not None:
        g = _growth(pat, p_pat) if pat > 0 else None
        items.append({"key": "pat", "label": "PAT", "value": fmt.crore(pat), "change": g,
                      "detail": f"{fmt.signed_pct(g)} {vs}" if g is not None else None})
    y = ys[-1] if ys else None
    if y and lender and y.pat is not None and y.net_worth and y.net_worth > 0:
        items.append({"key": "roe", "label": "Return on equity", "value": f"{y.pat / y.net_worth * 100:.1f}%",
                      "change": None, "detail": f"{y.fy}, on year-end net worth"})
    if y and not lender and y.roce is not None:
        py = next((p for p in reversed(ys[:-1]) if p.roce is not None), None)
        d = y.roce - py.roce if py else None
        items.append({"key": "roce", "label": "ROCE", "value": f"{y.roce:.0f}%", "change": d,
                      "detail": f"{y.fy}; {py.fy} {py.roce:.0f}%" if py else y.fy})
    if y and not lender and y.total_debt is not None and y.net_worth and y.net_worth > 0:
        items.append({"key": "de", "label": "Debt ÷ equity", "value": f"{y.total_debt / y.net_worth:.2f}x",
                      "change": None, "detail": y.fy})
    return {"available": bool(items), "period": period, "items": items, "lender": lender}


def trends(db: Session, company: Company) -> dict:
    """The multi-year direction, one row per measure: what is growing, what is compressing."""
    ys = _years(db, company.id)
    if len(ys) < 3:
        return {"available": False}
    lender = is_lender(ys, _quarters(db, company.id))
    rows = []
    for key, label in (("revenue", "Revenue"), ("pat", "PAT")):
        s = [(y.fy, getattr(y, key)) for y in ys if getattr(y, key) is not None]
        if len(s) < 3:
            continue
        (f0, v0), (f1, v1), n = s[0], s[-1], len(s) - 1
        if v0 > 0 and v1 > 0:
            cagr = ((v1 / v0) ** (1 / n) - 1) * 100
            word = "Growing" if cagr >= 2 else "Shrinking" if cagr <= -2 else "Flat"
            detail = f"{f0} {fmt.crore(v0)} → {f1} {fmt.crore(v1)}, {fmt.signed_pct(cagr)} a year"
        else:
            cagr = None
            word = "Growing" if v1 > v0 else "Shrinking"
            detail = f"{f0} {fmt.crore(v0)} → {f1} {fmt.crore(v1)}"
        rows.append({"key": key, "label": label, "word": word, "dir": {"Growing": "up", "Shrinking": "down"}.get(word, "flat"),
                     "detail": detail, "cagr": cagr, "series": [{"fy": f, "v": v} for f, v in s]})
    for key, label in (("opm", "EBITDA margin"), ("roce", "ROCE")):
        if lender:
            continue
        s = [(y.fy, getattr(y, key)) for y in ys if getattr(y, key) is not None]
        if len(s) < 3:
            continue
        (f0, v0), (f1, v1) = s[0], s[-1]
        d = v1 - v0
        word = "Expanding" if d >= 1 else "Compressing" if d <= -1 else "Steady"
        rows.append({"key": key, "label": label, "word": word, "dir": {"Expanding": "up", "Compressing": "down"}.get(word, "flat"),
                     "detail": f"{f0} {v0:.1f}% → {f1} {v1:.1f}%, {fmt.pts(d)}", "cagr": None,
                     "series": [{"fy": f, "v": round(v, 1)} for f, v in s]})
    if not rows:
        return {"available": False}
    up = [r["label"] for r in rows if r["dir"] == "up"]
    down = [r["label"] for r in rows if r["dir"] == "down"]
    parts = []
    if up:
        parts.append(f"{_join(up)} {'is' if len(up) == 1 else 'are'} up")
    if down:
        parts.append(f"{_join(down)} {'is' if len(down) == 1 else 'are'} down")
    title = f"Since {ys[0].fy}: " + ("; ".join(parts) if parts else "little has changed") + "."
    return {"available": True, "title": title, "rows": rows, "from": ys[0].fy, "to": ys[-1].fy}


def _join(xs: list[str]) -> str:
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def balance_card(db: Session, company: Company) -> dict:
    """Debt, leverage, funding structure and the working-capital cycle, from the last full year's balance sheet."""
    ys, qs = _years(db, company.id), _quarters(db, company.id)
    ys = [y for y in ys if y.total_debt is not None or y.net_worth is not None]
    if not ys:
        return {"available": False}
    lender = is_lender(_years(db, company.id), qs)
    y, fy = ys[-1], ys[-1].fy
    rows = []

    def span(key: str) -> tuple[str, list[dict]]:
        s = [(r.fy, getattr(r, key)) for r in ys if getattr(r, key) is not None]
        detail = f"{s[0][0]} {fmt.crore(s[0][1])} → {s[-1][0]} {fmt.crore(s[-1][1])}" if len(s) >= 2 else fy
        return detail, [{"fy": f, "v": round(v)} for f, v in s]

    if y.total_debt is not None:
        detail, series = span("total_debt")
        rows.append({"key": "debt", "label": "Borrowings",
                     "value": fmt.crore(y.total_debt), "detail": detail, "flag": None, "series": series})
    if y.net_worth is not None:
        detail, series = span("net_worth")
        rows.append({"key": "net_worth", "label": "Shareholders' equity", "value": fmt.crore(y.net_worth),
                     "detail": detail, "flag": None, "series": series})
    title = None
    if lender:
        title = "A lender: borrowed money is its raw material, so leverage ratios are not judged here."
    else:
        debt, nw = y.total_debt, y.net_worth
        nd = debt - (y.cash or 0) if debt is not None else None
        if nd is not None:
            rows.append({"key": "net_debt", "label": "Net debt" if nd > 0 else "Net cash", "value": fmt.crore(abs(nd)),
                         "detail": f"{fy}; borrowings less cash of {fmt.crore(y.cash or 0)}", "flag": None, "series": []})
        de = debt / nw if debt is not None and nw and nw > 0 else None
        if de is not None:
            rows.append({"key": "de", "label": "Debt ÷ equity", "value": f"{de:.2f}x", "detail": fy,
                         "flag": "watch" if de > 1 else "healthy", "series": []})
        lev = nd / y.ebitda if nd is not None and nd > 0 and y.ebitda and y.ebitda > 0 else None
        if lev is not None:
            rows.append({"key": "nd_ebitda", "label": "Net debt ÷ EBITDA", "value": f"{lev:.1f}x", "detail": f"{fy}; years of EBITDA to repay",
                         "flag": "red" if lev > 4 else "watch" if lev > 3 else "healthy", "series": []})
        cover = None
        if len(qs) >= 4:
            interest, pbt = _total(qs[-4:], "interest"), _total(qs[-4:], "pbt")
            if interest and interest > 0 and pbt is not None:
                cover = (pbt + interest) / interest
                rows.append({"key": "cover", "label": "Interest cover", "value": f"{cover:.1f}x",
                             "detail": f"12 months to {qs[-1].fiscal_label}; profit before interest and tax ÷ interest",
                             "flag": "red" if cover < 1.5 else "watch" if cover < 3 else "healthy", "series": []})
        if debt is not None and nw and nw > 0 and debt + nw > 0:
            eq = nw / (debt + nw) * 100
            rows.append({"key": "funding", "label": "Funding structure", "value": f"{eq:.0f}% equity",
                         "detail": f"{fy}; {100 - eq:.0f}% borrowings", "flag": None, "series": [],
                         "split": {"equity": round(eq, 1), "debt": round(100 - eq, 1)}})
        if nd is not None:
            if nd <= 0:
                title = f"Net cash of {fmt.crore(abs(nd))}" + (f"; borrowings are {de:.2f}x equity." if de is not None else ".")
            elif lev is not None:
                title = f"Net debt of {fmt.crore(nd)}, {lev:.1f}x a year's EBITDA" + (f"; interest covered {cover:.1f}x." if cover else ".")
            else:
                title = f"Net debt of {fmt.crore(nd)}" + (f"; borrowings are {de:.2f}x equity." if de is not None else ".")
        wc = cash_card(db, company, None)
        for r in wc.get("rows", []) if wc.get("available") else []:
            if r["key"] in ("receivable_days", "inventory_days", "wc_days"):
                rows.append({**r, "value": f"{r['value'].replace('-', fmt.MINUS)} days",
                             "detail": r["detail"].replace("-", fmt.MINUS), "group": "working_capital"})
    return {"available": bool(rows), "title": title, "rows": rows, "lender": lender, "fy": fy,
            "source": f"screener.in, compiled from annual reports ({ys[0].fy}–{fy})"}
