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

## 2026-11-13: deployment, cron moved onto GitHub runners
- Deployed: Render (API), Vercel (frontend), Neon (Postgres). Local finn.db copied into Neon with a one-off pg8000 script (laptop Application Control blocks psycopg's DLL).
- Surprise: `eod_prices` triggered on Render hung for 17+ min with no result (same job: 11 s on the laptop; Yahoo answers the laptop in 0.5 s). Yahoo throttles Render's IPs, and the background-thread design hid it: GitHub showed green, the job_run row stayed "running".
- Decision: cron runs jobs directly on the GitHub runner against Neon (`python -m app.jobs.cli job <name>`), so pass/fail and logs are real. Repo variable `CRON_MODE=render` restores the old POST-to-Render path; `snapshot` always runs on Render (it writes a file that Render serves).
- Hardening: Yahoo requests time out after 15 s (was 45 s); a failed job is recorded from a fresh DB session; runs still unfinished after 2 h are closed as "Did not finish".
- Correction (same day): the slowness was not Yahoo. One `eod_prices` run made 6,259 DB queries (a select per stored price row, plus price signals re-evaluated for 25 sessions). Fine on local SQLite (11 s); against Neon in Singapore from a US host (~0.2 s per round trip) that is ~20 min, matching Render's 18.5 min run. Fix: one select per symbol in `prices.store`, and daily runs re-evaluate signals for 5 sessions (25 on an empty DB and in bootstrap). Now 706 queries, same output.

## 2026-11-13: urgent alerts reach the user on every path
- Gap found after deploy: only urgent filings notified. Urgent price moves and new tripwire hits were stored as P0 events but never sent; no device had subscribed, so nothing reached a phone.
- Now: new tripwire hits and P0 price/volume/sector events (latest session only, so backfill never floods) call `notify_event`. Dedupe stays one notification per event.
- Telegram added as a second channel (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`). Inbox row always; Web Push and Telegram are independent, so either one failing never blocks the other. `channel` is inbox / webpush / telegram / both (column is 10 chars).
- Verified on a DB copy with faked senders: tripwire hit, price P0, no duplicates on re-run, each channel down in turn.

## 2026-11-13: slow Alerts page on the deployed app
- Surprise: `GET /api/settings` took 77 s on Render (439 queries at ~175 ms each: Render is far from Neon Singapore). Every checkbox waited for the same payload, because it re-ran the week-of-alerts preview.
- Fix: `portfolio._closes` loads each key's price history once per DB session (`prices.store` clears it); a save that does not move a threshold skips the preview; the Alerts page flips controls at once and rolls back on error.
- Queries: settings 439 -> 93, checkbox save 439 -> 1, portfolio 151 -> 105, brief 50 -> 31, eod job 706 -> 348. Responses byte-identical apart from the current-time window.

## 2026-11-14: research parser, theme on refresh, check-in message
- Research tab failed on the deployed app with "Couldn't find a tree builder ... lxml": `sources/screener.py` parses with lxml, which was installed on the laptop but missing from requirements.txt. Added `lxml>=5.0`.
- Theme "changing on refresh": page colours were right, but the browser chrome (status bar, address bar, pull-to-refresh) followed the phone, not the saved choice. Patching Next's theme-color metas failed: React re-inserts a meta whose content changed after hydration. Now `lib/theme.ts` creates the theme-color metas itself before first paint and on every picker change. Checked with Playwright at 390 px: phone light/dark x saved none/light/dark, across reloads and tab switches, and the picker; 0 failures, 0 hydration errors.
- Check-in: a portfolio summary (value, day change, biggest moves, tripwires hit, urgent count, filings freshness) to the inbox, phone push and Telegram after scheduled ingest/eod runs, at most every CHECKIN_HOURS (repo variable, default 2, 0 = off), never in quiet hours. Run workflow > checkin sends one now. Proves the channels work on quiet days. Numbers from portfolio.book/move_on, so they match the Portfolio page.
