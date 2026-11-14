# FINN

*FINN interrupts you only when your thesis might be broken. Everything else waits for a batched brief, and every claim links to its source.*

A mobile-first investment agent for a concentrated portfolio of Indian stocks, with two modes:

- **Push:** a windowed brief of NSE filings and EOD price/volume moves, ranked, with routine items counted instead of shown. Includes verified results cards (Rev / EBITDA / PBT / PAT with QoQ and YoY), management-change cards with bios and cluster checks, configurable thresholds, tripwires, an audio brief and web push for urgent items only.
- **Pull:** research on any NSE ticker, grounded only in the last 4 concall transcripts and the latest annual report: a promise ledger (what management promised vs what it delivered) with a guidance filter, a financial snapshot, the multi-year trajectory, the balance sheet, cash quality, the business mix, bull vs bear, and Ask with numbered citations.

- Deployed app: _(link to be added)_
- Write-up: [docs/WRITEUP.md](docs/WRITEUP.md)
- Spec: [FINN_BUILD_SPEC.md](FINN_BUILD_SPEC.md) and [FINN_DESIGN_SYSTEM.md](FINN_DESIGN_SYSTEM.md)

## Architecture

```
 NSE announcements ─┐                         ┌─ Brief / Event / Alerts ─┐
 Yahoo EOD prices ──┼─► Push pipeline ─► DB ◄─┤                          ├─► Next.js PWA (Vercel)
 screener.in ───────┼─► Pull pipeline ─►     ─┤  FastAPI /api (Render)   │      ├ Ask sheet (voice)
 transcripts, ARs ──┘   (rules first,          └─ Company / Ask / Research┘      └ Listen (speechSynthesis)
                         LLM for leftovers)          ▲
        GitHub Actions cron ── POST /api/jobs/* ─────┘  (laptop CLI if NSE blocks the cloud IP)
```

- `backend/app/push`: fetch, normalise, dedupe, classify (regex rules, LLM only for leftovers), enrich, score, digest, notify.
- `backend/app/pull`: any-ticker ingest, chunking, BM25 retrieval, promise extraction, verdicts (arithmetic in Python), cards, Ask.
- `backend/app/llm`: provider-agnostic client (Gemini / Groq / OpenAI / Anthropic), cache, usage and budget, guardrails (citation and number checks, banned phrases).
- `backend/app/api`: REST endpoints (spec section 11) plus replay mode.
- `frontend/`: Next.js 14 App Router, Tailwind (design tokens only), TanStack Query, PWA (manifest + service worker + web push).

**Without any API keys the app still runs:** rule-based parsers and templates replace the LLM, the in-app inbox replaces web push, and bios fall back to the filing's own profile.

## Run locally

```bash
# backend
cd backend
python -m venv .venv && .venv\Scripts\activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                              # fill in keys; blanks are fine
python -m app.jobs.cli bootstrap                    # seed + 120 days of prices + 30 days of filings + research demo set
python -m uvicorn app.main:app --reload --port 8000   # python -m avoids Windows blocking uvicorn.exe

# frontend
cd frontend
npm install
copy .env.example .env.local                        # NEXT_PUBLIC_API_BASE=http://localhost:8000
npm run dev                                         # http://localhost:3000
```

Other CLI jobs: `ingest --days 2`, `eod --days 10`, `research <SYMBOL>`, `tripwires`, `snapshot --label demo`.

## Tests

```bash
cd backend && python -m pytest -q                   # unit + API contract tests (no network)
cd frontend && npm run build && npx next start &    # with the API running on :8000
npx playwright install chromium && npm run test:mobile   # Brief -> event -> company -> Ask at 390 / 360 px, light and dark
```

## Deploy

1. **Database:** create a Postgres database on Neon or Supabase and copy its URL.
2. **Backend (Render):** create a service from `render.yaml`. Set `DATABASE_URL`, `FRONTEND_ORIGIN` (your Vercel URL), `JOB_TOKEN` (a long random string) and, optionally, `LLM_API_KEY`, `WEBSEARCH_API_KEY` and the VAPID keys (`npx web-push generate-vapid-keys`). Tables are created and the portfolio is seeded on first start. Free instances sleep when idle: the first request can take up to a minute, and the app shows "Waking up FINN" while it does.
3. **Frontend (Vercel):** import `frontend/`, set `NEXT_PUBLIC_API_BASE` to the Render URL.
4. **Cron:** `.github/workflows/cron.yml` runs the jobs on GitHub's runners, straight against the database. Add repo secrets `DATABASE_URL` and `LLM_API_KEY` (optional: the VAPID keys, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `FRONTEND_ORIGIN`), plus `FINN_API` and `JOB_TOKEN` for the replay snapshot. It runs ingest hourly 09:00-20:00 IST every day, EOD prices on weekdays, the digest, docs refresh, and a portfolio check-in every `CHECKIN_HOURS` (repo variable, default 1).
5. **Load data:** run `python -m app.jobs.cli bootstrap` once with `DATABASE_URL` pointing at production.

**If NSE blocks the cloud host:** run `python -m app.jobs.cli ingest` from a laptop with `DATABASE_URL` set to production Postgres. It runs the same code against the same database. This is a deliberate trade-off: NSE often blocks datacenter IPs.

**Replay mode:** `python -m app.jobs.cli snapshot --label demo` records the API's responses into `backend/snapshots/demo.json`. Commit it. Turning on Alerts → Data → Replay mode (or adding `?replay=demo` to the URL) serves that window, with a banner saying so. Live mode is the default.

On iPhone, add FINN to the Home Screen to receive push notifications (iOS allows web push only for installed web apps).
