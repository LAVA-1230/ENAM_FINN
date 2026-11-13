"""screener.in tables -> financial_q (last 12 quarters) and financial_y (last 6 years)."""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Company, FinancialQ, FinancialY
from ..sources import screener

log = logging.getLogger(__name__)
SECTOR_MAP = [  # screener's sector breadcrumb -> our sector names (seed/sector_index.yaml)
    ("bank", "Banks"), ("finance", "Financials"), ("nbfc", "Financials"), ("insurance", "Financials"),
    ("it -", "IT"), ("software", "IT"), ("information technology", "IT"), ("pharma", "Pharma"),
    ("healthcare", "Healthcare"), ("hospital", "Healthcare"), ("fmcg", "FMCG"), ("food", "FMCG"),
    ("personal care", "FMCG"), ("automobile", "Auto"), ("auto ", "Auto"), ("cement", "Cement"),
    ("construction", "Infrastructure"), ("capital goods", "Infrastructure"), ("cables", "Infrastructure"),
    ("electrical", "Infrastructure"), ("metal", "Metals"), ("steel", "Metals"), ("oil", "Energy"),
    ("power", "Energy"), ("energy", "Energy"), ("realty", "Realty"), ("chemical", "Chemicals"),
    ("consumer durables", "Consumer durables"), ("retail", "Retail"), ("consumer", "Consumer"),
]


def map_sector(path: list[str]) -> str | None:
    for part in reversed(path or []):
        low = part.lower() + " "
        for key, sector in SECTOR_MAP:
            if key in low:
                return sector
    return None


def load(db: Session, company: Company, parsed: dict | None = None) -> dict:
    d = parsed or screener.parse(company.symbol)
    if d.get("bse_code") and not company.bse_code:
        company.bse_code = d["bse_code"]
    if not company.sector:
        company.sector = map_sector(d.get("sector_path"))
    nq = ny = 0
    for q in d["quarters"][-12:]:
        row = db.scalar(select(FinancialQ).where(FinancialQ.company_id == company.id, FinancialQ.fiscal_label == q["fiscal_label"],
                                                 FinancialQ.source == "screener"))
        if not row:
            row = FinancialQ(company_id=company.id, fiscal_label=q["fiscal_label"], source="screener", period_end=q["period_end"])
            db.add(row)
            nq += 1
        for k in ("revenue", "expenses", "ebitda", "other_income", "interest", "depreciation", "pbt", "tax", "pat"):
            setattr(row, k, q[k])
        row.opm = (q["ebitda"] / q["revenue"] * 100) if q["ebitda"] is not None and q["revenue"] else q["opm"]
        row.basis = d["basis"]
    for y in d["years"][-6:]:
        row = db.scalar(select(FinancialY).where(FinancialY.company_id == company.id, FinancialY.fy == y["fy"]))
        if not row:
            row = FinancialY(company_id=company.id, fy=y["fy"], source="screener")
            db.add(row)
            ny += 1
        for k, v in y.items():
            if k != "fy":
                setattr(row, k, v)
        if y.get("ebitda") is not None and y.get("revenue"):
            row.opm = y["ebitda"] / y["revenue"] * 100
    db.flush()
    return {"quarters": nq, "years": ny, "basis": d["basis"], "url": d["url"], "is_bank": any(q.get("is_bank") for q in d["quarters"])}


def load_all(db: Session) -> dict:
    out = {"ok": [], "failed": []}
    for c in db.scalars(select(Company).where((Company.is_holding.is_(True)) | (Company.is_research.is_(True)))).all():
        try:
            load(db, c)
            out["ok"].append(c.symbol)
            db.commit()
        except Exception as e:  # noqa: BLE001
            db.rollback()
            log.warning("financials %s failed: %s", c.symbol, e)
            out["failed"].append(c.symbol)
    return out
