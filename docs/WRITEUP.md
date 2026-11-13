# FINN: covering note (draft)

> Fields marked **[TO FILL]** need the deployed link, accounts or measured numbers. They are left blank until those exist.

**Deployed app:** [TO FILL: Vercel link]. On iPhone, add it to the Home Screen to receive push.
**Repo:** [TO FILL: GitHub link]
**AI build history:** [TO FILL: Claude conversation share links] plus `BUILD_LOG.md`.

## What I built

*FINN interrupts you only when your thesis might be broken. Everything else waits for a batched brief, and every claim links to its source.*

- **Push.** A windowed brief (since last visit, 24h, 3 days, 7 days, custom) of NSE filings and EOD price moves for an 18-stock book. Items are ranked by a priority matrix and each shows "why this is here". Routine filings are counted, not shown. Results cards give Revenue / EBITDA / PBT / PAT with QoQ and YoY, and appear only when the numbers pass validation against the PDF. Management-change cards include the stated reason (quoted), the successor, a cluster check ("2nd key exit in 5 months") and a bio. Price, volume and impact thresholds are configurable with a live "how many alerts would this have produced" preview. Every event type can be overridden to urgent / today / FYI / routine.
- **Pull.** Any NSE ticker: FINN reads the last 4 concall transcripts and the latest annual report and builds a **promise ledger**: each forward-looking commitment, quoted verbatim with its page, judged kept / missed / late / on track / behind / dropped against reported numbers. Cash quality, the business mix, bull vs bear and **Ask** are all cited. Ask drops any sentence without a valid citation or with a number the source doesn't contain.
- **Daily workflow.** Tripwires (pre-set sell-review triggers), thesis tags on events, a decision journal that reminds you "last time you held…", a spoken brief (Listen), push-to-talk Ask, a results calendar, concall prep questions, and web push for urgent items only, with an inbox fallback.

## Key decisions and trade-offs

- **Interrupt only on urgent items.** Research on alerts and over-trading says one-by-one pings increase trading and hurt returns. Everything below urgent waits for the brief.
- **Rules before the LLM.** About 82% of filings are classified by regex rules at zero LLM cost (bootstrap run, 370 filings). Results tables are parsed in Python first; the LLM is a fallback.
- **Numbers in Python, never in the LLM.** The LLM extracts and words. Arithmetic, scoring, verdicts on numeric promises, the audio script and suggested questions are all code.
- **Verify or hide.** An extracted number is shown only if it appears in the PDF and the P&L ties out (PBT − tax ≈ PAT, cross-checked with screener.in). Otherwise the card says "couldn't verify" and links the PDF.
- **Grounding.** Numbers come from screener.in tables (compiled from filings) and results PDFs. Narrative comes only from transcripts and annual reports. No news, broker notes or model memory.
- **Cheap vs strong routing.** A fast model handles extraction; a smart model is used only for Ask, bull vs bear and non-numeric verdicts. All calls are cached by prompt version and input hash, with a daily budget cap.
- **PWA over native.** One link that opens on any phone, with push, offline cache and voice from browser APIs at zero cost.
- **Replay mode.** A recorded window keeps the demo alive if NSE blocks the cloud host. It is clearly bannered, and live mode is the default.
- **Laptop ingestion.** If NSE blocks datacenter IPs, the same CLI runs from a laptop against the production database.

## Cost

- LLM provider and models: [TO FILL]
- Cost per day for 20 companies: [TO FILL from `GET /api/admin/usage` → `cost_per_day_per_20_companies_usd`]
- Cache hit rate: [TO FILL]
- Without a key the app runs on rules and templates at ₹0.

## Deliberately left out

Real-time prices and intraday alerts, valuation models, news and broker data, multi-user accounts, native widgets, Hinglish voice.

## Next

Team mode (shared notes and decisions), a licensed data feed, insider and bulk-deal signals, a native widget, Hinglish voice, and learning from the user's dismissals to tune scores.
