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
