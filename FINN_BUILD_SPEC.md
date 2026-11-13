# FINN: Build Specification for Claude Code

> **What this file is.** The complete brief for building FINN end to end: a working, deployed, mobile-first app with a real backend, not a mock-up. It contains the product decisions, the architecture, every backend module, the API, every frontend screen, the build order, the tests and the submission checklist.
>
> **How to use it (Claude Code).** Put this file at the repo root and reference it from `CLAUDE.md`. Read it fully before writing code. Build in the milestone order of section 14, commit after each milestone, and keep the app demo-able at the end of every milestone. When this spec says **VERIFY**, check the live source before relying on the detail: exchange endpoints and HTML layouts change.

---

## Table of contents

1. Context and deadline
2. Product point of view (the rules every screen follows)
3. Scope: must / should / could / won't
4. Tech stack and repo layout
5. Data sources and how to fetch them
6. Data model
7. Push engine (backend)
8. Pull engine (backend)
9. Daily-workflow features (tripwires, audio brief, voice, concall prep, journal)
10. LLM layer: routing, caching, prompts, guardrails
11. API reference
12. Frontend: design system, screens, components, interactions
13. Notifications, scheduling, deployment, demo/replay mode
14. Milestone plan (12–15 Nov) and cut order
15. Testing and verification
16. Submission checklist and write-up outline
17. Appendices: classifier rules, priority matrix, prompts, JSON schemas, seed portfolio

---

## 1. Context and deadline

**Who it's for.** ENAM Holdings, a lean public-markets firm making high-conviction, long-term decisions. The user is a fundamentals investor with a concentrated portfolio of 15–20 Indian stocks, not a trader.

**The brief in one paragraph.** Build FINN, a mobile-first financial investment agent with two modes. **Push** proactively tells the investor what changed and why they should care: a windowed digest of filings, ranked, with routine items collapsed, plus triggered alerts for material announcements and configurable price/volume thresholds. **Pull** is on-demand research on any NSE company, grounded only in annual reports and concall transcripts. The firm values most a "numbers vs narrative" analysis: what management promised over the last four quarters vs what was delivered.

**How they grade.** Creativity, product sense, judgment and architecture, not completeness. "Thin-but-working beats broad-but-broken." "A demo that doesn't run is the worst outcome." "No AI slop." Efficiency (cheap model routing, caching, chunking) earns bonus points.

**Hard requirements from the brief**

| # | Requirement | Where in this spec |
|---|---|---|
| R1 | Mock portfolio of 15–20 NSE/BSE companies, mixed sectors and sizes | 17.5 |
| R2 | 3–5 extra companies to demo research on | 17.5 |
| R3 | Research must work on **any NSE ticker** (not hard-wired) | 8.1 |
| R4 | EOD price and volume (yfinance, `.NS` tickers) | 5.1 |
| R5 | Corporate announcements from NSE/BSE | 5.2, 5.3 |
| R6 | Annual reports + concall transcripts (screener.in or company IR) | 5.4 |
| R7 | Windowed digest: user picks the period (default 24h), ranked, routine collapsed | 7.7, 12.4 |
| R8 | Triggered alerts: material announcement types + price/volume thresholds, **configurable** | 7.5, 7.6, 12.8 |
| R9 | Management change card with the incoming person's bio | 7.4.2 |
| R10 | Results card: Revenue, EBITDA, PBT, PAT, QoQ and YoY | 7.4.1 |
| R11 | Judgment on every other announcement type (summary / link / hidden) | 7.3, 17.2 |
| R12 | Pull grounded only in annual reports + transcripts; no news, broker notes or model memory | 8, 10.5 |
| R13 | Promise vs delivery over the last 4 quarters (most valued) | 8.3 |
| R14 | Experimental interaction model, mobile-first | 9, 12 |
| R15 | Deployed link easy to open on a phone + GitHub repo + AI build history + write-up | 13, 16 |

**Deadline: Saturday 15 November 2026.** Today is Thursday 12 November, evening (IST). About 2.5 working days remain, so section 14 has a strict build order and a cut order.

---

## 2. Product point of view

**One line (use it in the write-up and the app's empty states):**
> *FINN interrupts you only when your thesis might be broken. Everything else waits for a batched brief, and every claim links to its source.*

**Why:** the same data is available to everyone; the edge is how and when the investor meets it. Research behind this:
- Analysts lose hours filtering alerts across several tools.
- Price alerts and push notifications increase trading and hurt returns; batched news skews judgment less than one-by-one pings.
- Professional managers sell on pre-set "sell triggers" from a pre-mortem, not on headlines.

**Rules every screen follows**
1. Every item answers three questions: **what happened · why it matters · what it does to my portfolio.**
2. **Facts and interpretation are visibly separate.** "From the filing" (white block) vs "FINN's context" (blue block, labelled "computed from stored filings and prices").
3. **Every number and claim is traceable.** Tap it to open the source (filing PDF, transcript page). Unverified numbers say "couldn't verify", never a confident guess.
4. **Routine is counted, not shown.** "11 routine filings hidden · show".
5. **Only P0 interrupts.** P1–P3 wait for the brief.
6. **Every card says why it is here.** "Why this is here: CFO exit · 2nd key exit in 5 months · 8% of your portfolio".
7. **Freshness on every figure.** "EOD close 9 Nov", "filed 16:42 · NSE". Never claim real-time.

**Copy rules (anti-slop), enforced in prompts and reviewed in UI copy**
- Lead with the number or the fact. Max 1 sentence per summary line, ≤ 140 characters.
- Banned words in generated text: "significant", "notably", "robust", "it is worth noting", "this announcement", "overall", "in conclusion", "game-changer", "stellar".
- No sentence without a number, a name, a date or a citation in Pull outputs.
- No emoji in the UI.

---

## 3. Scope

Build top to bottom. **Must** = the demo fails without it. **Should** = makes it distinctive. **Could** = only if time remains. **Won't** = say so in the write-up.

| Priority | Feature |
|---|---|
| **Must** | Portfolio seed (18 holdings, weights, sectors) |
| **Must** | EOD prices + index prices; stock-specific move split; ₹ impact |
| **Must** | NSE announcements ingest, dedupe, rule classifier, priority scoring, "why this is here" |
| **Must** | Windowed digest (24h / 3d / 7d / custom / since last visit) with tiers + routine collapsed |
| **Must** | Results enrichment (Rev/EBITDA/PBT/PAT, QoQ/YoY, validated) |
| **Must** | KMP change enrichment (who, reason, successor, cluster check, bio) |
| **Must** | Configurable thresholds (price %, volume ×, portfolio impact) + per-category tier overrides |
| **Must** | Pull: any-ticker ingest (screener.in docs + financial tables), promise ledger with verdicts and citations |
| **Must** | Ask (text) with citations, grounded only in the company's documents |
| **Must** | Deployed frontend + backend, replay mode so the demo is never empty |
| **Should** | Cash quality card, business/segment snapshot, bull vs bear |
| **Should** | Credit rating, pledge, fund-raise, order-win, M&A enrichment (size vs company) |
| **Should** | Tripwires per holding + "tripwire hit" events |
| **Should** | Audio brief ("Listen"), push-to-talk voice Ask |
| **Should** | Concall prep card + results calendar strip |
| **Should** | Web Push for P0 with in-app inbox fallback |
| **Should** | Decision journal + "Last time you…" on cards; thesis tag on events |
| **Could** | Swipe mode for the brief |
| **Could** | Share card (Web Share API) |
| **Could** | BSE fallback source; insider/SAST trades; bulk/block deals |
| **Could** | Telegram bot for P0 |
| **Won't** | Real-time prices, intraday alerts, native app, valuation models, news/broker data, multi-user auth, Hinglish voice, home-screen widgets |

---

## 4. Tech stack and repo layout

### 4.1 Stack (defaults; the user may override)

| Layer | Choice | Why |
|---|---|---|
| Backend | Python 3.11+, **FastAPI**, Pydantic v2, SQLAlchemy 2.0 | Fast to build; Python has the data libraries |
| DB | **SQLite** locally; **Postgres** (Neon or Supabase free tier) in production via `DATABASE_URL` | Same ORM code; prod DB persists across deploys |
| Scheduling | **GitHub Actions cron** calling protected job endpoints, plus a CLI for manual/local runs | Free-tier hosts sleep; cron also wakes them |
| PDFs | **PyMuPDF** (`pymupdf`) for text; `pdfplumber` only if tables need it | Fast, reliable |
| HTTP | `httpx` with retries (`tenacity`) | |
| Prices | `yfinance` | Named in the brief |
| HTML parsing | `selectolax` or `beautifulsoup4` | screener.in pages |
| Retrieval | **BM25** (`rank_bm25`) over section-aware chunks | No embedding cost; good on financial terms |
| LLM | Provider-agnostic client; default **Google Gemini** (fast + smart tiers), switchable to Groq/OpenAI/Anthropic via env | Free tier; routing is the cost story |
| Web search (bio) | Optional Tavily or Brave Search API key; fall back to the appointment filing's own profile | |
| Push | `pywebpush` + VAPID keys | Web Push from a PWA |
| Frontend | **Next.js 14+ (App Router), TypeScript, Tailwind CSS**, PWA (manifest + service worker) | Deploys to Vercel; one link opens on any phone |
| Frontend data | TanStack Query | Caching, loading states |
| Voice | Browser Web Speech API (`SpeechRecognition`, `speechSynthesis`), feature-detected | Free; no server audio |
| Hosting | Frontend: Vercel. Backend: Render or Railway (free tier). DB: Neon/Supabase | |
| Tests | pytest; Playwright for a mobile smoke test | |

**Model names and free-tier limits change. VERIFY current names and limits for the chosen provider before coding the defaults.** Put model names in env vars (`LLM_FAST_MODEL`, `LLM_SMART_MODEL`), never hard-coded.

### 4.2 Repo layout

```
finn/
├── CLAUDE.md                     # points to this spec; working rules
├── FINN_BUILD_SPEC.md            # this file
├── BUILD_LOG.md                  # running log of decisions (helps the "AI build history")
├── README.md                     # setup, run, deploy, architecture diagram, write-up link
├── docs/
│   ├── WRITEUP.md                # covering-note draft (section 16)
│   └── ARCHITECTURE.md
├── backend/
│   ├── pyproject.toml
│   ├── .env.example
│   ├── app/
│   │   ├── main.py               # FastAPI app, CORS, routers
│   │   ├── config.py             # pydantic-settings, env vars
│   │   ├── db.py                 # engine, session, init
│   │   ├── models.py             # SQLAlchemy models (section 6)
│   │   ├── schemas.py            # Pydantic response models (section 11)
│   │   ├── fiscal.py             # Indian FY/quarter helpers
│   │   ├── sources/
│   │   │   ├── nse.py            # announcements, session warm-up
│   │   │   ├── bse.py            # fallback announcements (Could)
│   │   │   ├── prices.py         # yfinance wrapper, index prices
│   │   │   ├── screener.py       # docs links + financial tables
│   │   │   ├── pdf.py            # download, cache, text extraction, page select
│   │   │   └── websearch.py      # optional bio search
│   │   ├── push/
│   │   │   ├── rules.py          # keyword → category table (Appendix 17.1)
│   │   │   ├── classify.py       # rules first, LLM fallback
│   │   │   ├── score.py          # priority matrix (Appendix 17.2)
│   │   │   ├── enrich/
│   │   │   │   ├── results.py
│   │   │   │   ├── kmp.py
│   │   │   │   ├── rating.py
│   │   │   │   ├── pledge.py
│   │   │   │   ├── corporate_action.py   # fundraise, M&A, order, capex, buyback, dividend
│   │   │   │   └── generic.py            # one-line summary
│   │   │   ├── price_signals.py
│   │   │   ├── tripwires.py
│   │   │   ├── digest.py
│   │   │   ├── audio.py          # audio-brief script
│   │   │   └── notify.py         # web push + inbox
│   │   ├── pull/
│   │   │   ├── ingest.py         # any-ticker cold start orchestration
│   │   │   ├── financials.py     # quarterly/annual tables → DB
│   │   │   ├── chunks.py         # section-aware chunking
│   │   │   ├── retrieval.py      # BM25 index per company
│   │   │   ├── promises.py       # extraction per transcript
│   │   │   ├── verdict.py        # deterministic + LLM verdicts
│   │   │   ├── cash.py
│   │   │   ├── business.py       # segments / revenue mix
│   │   │   ├── bullbear.py
│   │   │   ├── prep.py           # concall prep questions
│   │   │   └── ask.py
│   │   ├── llm/
│   │   │   ├── client.py         # provider abstraction, JSON mode, retries
│   │   │   ├── cache.py          # (prompt_version, input_hash) → output
│   │   │   ├── usage.py          # token + cost logging
│   │   │   ├── guard.py          # citation + number checks
│   │   │   └── prompts/          # one .md per prompt, versioned (Appendix 17.3)
│   │   ├── api/
│   │   │   ├── brief.py  events.py  companies.py  research.py
│   │   │   ├── ask.py  settings.py  portfolio.py  decisions.py
│   │   │   ├── push.py  jobs.py  replay.py  health.py
│   │   └── jobs/
│   │       ├── runner.py         # job functions
│   │       └── cli.py            # `python -m app.jobs.cli <cmd>`
│   ├── seed/
│   │   ├── portfolio.yaml        # holdings, quantities, sectors, BSE codes
│   │   └── sector_index.yaml     # sector → yfinance index symbol
│   ├── snapshots/                # replay snapshots (committed: one demo window)
│   └── tests/
│       ├── fixtures/             # 3–5 real results PDFs, 2 transcripts, sample API JSON
│       └── test_*.py
├── frontend/
│   ├── package.json
│   ├── app/                      # routes (section 12.3)
│   ├── components/
│   ├── lib/                      # api client, types, voice, audio, push
│   ├── public/manifest.webmanifest, sw.js, icons
│   └── tests/mobile.spec.ts
└── .github/workflows/
    ├── ci.yml                    # lint + tests
    └── cron.yml                  # scheduled job calls
```

### 4.3 Environment variables (`backend/.env.example`)

```
DATABASE_URL=sqlite:///./finn.db
FRONTEND_ORIGIN=http://localhost:3000
JOB_TOKEN=change-me                 # protects /jobs/* endpoints
LLM_PROVIDER=gemini                 # gemini | groq | openai | anthropic
LLM_API_KEY=
LLM_FAST_MODEL=                     # VERIFY current cheap model name
LLM_SMART_MODEL=                    # VERIFY current strong model name
LLM_DAILY_BUDGET_USD=0.50           # hard stop for paid tiers
WEBSEARCH_PROVIDER=none             # none | tavily | brave
WEBSEARCH_API_KEY=
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_SUBJECT=mailto:you@example.com
DATA_DIR=./data                     # pdf cache, text cache
REPLAY_DEFAULT=false
TZ=Asia/Kolkata
```

Frontend: `NEXT_PUBLIC_API_BASE`, `NEXT_PUBLIC_VAPID_PUBLIC_KEY`.

### 4.4 Human prerequisites (ask the user if missing; never create paid accounts)

- [ ] GitHub repo created
- [ ] LLM API key (free tier)
- [ ] Optional web-search API key for bios
- [ ] Vercel account (frontend), Render/Railway account (backend), Neon/Supabase (Postgres)
- [ ] A phone to test on (Android Chrome is the easiest for push + voice)

---

## 5. Data sources

**Politeness and resilience rules (apply to every source):**
- Browser-like `User-Agent`, `Accept`, `Accept-Language`, `Referer` headers.
- Max ~1 request/second per host; exponential backoff on 401/403/429/5xx; max 3 retries.
- Cache every raw response and every downloaded PDF on disk keyed by URL hash. Never download the same PDF twice.
- Every stored item keeps `source`, `source_url`, `fetched_at`, `published_at`.
- If a live fetch fails, the app keeps serving stored data and shows the last-updated time. It never crashes and never shows an empty error screen.

### 5.1 Prices (yfinance)

- Holdings: `<SYMBOL>.NS`. Fetch 60 trading days on first run, then incremental daily.
- Indices: Nifty 50 `^NSEI`; sector indices from `seed/sector_index.yaml`, e.g. `^NSEBANK`, `^CNXIT`, `^CNXPHARMA`, `^CNXAUTO`, `^CNXFMCG`, `^CNXMETAL`, `^CNXREALTY`, `^CNXENERGY`. **VERIFY each symbol returns data**; if a sector index is missing, fall back to `^NSEI` and label the split "vs Nifty".
- Store close, volume and the date. Freshness label: "EOD close <date>".
- Batch download (`yf.download([...], period=..., group_by="ticker")`) to keep requests low.

### 5.2 NSE corporate announcements (primary)

- NSE requires a cookie session: `GET https://www.nseindia.com/` first (browser headers), then reuse the session cookies for the API.
- Endpoint pattern (**VERIFY**): `GET https://www.nseindia.com/api/corporate-announcements?index=equities&symbol=<SYMBOL>&from_date=DD-MM-YYYY&to_date=DD-MM-YYYY`
- Fields typically include the symbol, company name, `desc` (NSE's category text), `attchmntText` (subject/summary), `attchmntFile` (PDF URL), and an announcement timestamp (`an_dt` / `sort_date`) plus a sequence id. **VERIFY field names on a live response** and map them in one place (`sources/nse.py::normalise`).
- If 401/403 persists: refresh the session once, then fall back to BSE (Could) or stored data.
- **NSE often blocks datacenter IPs.** Design for it: the ingestion CLI can run from the developer's laptop against the production `DATABASE_URL` (section 13.4). Document this in the README.

### 5.3 BSE announcements (fallback, Could)

- Endpoint pattern (**VERIFY**): `https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w?pageno=1&strCat=-1&strPrevDate=YYYYMMDD&strScrip=<BSE_CODE>&strSearch=P&strToDate=YYYYMMDD&strType=C&subcategory=-1` with `Referer: https://www.bseindia.com/`.
- Attachment URL pattern: `https://www.bseindia.com/xml-data/corpfiling/AttachLive/<ATTACHMENTNAME>`.
- Needs the BSE scrip code per company (store it in `portfolio.yaml`).
- Dedupe across exchanges (section 7.2).

### 5.4 screener.in (fundamentals for Pull)

- Company page: `https://www.screener.in/company/<SYMBOL>/consolidated/`; fall back to `/company/<SYMBOL>/` (standalone) if consolidated is empty. **VERIFY layout and selectors.**
- **Documents section:** annual report links (by year) and concall rows (Transcript / PPT / recording links, by date). Take the **last 4 transcripts** and the **latest 1–2 annual reports**.
- **Financial tables on the same page:** quarterly results (about the last 12 quarters: sales, expenses, operating profit, OPM %, other income, interest, depreciation, PBT, tax %, net profit), annual P&L, balance sheet, cash flow, ratios (debtor days, inventory days, working-capital days, ROCE). Parse these into structured tables.
- **Grounding decision (write it in the write-up):** numbers come from screener.in's tables, which are compiled from company filings, and are cross-checked against results PDFs where we have them. Narrative, guidance and segments come only from annual reports and transcripts. No news, broker notes or model memory.
- Cache the HTML for 24h. Be polite: it is a small site.

### 5.5 Bios for management changes

Order of preference:
1. **The appointment filing itself.** Indian KMP appointment filings usually include a brief profile. Extract it with the fast model.
2. **Web search API** (if a key is configured): query `"<name>" <company> CFO`, take the top 3 results, and have the fast model write ≤ 3 lines (previous roles with years, qualifications) with the source URLs.
3. If nothing is found: "No public profile found", plus the filing link.

**Do not scrape LinkedIn** (its terms forbid it and it blocks bots). Mention "LinkedIn-style background" in the UI copy only as a description.

---

## 6. Data model

Use SQLAlchemy models; all timestamps UTC in the DB, rendered in IST. JSON columns are fine for nested data.

```
company        id, symbol (unique), name, isin, bse_code, sector, sector_index,
               is_holding, is_research, created_at

holding        id, company_id, quantity, avg_cost, thesis (text),
               thesis_source ("concall"|"user"), muted_until, only_p0 (bool)

price_daily    company_id|index_symbol, date, close, volume   (unique per key+date)

filing         id, company_id, exchange ("NSE"|"BSE"), exchange_category (raw desc),
               subject, attachment_url, published_at, fetched_at,
               raw (json), content_hash (unique), pdf_text_path

event          id, company_id, filing_id (nullable), kind ("filing"|"price"|"volume"|
               "tripwire"|"sector"|"cluster"), category, tier ("P0".."P3"), score,
               reasons (json list of strings → "why this is here"),
               title, metric_line, impact_line, summary,
               facts (json), context (json list), enrichment (json),
               status ("new"|"seen"|"dismissed"), dismiss_reason,
               thesis_tag ("strengthens"|"neutral"|"weakens"|null),
               verify_ok (bool), created_at, event_date

financial_q    company_id, fiscal_label ("Q2 FY27"), period_end, revenue, expenses,
               ebitda, opm, other_income, interest, depreciation, pbt, tax, pat,
               basis ("consolidated"|"standalone"), source ("results_pdf"|"screener")
financial_y    company_id, fy, revenue, ebitda, pat, cfo, capex, total_debt, cash,
               net_worth, receivable_days, inventory_days, wc_days, roce, source

document       id, company_id, kind ("transcript"|"annual_report"|"presentation"|"results"),
               period_label ("Q1 FY27" / "FY26"), url, local_path, text_path,
               pages, content_hash, fetched_at
chunk          id, document_id, page_from, page_to, section, speaker, text

promise        id, company_id, document_id, made_in ("Q4 FY26"), metric, metric_key
               ("revenue_growth"|"ebitda_margin"|"pat_growth"|"capex"|"net_debt"|
               "volume"|"plant"|"other"), target_text, target_low, target_high, unit,
               horizon ("FY27"|"Q1 FY27"|...), quote, page, speaker
promise_verdict promise_id, status ("kept"|"missed"|"late"|"on_track"|"pending"|"dropped"),
               actual_text, actual_value, evidence (json: citations), method
               ("rule"|"llm"), computed_at

company_research company_id, status ("queued"|"running"|"ready"|"failed"),
               progress (json steps), cards (json: cash, business, bullbear, scorecard),
               updated_at, error

tripwire       id, company_id, kind ("metric"|"event_count"|"pledge"|"drawdown"|"weight"),
               metric_key, op (">"|"<"), threshold, window_days, label,
               source ("auto"|"user"), last_value, status ("ok"|"near"|"hit")

decision       id, company_id, event_id (nullable), action ("hold"|"add"|"trim"|"exit"|"note"),
               note, created_at

settings       singleton: price_pct, volume_x, impact_pct, tier_overrides (json),
               push_p0_only, show_routine, brief_times, last_brief_seen_at

push_sub       id, endpoint, keys (json), created_at
notification   id, event_id, channel ("webpush"|"inbox"), sent_at, delivered (bool)

llm_cache      key (prompt_name+version+input_hash), output (json), model, created_at
llm_usage      id, job, prompt_name, model, input_tokens, output_tokens, cost_usd, created_at
job_run        id, job, started_at, finished_at, ok, stats (json), error
snapshot       id, label, window_from, window_to, payload_path, created_at
```

Single user. No auth for reading (reviewers must open the link instantly). Write endpoints for settings/decisions are open too (demo). **Job endpoints require `JOB_TOKEN`.**

**Fiscal helper (`fiscal.py`):** the Indian FY runs April–March. Q1 = Apr–Jun, Q2 = Jul–Sep, Q3 = Oct–Dec, Q4 = Jan–Mar. FY27 = Apr 2026–Mar 2027. Provide `quarter_label(date)`, `prev_quarter(label)`, `year_ago(label)`, and parsers for strings like "Quarter ended 30.09.2026" and "Sep 2026".

---

## 7. Push engine

### 7.1 Pipeline

```
fetch → normalise → dedupe → classify → enrich → score → store event → notify (P0 only)
```

One job, `ingest_filings(window)`, runs for every holding (and research companies, so their timelines fill). Each stage is a pure function where possible, so it can be unit-tested.

### 7.2 Normalise and dedupe

- Map the exchange's fields to the `filing` model in one function per source.
- `content_hash = sha1(symbol + (attachment_url or subject) + published_date)`.
- Cross-exchange dedupe: same company, same day, subject similarity ≥ 0.9 (rapidfuzz) → keep the NSE copy.

### 7.3 Classify (rules first)

1. Match NSE's `exchange_category` and the subject text against the regex table in **Appendix 17.1**, in order. First match wins.
2. Unmatched filings (expect ~10–20%) go to the **fast model** with the fixed category list; it returns `{category, confidence}`. If confidence is below 0.6 → category `other`, tier P2, with the raw subject shown.
3. Log the hit rate (rules vs LLM). It goes into the write-up ("X% classified with zero LLM cost").

### 7.4 Enrichment handlers

Register handlers in a dict `{category: handler}`. Each returns `facts` (from the filing), `context` (computed by FINN) and `enrichment` (card-specific data). Each sets `verify_ok`.

#### 7.4.1 Results (`enrich/results.py`), Must

1. Download the PDF; extract text from the first ~8 pages (results tables are near the front).
2. Fast model + JSON schema (Appendix 17.4, `results_extract`): current quarter, previous quarter and year-ago quarter columns for revenue from operations, other income, total expenses, finance costs, depreciation, PBT, tax, PAT; plus `basis` (consolidated/standalone), `unit` (lakh/crore/million) and `period_labels`.
3. Python computes in ₹ crore: **EBITDA = PBT + finance costs + depreciation − other income**, EBITDA margin, QoQ % and YoY % for each metric, and margin change in points.
4. **Validate before showing:**
   - Every extracted number must appear in the PDF text (normalise commas and decimals).
   - |(PBT − tax) − PAT| ≤ 1.5% of PAT (allow for minority interest / exceptional items: if it fails, look for an "exceptional items" line before failing).
   - Units are consistent across columns.
   - Cross-check with screener quarterly data when available (within 2%).
   - If validation fails: show the filing with "Results filed · couldn't verify numbers automatically · open PDF". Never show unverified numbers as fact.
5. Prefer consolidated; label which basis is shown.
6. **Banks and NBFCs:** EBITDA is not meaningful. Detect by sector (Banks/Financials) or by lines like "Interest earned"; show Total income, Operating profit (pre-provision), Provisions, PBT, PAT instead, and say so on the card.
7. Context lines: compare against the latest guidance in `promise` (if this company has a promise ledger), e.g. "EBITDA margin 21.8% vs 24–25% guided (Q4 FY26 call)"; give the concall date if a concall-intimation filing exists.
8. Escalate to P0 if |PAT YoY| > 20% or the margin moves more than 3 points vs guidance (defaults; tunable).

#### 7.4.2 KMP change (`enrich/kmp.py`), Must

1. Fast model extracts: `person`, `role`, `change` (resignation/appointment/cessation/retirement), `reason_stated` (verbatim), `effective_date`, `successor` (name/role/interim?), `profile_text` (if the filing includes a profile).
2. **Cluster check:** count other KMP/director/auditor exit events for this company in the last 365 days from `event`. If ≥ 1 → context "2nd key exit in N months: <role> left on <date>" and the score escalator.
3. **Timing check:** days to the next board meeting / results date (from intimation filings) → context "Exit comes 7 days before the Q2 board meeting".
4. **Bio:** section 5.5 for the incoming or interim person (and the outgoing person's tenure if stated).
5. Tier: CEO/MD/CFO resignation → P0; planned retirement with successor named → P1; CS/other KMP → P2 (P1 if part of a cluster). **Auditor resignation → always P0** with the auditor's stated reason quoted.
6. Never imply wrongdoing. Context states facts ("Reason stated: personal reasons"), not speculation.

#### 7.4.3 Credit rating (`enrich/rating.py`), Should

Extract the agency, instrument, amount, old → new rating, outlook and rationale (≤ 1 line, quoted). Downgrade → P1 (P0 if the company is a lender/NBFC or debt/equity > 1). Upgrade → P2. Reaffirmation → P3.

#### 7.4.4 Pledge / SAST (`enrich/pledge.py`), Should

Extract promoter holding %, pledged share of the promoter holding (before → after) and the lenders. Context: crossing 40%; the price trend this month. Rising pledge with the price falling → P0.

#### 7.4.5 Corporate actions (`enrich/corporate_action.py`), Should

Fund-raise (QIP/rights/preferential/NCD), M&A, order win, capex, buyback, dividend/bonus/split. Extract the amount, then compute **size vs company** from `financial_y`: order value ÷ last FY revenue; deal value ÷ market cap (price × shares, if available; otherwise vs net worth); dilution %; capex ÷ gross block or net worth. Show "₹500 cr order ≈ 18% of FY26 revenue". The thresholds for escalation are in Appendix 17.2.

#### 7.4.6 Generic (`enrich/generic.py`)

- P2: fast model writes one line, ≤ 140 characters, number-first, from the filing's first 2 pages.
- P3: no LLM call. The title only.

### 7.5 Price signals (`push/price_signals.py`), Must

After each EOD price job, for each holding:

```
ret         = close / prev_close - 1
sector_ret  = sector index return (fallback Nifty)
specific    = ret - sector_ret
vol_ratio   = volume / mean(volume over previous 20 sessions)
impact_rs   = quantity * (close - prev_close)
impact_pct  = weight * ret            # contribution to portfolio return
explained   = any filing for this company in the last 48h (link it)
```

Events:
- **Stock-specific move:** |specific| ≥ `settings.price_pct` → P1; escalate to P0 if |impact_pct| ≥ `settings.impact_pct`.
- **Unusual volume:** vol_ratio ≥ `settings.volume_x` → P2; P1 if `explained` is false ("unexplained").
- **Sector move:** if 3+ holdings in one sector move the same way beyond half the threshold → one grouped card instead of several.
- **Portfolio header (not an event):** total return, ₹ change, Nifty return, top contributor and its share of the move, and a stacked bar of contributors.

Language rule: volume is an **observation**, never a prediction. No "may signal accumulation".

### 7.6 Scoring (`push/score.py`), Must

Implement Appendix 17.2 exactly. The function returns `(tier, score, reasons)`; `reasons` are short human strings that are shown on the card as "Why this is here".

```
score = base(category)                         # P0=90, P1=70, P2=40, P3=10
      + 15 if cluster detected
      + 10 if holding weight > 8%
      + 10 if size_vs_company over its threshold
      + 10 if same-day price move confirms (same direction, ≥ half the price threshold)
      - 20 if a duplicate/follow-up of an event already shown
tier  = P0 if score ≥ 85 · P1 if ≥ 60 · P2 if ≥ 30 · else P3
then apply settings.tier_overrides[category] (user override wins)
then apply holding.muted_until / only_p0
```

### 7.7 Digest (`push/digest.py`), Must

`build_brief(window_from, window_to)` returns:
- `header`: portfolio return, ₹ change, Nifty return, attribution (top 3 contributors), "stock-specific vs market" sentence (templated, no LLM).
- `attention`: P0 + P1 events, sorted by score then time.
- `good_to_know`: P2 one-liners.
- `routine`: P3 count + titles, grouped (e.g. "Trading window closure (6 companies)").
- `coming_up`: next 7 days of board meetings/concalls (from intimation filings).
- `tripwires_near`: tripwires with status `near`.
- `counts` and `freshness` (last filings fetch time, last EOD date).

Windows: `24h` (default), `3d`, `7d`, `custom` (from/to), `since_last_visit` (uses `settings.last_brief_seen_at`).

### 7.8 Cluster and red-flag rules (part of scoring/context)

- KMP cluster: ≥ 2 key exits (CEO, MD, CFO, CS, auditor, independent director) in 365 days.
- Auditor resignation: always P0.
- Payment default / delay filings: always P0.
- Pledge: crossing 40% of promoter holding, or rising for 2 consecutive filings while the stock is down this month → P0.

---

## 8. Pull engine

### 8.1 Any-ticker cold start (`pull/ingest.py`), Must

`POST /research/{symbol}` starts a background task and returns immediately with `status=running`. Progress steps (stored in `company_research.progress`, polled by the UI):

1. **Resolve** the symbol: validate it with yfinance (`<SYMBOL>.NS` has history) and the screener page exists. Create the `company` row if new.
2. **Financials:** parse screener tables → `financial_q` (last 12 quarters) and `financial_y` (last 5 years).
3. **Documents:** collect links for the last 4 concall transcripts and the latest annual report. Download and extract text (cache).
4. **Chunk:** transcripts by speaker turn (merge short turns to ~800–1,200 tokens, keep the page number and speaker); annual reports by section heading, but only for **selected pages** (8.6).
5. **Promises:** extract per transcript (8.2).
6. **Verdicts:** rule-based first, LLM for the rest (8.3).
7. **Cards:** cash quality, business snapshot, bull vs bear (8.4–8.5).
8. **Index:** build the BM25 index for Ask.
9. `status=ready`.

Target: under 2 minutes cold, instant after. Run the Must steps (1–6, 8) first and mark the company `ready` with partial cards if Should steps fail. **Never hard-code anything to the demo companies.** Test with a random ticker before submission.

### 8.2 Promise extraction (`pull/promises.py`), Must

- One **fast-model** call per transcript, with the whole transcript text (transcripts are typically 15–40 pages and fit in a long-context model). If it's too long, split at the end of the management opening remarks vs the Q&A and run twice.
- Output (Appendix 17.4, `promise_extract`): every **explicit forward-looking commitment** on growth, margins, capex, debt, volumes, capacity/plant timelines, product launches or market share. Each with metric, `metric_key`, target text, numeric low/high, unit, horizon, **verbatim quote**, page and speaker.
- Exclude vague statements ("we remain optimistic") unless they include a number or a date.
- Dedupe across quarters: the same metric + horizon repeated in later calls → keep the earliest as `made_in` and record the repeats (shows consistency) or changes (shows revisions: "guidance cut from 24–25% to 22–23% in Q2 FY27").

### 8.3 Verdicts (`pull/verdict.py`), Must

**Rules first (Python), using `financial_q`/`financial_y`:**

| metric_key | Actual computed as | Verdict logic |
|---|---|---|
| revenue_growth | YoY growth for the horizon (YTD quarters vs the same quarters a year ago, if the horizon is a full FY in progress) | ≥ low → kept/on_track; < low by > 1pt → missed (or "behind" if the horizon is still open) |
| ebitda_margin | OPM for the horizon quarters | inside the band → kept; below low → missed / behind |
| pat_growth | as revenue | as revenue |
| net_debt | latest total debt − cash | on the path to target → on_track |
| capex | YTD capex vs the annual target, pro-rated | ≥ 40% at H1 → on_track |
| other (plant, launch, filings, market share) | LLM judge (below) | |

Status meanings: **kept** (horizon passed, met), **missed** (horizon passed, not met), **late** (met after the horizon), **on_track / behind** (horizon still open), **pending** (no data yet), **dropped** (not mentioned in the last 2 transcripts after being stated before; detect with BM25 search + the fast model confirming absence).

**LLM judge (smart model, one call per company, only for non-numeric promises):** input = the promise rows + relevant excerpts from later transcripts and results (retrieved by BM25 on the metric words). Output = status + the actual-evidence quote + citations. Arithmetic is never done by the LLM.

**Scorecard:** "Delivered X of Y promises that have come due" + counts by status. This is the hero card of the company page.

### 8.4 Cash quality (`pull/cash.py`), Should

From `financial_y`:
- **Operating cash flow ÷ PAT** (3-year average and latest). Flags: ≥ 0.8 healthy; 0.5–0.8 watch; < 0.5 red flag.
- **Receivable days, inventory days, working-capital days** trend (3–5 years). Rising for 2+ years → watch.
- **Net debt** and its trend; debt/equity.
Every value carries its source ("FY26, screener.in from annual report" / annual report page).

### 8.5 Business snapshot and bull vs bear, Should

- **Business (`pull/business.py`):** from the annual report's segment note and MD&A pages: segments with revenue share %, one-line description per segment, geography split if stated. Fast model, JSON, with the page citation.
- **Bull vs bear (`pull/bullbear.py`):** smart model; input = the promise scorecard + cash card + business card + financial trends (structured data only, no raw documents). 3 bullets each, ≤ 120 characters, each citing the card/source it came from. It may not introduce any fact not present in the input (the guard enforces this, 10.5).

### 8.6 Annual report page selection (cost control)

Annual reports run to 200–400 pages. Never send the whole report. Score each page by keyword hits:
- MD&A: "management discussion", "outlook", "industry overview", "opportunities", "threats".
- Segments: "segment information", "segment revenue", "operating segments".
- Cash/working capital: "cash flow statement", "trade receivables", "inventories", "borrowings".

Take the top ~15 pages per section group (contiguous runs preferred) and record page numbers for citations.

### 8.7 Ask (`pull/ask.py`), Must

1. Context: optional `company_id` and `event_id` (from the card the user opened). Portfolio-level questions ("what moved my portfolio?") are answered from computed data, without retrieval.
2. Retrieve the top 8 chunks by BM25 from that company's transcripts, selected annual-report pages and recent filings, plus relevant structured rows (`financial_q`, `promise`, `event`).
3. **Smart model** answers in ≤ 120 words, every sentence ending with citation markers `[1]`, `[2]` mapped to chunks (document, period, page).
4. Guard (10.5): drop sentences without a valid citation; check numbers against sources; if nothing relevant was retrieved → "Not found in this company's filings and transcripts."
5. Suggested questions per context (3 per card type), generated by template, not by LLM.
6. Cache answers by (question normalised, context ids, document hashes).

### 8.8 Concall prep (`pull/prep.py`), Should

For each holding with a concall in the next 3 days (from intimation filings), and on demand: build 3–5 questions from:
- promises marked missed/behind/dropped ("FY27 margin guidance was 24–25%; H1 is 22.8%. Is the guidance unchanged?"),
- tripwires near or hit,
- KMP changes since the last call.
Questions are templated from structured data; the fast model only smooths wording (≤ 25 words each). After the transcript arrives, mark each question answered or not (fast model over the Q&A section) and refresh the promise ledger.

---

## 9. Daily-workflow features

These implement the point of view: personal, low-noise, verifiable.

### 9.1 Tripwires (`push/tripwires.py`), Should, high value

- Each holding gets 2–4 **auto tripwires** when its research is ready, editable by the user:
  - from missed or behind promises (e.g. "EBITDA margin < 22%"),
  - standard red flags: "Another key person exits (12 months)", "Promoter pledge > 40%", "Working-capital days > <current + 10>", "Position weight > 10%", "Drawdown from avg cost > 25%".
- Evaluate after every ingest (filings, prices, financials). Status: `ok`, `near` (within 10% of the threshold), `hit`.
- A hit creates an event (kind `tripwire`): **"Tripwire hit · Kestrel working-capital days 41 (your limit 35)"**, P0 by default, with the reasons and the source.
- The UI shows tripwires on the company page and "near" ones in the brief.

### 9.2 Thesis per holding

- Pre-fill each holding's thesis (≤ 2 lines) from the latest concall's management opening remarks + the promise ledger (fast model, cited); the user can edit it.
- Each P0/P1 event card asks "Does this change your thesis?" (Strengthens / No change / Weakens), stored as `event.thesis_tag`.
- Portfolio list shows thesis health: green (no weakens/hit tripwires in 90 days), amber (one), red (a tripwire hit or two or more weakens).

### 9.3 Decision journal, Should

- On any event or company: Hold / Add / Trim / Exit / Note, plus a one-line reason (typed or dictated).
- The next event for that company shows **"Last time (14 Jun): you held after the CS exit: 'watch for more exits'."**
- Company page tab or section: "Your decisions" (newest first).

### 9.4 Audio brief ("Listen"), Should

- `GET /brief/audio-script?window=…` returns a plain-text script, about 60–120 seconds when read (~150–300 words), built **by template** from the brief: header sentence → each P0/P1 in one sentence → count of the rest → "coming up today". Example: "Good morning. Your portfolio fell 0.8% yesterday, 63% of it from Kestrel Auto. Two items need you. First: Kestrel's CFO resigned, the second key exit in five months…"
- The frontend plays it with `speechSynthesis` (prefer an `en-IN` voice if available), with play/pause, a progress bar, and the current item highlighted. No server audio, zero cost.
- Hide the button if `speechSynthesis` is unavailable.

### 9.5 Push-to-talk voice Ask, Should

- Mic button in the Ask sheet: hold (or tap to toggle) → Web Speech API `SpeechRecognition` (`webkitSpeechRecognition` on Safari/Chrome; `lang="en-IN"`) → the transcript fills the input → the user sees it and sends.
- The answer renders on screen with citations; a speaker button reads it aloud.
- Voice only asks questions. It never changes settings or takes actions.
- Feature-detect: hide the mic where unsupported (e.g. Firefox).

### 9.6 Results calendar strip, Should

From board-meeting and concall intimation filings: a horizontal strip on the brief, "Coming up: Navami results 14 Nov · Kestrel concall 16 Nov". Tap → the company page with the prep card.

### 9.7 Share, Could

On an event or company card: the Web Share API with a clean text summary (title, metric line, impact, source link). Fall back to copy-to-clipboard.

---

## 10. LLM layer

### 10.1 Client (`llm/client.py`)

- `complete(prompt_name, tier, inputs, schema=None) -> dict|str`; `tier` is `"fast"` or `"smart"`.
- Load prompt templates from `llm/prompts/<name>.md`, each with a `version:` header.
- JSON mode/structured output where the provider supports it; otherwise parse and validate with Pydantic, retry once with the validation error appended.
- Timeouts: fast 30s, smart 60s. Retries: 2 with backoff.
- Provider adapters: gemini (default), groq, openai, anthropic. Same interface.

### 10.2 Routing

| Step | Tier | Notes |
|---|---|---|
| Filing classification leftovers | fast | rules handle most |
| Results / KMP / rating / pledge / action extraction | fast | JSON schemas |
| P2 one-liners | fast | ≤ 140 characters |
| Bio summary | fast | from the filing or search snippets |
| Promise extraction | fast | long context, one call per transcript |
| Promise "dropped" confirmation | fast | |
| Thesis pre-fill, prep question wording | fast | |
| Non-numeric promise verdicts | smart | one call per company |
| Bull vs bear | smart | structured input only |
| Ask answers | smart | retrieved chunks only |
| Arithmetic, thresholds, scoring, verdicts on numbers, audio script, suggested questions | **Python / templates** | free and exact |

### 10.3 Caching (`llm/cache.py`)

Key = `prompt_name + prompt_version + sha256(canonical inputs + model)`. Check before every call. Documents are processed once per `content_hash`. Answers to Ask are cached as in 8.7.

### 10.4 Usage and cost (`llm/usage.py`)

Log tokens and estimated cost per call. `GET /admin/usage` → totals by job and prompt, plus "cost per day for 20 companies" (put this number in the write-up). Enforce `LLM_DAILY_BUDGET_USD` for paid providers (stop non-essential calls and show a "budget reached" banner).

### 10.5 Guardrails (`llm/guard.py`)

- **Citation check:** every sentence in Pull outputs (Ask, verdict evidence, bull/bear, business) must carry a citation id that exists in the provided context. Drop sentences that don't.
- **Number check:** every number in generated text must match (after normalising units and rounding) a number in the cited chunk or in the structured inputs. Otherwise, drop the sentence or mark "unverified".
- **Grounding prompt rule:** "Use only the provided context. If the answer is not in it, say: Not found in this company's filings and transcripts. Do not use outside knowledge."
- **Banned-phrase filter** (section 2 copy rules) on all generated UI text; regenerate once if hit.
- **Facts vs context:** extraction prompts fill `facts`; `context` is computed in Python. The LLM never writes "why it matters" speculation.

---

## 11. API reference

Base path `/api`. JSON. All list endpoints return newest/highest-priority first. Pydantic models in `schemas.py`. Types are mirrored in `frontend/lib/types.ts`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | status, last ingest times, replay flag |
| GET | `/brief?window=24h\|3d\|7d\|since_last_visit&from=&to=&replay=` | section 7.7 payload |
| POST | `/brief/seen` | update `last_brief_seen_at` |
| GET | `/brief/audio-script?window=` | section 9.4 |
| GET | `/events/{id}` | full event: facts, context, enrichment, reasons, sources, last decision |
| PATCH | `/events/{id}` | `{status, dismiss_reason, thesis_tag}` |
| GET | `/portfolio` | holdings with weights, today's move, thesis health, notes |
| PATCH | `/portfolio/{symbol}` | thesis, mute, only_p0, quantity |
| GET | `/companies/{symbol}` | header, move split, weight, research status |
| GET | `/companies/{symbol}/promises` | ledger rows + scorecard |
| GET | `/companies/{symbol}/financials` | quarterly (8–12) and annual series |
| GET | `/companies/{symbol}/cash` | cash-quality card |
| GET | `/companies/{symbol}/story` | business mix + bull/bear |
| GET | `/companies/{symbol}/timeline?limit=` | events for this company |
| GET | `/companies/{symbol}/tripwires` / PUT | list / replace user tripwires |
| GET | `/companies/{symbol}/prep` | concall prep questions |
| POST | `/research/{symbol}` | start cold start; returns status |
| GET | `/research/{symbol}/status` | progress steps |
| GET | `/research/ready` | companies with ready research |
| POST | `/ask` | `{question, symbol?, event_id?}` → `{answer, citations[], suggested[]}` |
| GET | `/ask/suggested?symbol=&event_id=` | 3 template questions |
| GET/PUT | `/settings` | thresholds, tier overrides, delivery |
| GET/POST | `/decisions` | journal |
| POST | `/push/subscribe` | store a web-push subscription |
| POST | `/push/test` | send a test P0 notification |
| GET | `/notifications` | in-app inbox |
| POST | `/jobs/{name}` (token) | `ingest_filings`, `eod_prices`, `build_digest`, `docs_refresh`, `tripwires`, `snapshot` |
| GET | `/admin/usage` | LLM usage and cost |
| GET | `/sources/{kind}/{id}` | redirect/serve a cached PDF + page (for "tap to verify") |

**Event payload shape (abbreviated):**

```json
{
  "id": 412, "symbol": "XYZ", "company": "XYZ Ltd", "kind": "filing",
  "category": "kmp_change", "tier": "P0", "score": 95,
  "reasons": ["CFO exit", "2nd key exit in 5 months", "8.4% of your portfolio"],
  "title": "CFO resigns, 2nd key exit in 5 months",
  "metric_line": "−6.2% vs Nifty Auto −0.8%",
  "impact_line": "8.4% of portfolio · −₹52,100 yesterday",
  "summary": "…one line…",
  "facts": [{"k": "Stated reason", "v": "“Personal reasons”", "src": "filing p.1"}],
  "context": ["Company Secretary resigned on 14 Jun 2026", "Exit comes 7 days before the board meeting"],
  "enrichment": {"bio": {"name": "…", "lines": ["…"], "sources": ["…"]}},
  "source": {"exchange": "NSE", "url": "…", "published_at": "2026-11-09T11:12:00Z"},
  "verify_ok": true, "thesis_tag": null,
  "last_decision": {"date": "2026-06-14", "action": "hold", "note": "watch for more exits"}
}
```

---

## 12. Frontend

### 12.1 Principles

Mobile-first (design at 390×844, test at 360 and 430 widths), one-handed use, thumb-reachable primary actions, ≥ 44px touch targets. Fast: show cached data instantly (TanStack Query + service-worker cache), then refresh. Dense but calm: numbers in a monospace face, few colours, colour means something.

### 12.2 Design tokens (match the approved prototype)

```
--bg:        #F5F4EF   (warm off-white)      --surface: #FFFFFF
--ink:       #15171C   (text, dark header)   --ink-2:   #5B5F6A   --ink-3: #6B6F79
--line:      #E4E2DA   --line-2: #EFEDE6     --chip-bg: #E9E7E0
--accent:    #2A3DB0   (links, active, FINN's context)   --accent-bg: #EEF0FB
--up:        #1D6B44   --down: #B42318   --amber: #B76E00
Tier chips:  P0 bg #FCE8E6 fg #A3271B · P1 bg #FDF1D8 fg #8A5300
             P2 bg #ECEEF2 fg #3F4654 · P3 bg #F3F2EE fg #5B5F6A
Status chips: Kept #E3F2EA/#1D6B44 · Missed #FCE8E6/#A3271B · Late #FDF1D8/#8A5300
              On track #E7EBFB/#2A3DB0 · Dropped #ECEEF2/#3F4654
Fonts: Inter (UI) · Space Grotesk 700 (FINN wordmark only) · IBM Plex Mono (all numbers)
Radius: cards 16, sheets 22, chips 6, buttons 12–14
```

Provide a dark theme via `prefers-color-scheme` (bg #111317, surface #1A1D23, ink #F2F1EC, lines #2A2E36; keep chip hues, darken their backgrounds). Text contrast ≥ 4.5:1. Never use red/green alone to carry meaning: always pair with a sign (+/−) or a label.

### 12.3 Routes and navigation

Bottom nav (4 tabs): **Brief · Portfolio · Research · Alerts**. A chat icon in the top bar opens Ask from anywhere.

| Route | Screen |
|---|---|
| `/` | Brief |
| `/event/[id]` | Event detail |
| `/company/[symbol]` | Company page (tabs) |
| `/portfolio` | Holdings with thesis health |
| `/research` | Search any ticker + ready companies |
| `/alerts` | Settings: thresholds, tiers, delivery, tripwire defaults |
| `/inbox` | Notification inbox (from the bell in the top bar) |
| Ask | Bottom sheet over any route, with context |

### 12.4 Brief (home)

Top to bottom:
1. Top bar: FINN wordmark · "Tue 10 Nov · 07:30 brief" · bell (inbox count) · Ask icon.
2. **Window chips:** Since last visit (default once the user has visited before) · 24h · 3 days · 7 days · Custom (date range sheet).
3. **Portfolio header card (dark):** return %, ₹ change, attribution sentence, stacked contribution bar with a legend, "EOD close <date>". **Listen** button (audio brief).
4. **Coming up strip** (calendar): next results/concalls.
5. Counts line + **List/Swipe** toggle.
6. **Needs your attention:** P0/P1 cards (anatomy in 12.9). Tripwire hits appear here.
7. **Tripwires near limit** (if any): compact rows.
8. **Good to know:** P2 one-liners with the source and time.
9. **Routine:** dashed button "11 routine filings hidden · show" → grouped list.
10. Empty state: "Nothing needs you today. 9 routine filings hidden." (This is a feature: say it confidently.)
11. Freshness footer: "Filings checked 08:10 · Prices: EOD 9 Nov".

**Swipe mode (Could):** one card at a time, full-width; buttons Dismiss / Dig in / Seen (and swipe gestures); progress dots; "You're caught up" end state.

### 12.5 Event detail

- Back · time · tier chip · company · title · "Why this is here".
- **Exposure strip:** weight, move, your ₹ P&L.
- **Category block:**
  - Results → headline table (Metric · this quarter · QoQ · YoY), basis and unit, EBITDA definition, "verified against filing ✓" or "couldn't verify"; "Against what management promised" rows; concall date.
  - KMP → bio card (initials avatar, name, role, 2–3 background lines, sources) + cluster timeline.
  - Rating → old → new rating chips + rationale quote.
  - Pledge → before → after bar + price trend.
  - Corporate action → amount + "size vs company" figure.
  - Price/volume → move split (Nifty / sector / stock-specific) + volume ratio + "related filing" or "no filing found".
- **Facts from the filing** (white) with "Open PDF" (opens the source, at the page if known).
- **FINN's context** (blue), labelled "computed from stored filings and prices".
- **Last time you…** (decision journal), if any.
- **Your thesis** + Strengthens / No change / Weakens.
- Actions: **Open company** · **Ask about this** · Decide (Hold/Add/Trim/Exit/Note sheet) · Share.

### 12.6 Company page

- Header: symbol · exchange · sector, name, price, move, "EOD <date>"; move split card; weight and P&L (if held).
- Tabs: **Promises · Numbers · Timeline · Story** (+ a **Prep** chip when a concall is within 3 days).
- **Promises:** dark scorecard ("Delivered 2 of 5 promises that have come due" + status chips); then promise cards: metric, status chip, *verbatim quote*, "Delivered: …", citation links (tap → source page). Filter chips by status. Revisions shown as "Guidance cut: 24–25% → 22–23% (Q2 FY27 call)".
- **Numbers:** revenue bars for 8 quarters with the margin row under them (current quarter highlighted); PAT trend; cash-quality rows with flag chips and sources; tripwires section (status, current value vs limit, edit).
- **Timeline:** all events for the company, tier chip + date + one line; filter by tier.
- **Story:** revenue-mix bars, bull (green tint) and bear (red tint) lists with sources, "Built only from annual reports and concall transcripts" footnote; "Your decisions" list; thesis (editable).
- If research isn't ready: progress list (8.1 steps, live) with the honest time estimate.

### 12.7 Portfolio and Research

- **Portfolio:** "18 holdings · ₹X cr"; legend for thesis health; rows with dot, name, note (latest material event or "No events this week"), today's move, weight. Sort by weight / move / health. Long-press or a menu: mute 7 days, P0 only.
- **Research:** ticker input (uppercase, monospace) with autocomplete from known companies → Analyse → live progress → the company page. "Ready to explore" list. Short explanation line: "FINN reads the last 4 concall transcripts and the latest annual report."

### 12.8 Alerts (settings)

- **What counts as unusual:** steppers for price move % (stock-specific vs sector), volume × 20-day average, portfolio impact % (escalates to P0). Live preview: "With these settings, last 7 days would have produced N alerts."
- **Priority by event type:** P0–P3 segmented control per category (Appendix 17.2 categories).
- **Delivery:** notify only for P0 (on), show routine filings (off), brief times, quiet hours, enable push (permission flow), "Send test alert".
- **Tripwire defaults:** toggles for the standard red-flag tripwires.
- **Data:** replay mode toggle (demo), last fetch times, "Refresh now" (calls jobs with the token stored server-side; or hide in prod).

### 12.9 Card anatomy (the same everywhere)

```
[P0] Company name                                  filed 16:42 · NSE
Title in ≤ 8 words
Metric line (monospace): the one number that matters
Impact line (red/green): 8.4% of portfolio · −₹52,100 yesterday
─────────────────────────────────────────────
Why this is here: CFO exit · 2nd key exit in 5 months · 8% weight
```

### 12.10 Ask sheet

- Bottom sheet (max ~75% height), drag handle, "Context: <company · event>" line (removable chip).
- Suggested questions (3) as tappable rows.
- Conversation: user bubble (dark), answer card (white) with numbered citations; tap a citation → source viewer.
- Input row: text field + mic (push-to-talk) + send. While listening: a waveform/pulse and live transcript.
- Answer actions: read aloud, copy, "save to notes" (decision journal note).

### 12.11 Source viewer

Tapping any citation or "Open PDF" opens a sheet: document title, period, page; the PDF opened at that page (use the browser's PDF viewer via `#page=N` in a new tab as the simple version), plus the cited text excerpt highlighted in the sheet.

### 12.12 States

Every screen needs: loading skeletons (not spinners), empty states with a clear sentence, error states that keep cached data visible ("Couldn't refresh · showing data from 08:10"), and an offline banner.

### 12.13 PWA

`manifest.webmanifest` (name FINN, theme #15171C, background #F5F4EF, icons 192/512, `display: standalone`), service worker for caching the app shell + last API responses and for receiving push. An "Add to Home Screen" hint on iOS (web push on iPhone works only for home-screen web apps).

---

## 13. Notifications, scheduling, deployment, replay

### 13.1 Notifications

- On event creation with tier P0 (and the user's own threshold breaches) → web push via `pywebpush` to all subscriptions + an inbox row. Payload: title, metric line, `url: /event/{id}`.
- Respect quiet hours (P0 still allowed through if the user chooses).
- Everything else waits for the brief.
- Inbox in the app always works, even without push permission.

### 13.2 Scheduling (`.github/workflows/cron.yml`)

All times IST; GitHub cron is UTC, so convert. Each step: `curl -X POST -H "Authorization: Bearer $JOB_TOKEN" $API/jobs/<name>`.

| Job | When (IST) |
|---|---|
| `ingest_filings` | every 30 min, 09:00–20:00 (shorten to hourly if rate-limited) |
| `eod_prices` (+ price signals + tripwires) | 18:30 |
| `build_digest` | 07:30 and 19:00 |
| `docs_refresh` | daily 21:00 (new transcripts → promise ledger update) |
| `snapshot` | daily 21:30 (replay safety) |

Also the CLI: `python -m app.jobs.cli ingest --days 30`, `eod --days 60`, `research <SYMBOL>`, `snapshot --label demo`, `seed`.

### 13.3 Deployment

- **Backend** on Render or Railway (free tier) from `backend/`; start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Free instances sleep after inactivity; the cron hits wake them. Mention the possible cold-start delay in the README and show a friendly "waking up FINN…" state in the frontend if the first request is slow.
- **Postgres** on Neon/Supabase; run migrations (`alembic` or `create_all` + simple migrations) on start.
- **Frontend** on Vercel from `frontend/`; set `NEXT_PUBLIC_API_BASE`.
- CORS: allow the Vercel domain.
- Data directory: PDFs and text caches on ephemeral disk are fine (re-downloadable), but keep extracted text and results in Postgres so redeploys don't lose them.

### 13.4 If NSE blocks the cloud host

Run `python -m app.jobs.cli ingest` from the developer's laptop with `DATABASE_URL` pointing at production Postgres. Same code, same DB. Document this as a deliberate trade-off.

### 13.5 Replay mode (demo safety), Must

- `snapshot` job serialises the brief, events, the portfolio and the company pages for a window into `snapshots/<label>.json`.
- Commit one curated snapshot covering a busy recent window (results season, so it has results, KMP changes and price moves).
- `?replay=<label>` or the settings toggle serves from the snapshot. The UI shows a clear banner: **"Replay: 3–9 Nov 2026 data"**. Live mode stays the default; replay is the fallback if live data is thin or a source is blocked.
- The write-up explains this honestly.

---

## 14. Milestone plan and cut order

**Today: Thu 12 Nov (evening). Submission: Sat 15 Nov.** Commit at the end of every milestone, update `BUILD_LOG.md`, and keep the deployed app working.

| Milestone | When | Deliverables | Done when |
|---|---|---|---|
| **M0 Scaffold** | Thu night | Repo layout, FastAPI skeleton, DB models, settings, seed portfolio, yfinance EOD + indices, Next.js app with tokens, nav and a Brief page reading `/brief` with the header card | `/brief` returns a real portfolio header; frontend shows it at 390px |
| **M1 Push core** | Fri morning | NSE ingest (30 days), normalise/dedupe, rule classifier, scoring with reasons, price signals, digest with windows + routine collapse, event detail API | Brief shows real ranked events with "why this is here"; routine is collapsed; thresholds change the output |
| **M2 Showcase cards** | Fri afternoon | Results extractor with validation (+ bank variant), KMP enrichment with cluster + bio, generic one-liners, auditor/default red flags; frontend Event detail, Alerts settings | A real results filing shows a verified Rev/EBITDA/PBT/PAT QoQ/YoY table; a real KMP change shows a bio |
| **M3 Pull** | Fri night → Sat morning | screener ingest (tables + docs), transcript chunks, promise extraction, rule + LLM verdicts, scorecard, Ask with citations + guard, research cold-start UI with progress, company page (Promises, Numbers, Timeline) | A ticker never seen before goes from search → ready ledger with citations in ≤ 2–3 min |
| **M4 Workflow features** | Sat midday | Cash card, Story (business + bull/bear), tripwires, thesis tags, decision journal, audio brief, voice Ask, calendar strip, concall prep, web push + inbox | Each feature works on a phone |
| **M5 Ship** | Sat afternoon | Deploy all three parts, cron, snapshot + replay, Playwright mobile smoke test, README + `docs/WRITEUP.md`, usage/cost numbers, test on a real phone, random-ticker test | Checklist 15.3 passes |

**Cut order if behind (cut from the top first):** Telegram → share → swipe mode → BSE fallback → concall prep → calendar strip → decision journal → voice Ask → audio brief → web push (keep the inbox) → story/bull-bear → cash card → tripwires. **Never cut:** brief + ranking, results card, KMP card, configurable thresholds, promise ledger, Ask with citations, deployment, replay.

---

## 15. Testing and verification

### 15.1 Unit tests (pytest)

- `fiscal.py`: quarter labels, prev/year-ago, parsing.
- `rules.py`: ≥ 30 real subject lines → expected categories (fixtures from live NSE data).
- `score.py`: every escalator/dampener; user override; mute.
- `price_signals.py`: synthetic series → expected events; sector fallback.
- `results.py`: 3–5 real results PDFs in `tests/fixtures` (include one bank) → expected numbers; validation failure path.
- `verdict.py`: numeric verdict rules on synthetic financials.
- `guard.py`: drops uncited sentences; catches a changed number.
- `digest.py`: window filters, routine grouping, since-last-visit.

### 15.2 Integration

- `cli ingest --days 7` on 3 holdings against live NSE (skippable in CI with a flag).
- `cli research <SYMBOL>` for one demo company and one random company.
- API contract tests: every endpoint returns the schema.

### 15.3 Pre-submission checklist

- [ ] Deployed frontend opens on a phone in < 3s after warm-up; no horizontal scroll at 360px.
- [ ] Brief shows ranked events for 24h / 7d / custom; routine collapsed; header attribution correct (check one stock by hand).
- [ ] One results card verified by hand against the PDF (all 4 metrics, QoQ, YoY).
- [ ] One KMP card with a bio and sources.
- [ ] Changing the price threshold changes the alerts.
- [ ] Research works for a ticker not in the seed list (try 2).
- [ ] Every Pull sentence has a working citation; "not found" path works.
- [ ] Replay banner works; live mode is the default.
- [ ] Push test notification arrives on Android Chrome (or the inbox shows it).
- [ ] Voice and Listen hidden gracefully where unsupported.
- [ ] `/admin/usage` shows cost; number copied into the write-up.
- [ ] No secrets in the repo; `.env.example` complete; README has run + deploy steps.
- [ ] Playwright mobile smoke test passes (Brief → event → company → Ask).

---

## 16. Submission

**Email to:** assessment@enam.com · **Subject:** `IIT Delhi – AI Engineer - 2027`

Include:
1. **Deployed link** (Vercel), plus "Add to Home Screen for push on iPhone" note.
2. **GitHub repo** link.
3. **AI build history:** exports/share links of the Claude conversations (planning chat + Claude Code sessions) and `BUILD_LOG.md`.
4. **Write-up** (draft it in `docs/WRITEUP.md`, paste into the email; ~1 page):
   - **What I built:** the one-line point of view; Push (brief, ranking, results/KMP cards, thresholds, tripwires); Pull (any-ticker promise ledger with citations, Ask); daily-workflow features (Listen, voice, prep, journal).
   - **Key decisions and trade-offs:** interrupt only on P0 (cite the alert/overtrading research); rules before LLM (X% classified at zero cost); cheap vs strong model routing; numbers in Python, never in the LLM; verify-or-hide for extracted numbers; screener tables for numbers + documents for narrative; PWA over native; replay mode; laptop ingestion if NSE blocks cloud IPs.
   - **Cost:** tokens and ₹/$ per day for 20 companies; caching hit rate.
   - **Deliberately left out:** real-time data, valuation, news/broker data, multi-user, native widgets, Hinglish voice.
   - **Next:** team mode (shared notes/decisions), licensed data feed, insider/bulk-deal signals, native widget, Hinglish voice, learning the user's dismissals into scores.

---

## 17. Appendices

### 17.1 Classifier rules (starting set; tune on live data)

Match on NSE's category text (`desc`) **and** the subject (`attchmntText`), case-insensitive, in this order. **VERIFY the exact NSE category strings on live data and extend.**

| # | Category | Patterns (regex, any) | Base tier |
|---|---|---|---|
| 1 | auditor_change | `resignation of (the )?(statutory )?auditor`, `auditor.*resign` | P0 |
| 2 | default | `default`, `delay in (payment|servicing)`, `non-payment of (interest|principal)` | P0 |
| 3 | kmp_change | `resignation`, `cessation`, `appointment of .*(chief|cfo|ceo|managing director|company secretary|compliance officer|whole[- ]time director|director)`, `change in (directors|key managerial personnel|kmp)` | by role (7.4.2) |
| 4 | results | `financial results?`, `outcome of board meeting.*(result|financial)`, `integrated filing.*financial`, `unaudited|audited.*results` | P1 |
| 5 | rating | `credit rating`, `rating (action|reaffirm|upgrade|downgrade)` | by direction |
| 6 | pledge_sast | `pledge`, `encumbrance`, `regulation 31`, `sast`, `takeover regulations` | P1 |
| 7 | insider | `regulation 7\(2\)`, `insider trading`, `pit regulations` | P2 |
| 8 | mna | `acquisition`, `amalgamation`, `merger`, `demerger`, `scheme of arrangement`, `divest`, `sale of (stake|undertaking)` | P1 |
| 9 | fundraise | `qip`, `qualified institutions placement`, `rights issue`, `preferential (issue|allotment)`, `warrants`, `non-convertible debentures|ncd`, `commercial paper` | P1 |
| 10 | buyback | `buy[- ]?back` | P1 |
| 11 | order_win | `order (win|received|bagged)`, `bags (an )?order`, `letter of award`, `contract (award|win)` | P2 |
| 12 | capex | `capacity expansion`, `capex`, `commissioning`, `new plant`, `greenfield|brownfield` | P2 |
| 13 | litigation | `litigation`, `show cause`, `penalty`, `tax demand`, `order (from|of|by) .*(sebi|rbi|court|tribunal|gst)` | P2 |
| 14 | clarification | `clarification`, `spurt in (price|volume)`, `price movement` | attach to price event |
| 15 | concall_doc | `transcript`, `analyst.*(meet|call)`, `investor (meet|presentation)`, `earnings call`, `con\.? ?call` | P2 (triggers docs refresh) |
| 16 | dividend_corp | `dividend`, `bonus`, `split|sub-division`, `record date` | P2 |
| 17 | board_meeting | `board meeting (intimation|to be held)`, `prior intimation` | P3 (feeds calendar) |
| 18 | routine | `trading window`, `newspaper (publication|advertisement)`, `duplicate share certificate`, `loss of share certificate`, `74\(5\)`, `esop allotment|allotment under esop`, `compliance certificate`, `shareholding pattern` | P3 |
| 19 | other | (no match → LLM) | P2 |

### 17.2 Priority matrix (defaults; `*` = suggested thresholds to tune)

| Event | Default | Escalate when | De-escalate when |
|---|---|---|---|
| Auditor resignation | P0 | always | never |
| Default / payment delay | P0 | always | never |
| CEO / MD / CFO resignation | P0 | cluster; within 30 days of results* | planned retirement with successor → P1 |
| CEO / CFO appointment | P1 | outsider replacing an abrupt exit | pre-announced succession → P2 |
| CS / other KMP change | P2 | part of a cluster → P1 | |
| Quarterly results | P1 | \|PAT YoY\| > 20%* or margin > 3pt off guidance* → P0 | |
| Rating downgrade | P1 | lender/NBFC or D/E > 1* → P0 | |
| Rating upgrade / reaffirmed | P2 / P3 | | |
| Promoter pledge up | P1 | crosses 40%*, or rising while the price falls → P0 | pledge released → P2 |
| Promoter/insider sale | P1 | > 1% of equity* → P0 | < 0.1%* → P2 |
| Promoter/insider purchase | P2 | > 0.5%* → P1 | |
| M&A / scheme | P1 | > 10% of market cap* → P0 | |
| Fund-raise | P1 | dilution > 10%* → P0 | small debt (< 5% of net worth*) → P2 |
| Order win | P2 | > 10% of FY revenue* → P1 | |
| Capex | P2 | > 25% of gross block/net worth* → P1 | |
| Litigation / regulatory | P2 | > 5% of net worth* or SEBI/RBI action → P1 | |
| Buyback | P1 | | |
| Dividend / bonus / split | P2 | | |
| Concall doc / presentation | P2 | | |
| Board meeting intimation | P3 | | |
| Routine compliance | P3 | | |
| Stock-specific move ≥ price_pct | P1 | portfolio impact ≥ impact_pct → P0 | |
| Volume ≥ volume_x | P2 | no filing in 48h → P1 ("unexplained") | |
| Tripwire hit | P0 | | user may set P1 per tripwire |

### 17.3 Prompt templates (each a file in `llm/prompts/`, with a `version:` header)

**Shared system preamble (all extraction prompts):**
> You extract facts from Indian stock-exchange filings and company documents. Use only the text provided. Copy numbers exactly as written, with their units. If a field is not present, return null. Do not infer, estimate or add outside knowledge. Return only JSON matching the schema.

**`classify_filing` (fast):** input: category text, subject, first 1,500 characters of the PDF. Output `{category: <one of list>, confidence: 0–1}`.

**`results_extract` (fast):** input: text of the first ~8 pages. Instruction: "Find the statement of financial results. Identify the columns for the current quarter, the immediately preceding quarter, and the corresponding quarter of the previous year. Prefer the consolidated statement if both exist." Output: schema 17.4.

**`kmp_extract` (fast):** output `{person, role, change, reason_stated, effective_date, successor: {name, role, interim}, profile_text}`; `reason_stated` must be verbatim.

**`bio_summarise` (fast):** input: profile text and/or ≤ 3 search snippets with URLs. Output ≤ 3 lines: "Role, Company (years)", qualifications; each with its source URL. "If the snippets may refer to a different person with the same name, return null."

**`one_liner` (fast):** "Write one line, at most 140 characters, starting with the key number or fact. No adjectives. No 'the company'." + banned list.

**`promise_extract` (fast):** "List every explicit forward-looking commitment made by management in this transcript about growth, margins, capex, debt, volumes, capacity or plant timelines, product launches or market share. Include only statements with a number, a range or a date. Copy the quote verbatim. Give the page and the speaker. Do not include analyst statements." Output: schema 17.4.

**`promise_dropped_check` (fast):** input: promise + BM25 top chunks from the latest 2 transcripts. Output `{mentioned: bool, quote|null, page|null}`.

**`promise_judge` (smart):** input: non-numeric promises + evidence chunks with ids. Output per promise `{status, actual_text, citations: [chunk_id]}`. "If evidence is insufficient, status = pending."

**`bullbear` (smart):** input: structured cards only. "Write 3 bull and 3 bear points, each ≤ 120 characters, each citing the input field id it came from. Use no fact that is not in the input."

**`ask_answer` (smart):** input: question, context label, numbered chunks, structured rows. "Answer in at most 120 words. End every sentence with citation markers like [1]. Use only the numbered sources. If they don't contain the answer, reply exactly: Not found in this company's filings and transcripts."

**`thesis_prefill` (fast):** input: opening remarks of the latest transcript + top promises. Output ≤ 2 lines of the investment case as management states it, with citations.

**`prep_wording` (fast):** input: templated question drafts. Output the same questions made concise (≤ 25 words), no new facts.

### 17.4 JSON schemas (Pydantic)

```python
class ResultsColumn(BaseModel):
    label: str                      # e.g. "Quarter ended 30.09.2026"
    revenue: float | None           # revenue from operations
    other_income: float | None
    total_expenses: float | None
    finance_costs: float | None
    depreciation: float | None
    exceptional_items: float | None
    pbt: float | None
    tax: float | None
    pat: float | None
    # banks
    interest_earned: float | None
    operating_profit: float | None
    provisions: float | None

class ResultsExtract(BaseModel):
    basis: Literal["consolidated", "standalone"]
    unit: Literal["lakh", "crore", "million", "thousand"]
    is_bank_format: bool
    current: ResultsColumn
    previous_quarter: ResultsColumn
    year_ago_quarter: ResultsColumn
    page: int | None

class Promise(BaseModel):
    metric: str
    metric_key: Literal["revenue_growth","ebitda_margin","pat_growth","capex",
                        "net_debt","volume","plant","launch","market_share","other"]
    target_text: str
    target_low: float | None
    target_high: float | None
    unit: str | None                # "%", "₹ crore", "MT", ...
    horizon: str                    # "FY27", "Q1 FY27", "by March 2027"
    quote: str                      # verbatim
    page: int | None
    speaker: str | None

class PromiseExtract(BaseModel):
    period_label: str               # transcript quarter, e.g. "Q4 FY26"
    promises: list[Promise]

class AskAnswer(BaseModel):
    answer: str
    citations: list[int]            # chunk ids used
    found: bool
```

### 17.5 Seed portfolio (starting suggestion, validate before use)

18 holdings, about ₹1 crore total, weights 3–10%, mixed sectors and sizes. **Before finalising, run a "scout" script:** fetch the last 30 days of announcements for ~40 liquid NSE names and pick the 18 that give the richest demo (at least one results filing, one KMP change, one rating action, one pledge/insider item, one large price move), while keeping the sector mix. Validate every ticker with yfinance.

Starting list (sector): HDFCBANK (bank), ICICIBANK (bank), BAJFINANCE (NBFC), INFY (IT), TCS (IT), SUNPHARMA (pharma), DRREDDY (pharma), HINDUNILVR (FMCG), ITC (FMCG), NESTLEIND (FMCG), MARUTI (auto), M&M (auto), LT (infra), ULTRACEMCO (cement), TITAN (consumer), ASIANPAINT (consumer), plus 2 mid/small caps chosen by the scout for event richness.

Research demo set (3–5, outside the portfolio): choose by the scout, preferring companies with 4 recent transcripts on screener.in and clear numeric guidance (e.g. a consumer, an industrial and a pharma name).

`seed/portfolio.yaml` format:

```yaml
holdings:
  - symbol: HDFCBANK
    name: HDFC Bank
    sector: Banks
    sector_index: ^NSEBANK
    bse_code: "500180"        # VERIFY
    quantity: 600
    avg_cost: 1550
research:
  - symbol: PIDILITIND
```

### 17.6 `CLAUDE.md` (create at the repo root)

```markdown
# FINN — working rules for Claude Code
- The spec is FINN_BUILD_SPEC.md. Follow its milestone order (section 14) and cut order.
- Keep the app runnable after every milestone; commit with a clear message per milestone.
- Log decisions and surprises in BUILD_LOG.md (date, what, why).
- Never hard-code demo companies into logic. Research must work for any NSE ticker.
- Numbers are computed in Python; the LLM extracts and words, never calculates.
- Every Pull sentence needs a citation; unverified numbers are hidden, not guessed.
- VERIFY live endpoints/HTML before coding parsers; keep raw responses as test fixtures.
- Ask the user before creating accounts, spending money or changing the scope.
- Mobile-first: check every screen at 390×844.
```
