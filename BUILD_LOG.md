# Build log

## 12 Nov 2026, evening: M0–M3 backend
- Seed portfolio picked with `scripts/scout.py` for a demo-rich mix (results, KMP changes, ratings, large moves).
- Prices from Yahoo's chart endpoint (same data as yfinance) in parallel; sector indices fall back to Nifty when missing.
- NSE ingest with session warm-up; rule classifier with 19 categories. Bootstrap: 370 filings, 360 events, about 82% classified by rules.
- Results enrichment: Python parser first, LLM fallback, both validated against the PDF and screener.in before any number is shown.
- Pull: screener tables and documents, speaker-aware transcript chunks, BM25 (no embedding cost), promise extraction (LLM, or keyword rules without a key), verdicts computed in Python.

## 13 Nov 2026: API, Ask, replay, frontend
- API routers for spec section 11, plus a settings preview ("last 5 sessions would have produced N alerts") and tier overrides that keep the computed tier so a reset restores it.
- Ask works without an LLM key: it picks extractive sentences from the BM25 passages, and the same citation and number guard runs over them. Generic question words ("management", "guide") are down-weighted so a passing mention doesn't win.
- Replay is generic: the snapshot job records the API's own GET responses, and a middleware serves them with an `X-Finn-Replay` banner header. No per-endpoint replay code.
- Jobs run in a background thread behind a bearer token, so cron calls return at once.
- Frontend follows FINN_DESIGN_SYSTEM.md: ledger rows instead of cards, IBM Plex in three voices, and the highlighter only on verbatim source text. Urgency is shown as words ("Urgent", "Today"), not P0 chips.
- Taste check: with the logo removed, FINN is still recognisable by the serif quotes on the highlighter. Removed: coloured status pills on promises (verdicts are now words with weight).
- Verified: 24 backend tests pass; Playwright mobile smoke test passes at 390 px light, 390 px dark and 360 px with no horizontal scroll; replay snapshot of 599 responses served correctly.
- Pending (human prerequisites, left blank on purpose): LLM key, web-search key, VAPID keys, GitHub repo, Render, Vercel, Neon accounts.
