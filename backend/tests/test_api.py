"""API contract test on a fresh, empty database (no network): every read endpoint answers, and the
empty states are sentences, not errors. Run: cd backend && python -m pytest -q"""
import os
import tempfile

import pytest

_db = os.path.join(tempfile.mkdtemp(), "contract.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db}"
os.environ["LLM_PROVIDER"] = "none"
os.environ["JOB_TOKEN"] = "test-token"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # lifespan seeds the portfolio on an empty DB
        yield c


@pytest.mark.parametrize("path", [
    "/api/health", "/api/brief", "/api/brief?window=7d", "/api/brief?window=since_last_visit",
    "/api/brief?window=custom&from=2026-11-01&to=2026-11-10", "/api/brief/audio-script", "/api/portfolio",
    "/api/research/ready", "/api/settings", "/api/decisions", "/api/notifications", "/api/push/key",
    "/api/admin/usage", "/api/jobs", "/api/ask/suggested",
])
def test_reads(client, path):
    r = client.get(path)
    assert r.status_code == 200, r.text


def test_brief_shape(client):
    b = client.get("/api/brief").json()
    for k in ("window", "header", "attention", "good_to_know", "routine", "coming_up", "tripwires", "counts", "freshness"):
        assert k in b


def test_portfolio_seeded(client):
    p = client.get("/api/portfolio").json()
    assert p["count"] >= 15


def test_company_pages(client):
    sym = client.get("/api/portfolio").json()["holdings"][0]["symbol"]
    for part in ("", "/promises", "/financials", "/cash", "/story", "/timeline", "/tripwires", "/prep"):
        assert client.get(f"/api/companies/{sym}{part}").status_code == 200, part


def test_financials_carries_the_extra_views(client):
    """Snapshot, trajectory and balance sheet ride on /financials and say "unavailable" on an empty DB."""
    sym = client.get("/api/portfolio").json()["holdings"][0]["symbol"]
    f = client.get(f"/api/companies/{sym}/financials").json()
    for k in ("snapshot", "trends", "balance"):
        assert f[k]["available"] is False, k
    for k in ("title", "quarters", "years", "source"):
        assert k in f


def test_glance_views_compute_in_python():
    from datetime import date

    from app.db import session_scope
    from app.models import Company, FinancialQ, FinancialY
    from app.pull import glance

    with session_scope() as db:
        c = Company(symbol="GLANCETEST", name="Glance Test Ltd")
        db.add(c)
        db.flush()
        for i in range(4):
            db.add(FinancialY(company_id=c.id, fy=f"FY2{i + 3}", revenue=1000 + 100 * i, ebitda=200 + 10 * i, opm=20 - i,
                              pat=100 + 10 * i, total_debt=300, cash=100, net_worth=600, roce=18 + i, receivable_days=40,
                              wc_days=30, cfo=90, fcf=50))
        for i in range(8):
            db.add(FinancialQ(company_id=c.id, fiscal_label=f"Q{i % 4 + 1} FY2{5 + i // 4}", period_end=date(2025 + i // 4, 3 * (i % 4) + 3, 28),
                              revenue=300 + 10 * i, ebitda=60 + i, pat=30 + i, pbt=40 + i, interest=5))
        db.flush()
        snap, tr, bal = glance.snapshot_card(db, c), glance.trends(db, c), glance.balance_card(db, c)
        assert snap["available"] and not snap["lender"]
        rev = next(i for i in snap["items"] if i["key"] == "revenue")
        assert round(rev["change"], 2) == round((1420 - 1260) / 1260 * 100, 2)   # last 4 quarters vs the 4 before
        assert {r["key"]: r["word"] for r in tr["rows"]} == {"revenue": "Growing", "pat": "Growing", "opm": "Compressing", "roce": "Expanding"}
        rows = {r["key"]: r for r in bal["rows"]}
        assert rows["de"]["value"] == "0.50x" and rows["net_debt"]["label"] == "Net debt"
        assert rows["nd_ebitda"]["value"] == "0.9x"            # (300 - 100) / 230
        assert rows["cover"]["value"] == "10.1x"               # (182 + 20) / 20
        assert rows["funding"]["split"] == {"equity": 66.7, "debt": 33.3}
        # a lender: no ROCE or working-capital days, interest is a large share of revenue
        b = Company(symbol="LENDTEST", name="Lender Test Ltd")
        db.add(b)
        db.flush()
        for i in range(3):
            db.add(FinancialY(company_id=b.id, fy=f"FY2{i + 4}", revenue=1000, ebitda=-100, opm=-10, pat=150, total_debt=5000, net_worth=1000))
        db.add(FinancialQ(company_id=b.id, fiscal_label="Q1 FY27", period_end=date(2026, 6, 30), revenue=260, interest=140, pat=40))
        db.flush()
        lb = glance.balance_card(db, b)
        assert lb["lender"] and not any(r["flag"] for r in lb["rows"])
        assert {i["key"] for i in glance.snapshot_card(db, b)["items"]} == {"revenue", "pat", "roe"}
        db.rollback()


def test_unknown_company_404(client):
    assert client.get("/api/companies/NOSUCHCO").status_code == 404


def test_ask_not_found_without_documents(client):
    sym = client.get("/api/portfolio").json()["holdings"][0]["symbol"]
    a = client.post("/api/ask", json={"question": "What margin was guided?", "symbol": sym}).json()
    assert a["found"] is False


def test_settings_roundtrip(client):
    r = client.put("/api/settings", json={"price_pct": 2.5, "tier_overrides": {"dividend_corp": "P3"}})
    assert r.status_code == 200
    s = r.json()
    assert s["price_pct"] == 2.5 and s["tier_overrides"]["dividend_corp"] == "P3"
    assert client.put("/api/settings", json={"price_pct": 99}).status_code == 422


def test_decision_and_thesis(client):
    sym = client.get("/api/portfolio").json()["holdings"][0]["symbol"]
    assert client.post("/api/decisions", json={"symbol": sym, "action": "note", "note": "test"}).status_code == 200
    assert client.post("/api/decisions", json={"symbol": sym, "action": "buy"}).status_code == 422
    assert client.patch(f"/api/portfolio/{sym}", json={"thesis": "Compounding at 15%"}).json()["thesis"] == "Compounding at 15%"


def test_jobs_need_token(client):
    assert client.post("/api/jobs/tripwires").status_code == 401
    assert client.post("/api/jobs/nope", headers={"Authorization": "Bearer test-token"}).status_code == 404


def test_push_test_goes_to_inbox(client):
    assert client.post("/api/push/test").json()["channel"] == "inbox"
    assert client.get("/api/notifications").json()["unread"] >= 1
