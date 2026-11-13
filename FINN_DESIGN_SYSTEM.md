# FINN Design System: How FINN Should Look, and How to Avoid the "AI-Generated" Look

> **For Claude Code.** This file overrides section 12.2 (design tokens) of `FINN_BUILD_SPEC.md`. Everything else in section 12 (screens, flows, states) still applies. Read this before writing any frontend code, and run the review gate in section 9 before every frontend commit.

---

## 1. Why this file exists

The brief says: *"No AI slop … feel like a product someone thought hard about, not a model filling a template. Density and design both count."* Reviewers have seen hundreds of AI-built UIs, and those UIs share recognisable defaults. Design critics list the common ones: Inter as the only typeface, indigo-to-purple gradients, rows of identical rounded cards with soft shadows, generic thin-line icons and weightless copy ([925 Studios](https://www.925studios.co/blog/ai-slop-design-tells)); cards nested in cards, status dots with no defined meaning, and a different accent colour on every block ([Fountain Institute](https://www.thefountaininstitute.com/blog/signs-vibe-coded-ui)); Title Case everywhere, uniform border radius, fade-up animation on every element, and emoji as icons ([Anti-AI-slop ban list](https://github.com/Laith0003/ux-skill/wiki/Anti-AI-slop-ban-list)). Anthropic's own frontend-design guidance adds: a warm cream background with a terracotta accent, near-black with one acid accent, all-caps eyebrow labels over every heading, meta strings joined with middle dots, monospace for small data labels, and "→" appended to buttons.

**The first prototype hit several of these** (cream `#F5F4EF` ground, IBM Plex Mono data labels, ALL-CAPS section labels, "A · B · C" meta strings, "Seen →", every item in an identical rounded card). This file replaces that look.

---

## 2. The concept: "the marked-up filing"

Fundamental investors work by **reading primary documents and marking them up**: highlighting the line that matters in a results PDF, writing a note in the margin, keeping a ledger of what management said. FINN does that reading for them. The design borrows from that world, not from SaaS dashboards:

- **Ledger paper:** a cool grey-green ground with ruled rows, not cards.
- **Blue-black ink:** the text colour of a fountain pen, not a tinted near-black.
- **Highlighter:** the one bold element. It marks **verbatim words from a source document** (a management quote, the key line in a filing). Nothing else is ever highlighted.
- **Two voices, two typefaces:** FINN speaks in a sans; **documents speak in a serif**. The investor can tell at a glance which words came from the company and which from FINN. This is the "facts vs interpretation" rule (spec section 2) made visual.

**Spend boldness in one place:** the highlighter. Everything else is quiet, dense and disciplined.

---

## 3. Colour tokens

All text pairs below were checked for contrast (WCAG AA needs 4.5:1 for body text).

### Light (default)

| Token | Hex | Use | Contrast |
|---|---|---|---|
| `--paper` | `#E6EBE7` | App ground (ledger paper, cool grey-green) | — |
| `--sheet` | `#FBFCFA` | Raised surfaces: the brief sheet, event sheet, inputs | — |
| `--ink` | `#18202E` | Primary text, the dark portfolio header | 13.5 on paper · 15.9 on sheet |
| `--ink-2` | `#4A5463` | Secondary text | 6.4 on paper |
| `--ink-3` | `#5E6876` | Tertiary text (timestamps, sources) | 4.7 on paper · 5.5 on sheet |
| `--rule` | `#C9D2CC` | Ledger rules between rows | — |
| `--link` | `#1F3FA6` | Links, active tab, focus ring, interactive only | 8.8 on sheet |
| `--mark` | `#EEF078` | Highlighter behind source quotes and the key filing line | ink on it: 13.5 |
| `--up` | `#17703F` | Positive changes (always with "+") | 6.0 on sheet |
| `--down` | `#B3261E` | Negative changes (always with "−"); urgent tag | 6.4 on sheet; white on it 6.5 |

### Dark (`prefers-color-scheme: dark`, and a manual toggle)

| Token | Hex | Notes |
|---|---|---|
| `--paper` | `#12171F` | Ink-blue night, not neutral black |
| `--sheet` | `#1B222C` | |
| `--ink` | `#E9ECEA` | 15.1 on paper |
| `--ink-2` / `--ink-3` | `#A9B2BD` | 7.5 on sheet |
| `--rule` | `#2C3541` | |
| `--link` | `#8FB0FF` | 7.5 on sheet |
| `--mark` | `#C9C65A` with `--ink` set to `#12171F` on top | a dimmer highlighter; text on it 10.0 |
| `--up` | `#5BC28A` | 7.3 on sheet |
| `--down` | `#FF8A80` | 7.0 on sheet |

### Colour rules

1. **Colour always means something.** Red = down or urgent. Green = up. Blue = you can tap it. Yellow = words copied from a source document. No other colours exist in the UI.
2. **Never colour alone:** every change carries a sign (`+2.1%`, `−6.2%`); urgency carries a word ("Urgent").
3. No gradients, glows, glassmorphism or decorative shadows. Depth comes from `--paper` vs `--sheet` and one shadow used only on sheets that float over content (bottom sheets): `0 -8px 24px rgba(24,32,46,0.12)`.
4. Status colours on promise verdicts use **text + weight**, not a rainbow of chips (section 6.4).

---

## 4. Typography

One superfamily, three voices: **IBM Plex** (Google Fonts, free).

| Voice | Face | Where |
|---|---|---|
| FINN's voice | **IBM Plex Sans** 400/500/600 | All UI text, FINN's context, summaries |
| Numbers | **IBM Plex Sans Condensed** 500/600 with `font-variant-numeric: tabular-nums` | Every figure: prices, %, ₹, tables, the header number. Condensed width lets dense number rows fit on a phone; tabular figures keep columns aligned |
| The document's voice | **IBM Plex Serif** italic 400 | Verbatim quotes from filings and transcripts only, always on the highlighter |

- **No monospace anywhere.** Tabular figures do the alignment job without the "terminal" look.
- **VERIFY** `tnum` works in the loaded Plex files (check a column of `1,111` and `8,888` aligns). If it doesn't, keep Plex Sans Condensed but right-align numbers in fixed-width cells.
- Load only the weights listed (performance).

### Type scale (mobile, 16px base, ratio ~1.2)

| Role | Size / line-height | Weight | Notes |
|---|---|---|---|
| Hero number (portfolio move) | 40/44 Condensed | 600 | The one big number on the brief |
| Screen title | 24/30 | 600 | Sentence case |
| Item title | 17/23 | 600 | ≤ 8 words |
| Body | 15/22 | 400 | |
| Quote (serif italic) | 15/24 | 400 | Slightly more line-height for the serif |
| Secondary | 13/18 | 400–500 | |
| Small (time, source) | 12/16 | 400 | Never smaller than 12 |

### Typographic rules

- **Sentence case everywhere.** No ALL-CAPS labels, no letter-spaced eyebrows above headings. Section labels are 13px weight 600 in `--ink-2`, sentence case ("Needs you today").
- No single highlighted or coloured word inside a headline.
- Line length ≤ 70 characters for body text.
- Separate metadata with layout (two lines, or left/right alignment), not with middle dots. Write "Filed 16:42, NSE" (comma) when it must be inline.
- No "→" on buttons or links. The label says what happens ("Open company", "Ask about this").

---

## 5. Layout: the ledger, not a card grid

### 5.1 Principles

- **Rows on a sheet, not cards on a page.** The brief is one `--sheet` surface with full-width rows separated by `--rule` lines, like a ledger. Cards (separate rounded surfaces) are used only for things the user acts on independently: the portfolio header, a bottom sheet, the Ask answer.
- **A margin column** on the left of every row (48px) holds the time and the urgency mark, like the date column of a ledger. Content aligns to one left edge; everything is left-aligned, never centred.
- **Hierarchy by weight and position, not by boxes.** Urgent items get more text and a solid tag; FYI items are one line; routine items are a count.
- **Radius has a hierarchy:** sheets 20px (top corners only for bottom sheets), the portfolio header 14px, buttons and inputs 10px, tags 4px, rows 0. Never one radius on everything.
- Spacing scale: 4, 8, 12, 16, 24, 32. Side gutter 16px.

### 5.2 Brief (home), wireframe

```
┌──────────────────────────────────────┐
│ FINN                       [bell][ask]│  wordmark: Plex Sans Condensed 600, 20px
│ Tuesday 10 November, morning brief    │  13px ink-2
│ [Since last visit] [24h] [7 days] [..]│  segmented control, not pills soup
│ ┌──────────────────────────────────┐ │
│ │ −0.82%           −₹82,400         │ │  ink header (dark), hero number
│ │ Kestrel Auto caused 63% of it.    │ │
│ │ Nifty fell 0.31%.                 │ │
│ │ ████████████▒▒▒░░░░░░            │ │  contributor bar, labelled below
│ │ Kestrel −52.1k  Meru −9.7k  Others│ │
│ │ [Listen, 1 min]   EOD close 9 Nov │ │
│ └──────────────────────────────────┘ │
│ Coming up   Navami results Fri 14 Nov │  one quiet line, scrolls horizontally
│                                      │
│ Needs you today (3)                  │  13px 600 ink-2, sentence case
│ ┌ sheet ─────────────────────────────┐
│ │16:42 │ [Urgent] Kestrel Auto        │
│ │      │ CFO resigns, second key exit │  17px 600
│ │      │ in five months               │
│ │      │ −6.2%  vs Nifty Auto −0.8%   │  condensed numbers, down colour
│ │      │ 8.4% of your book, −₹52,100  │
│ │      │ Why: CFO exit, earlier CS    │  13px ink-3
│ │      │ exit in June, large holding  │
│ ├──────┼─────────────────────────────┤  ledger rule
│ │15:10 │ [Today] Navami Pharma        │
│ │      │ Q2 margin 21.8%, below the   │
│ │      │ 24–25% guided                │
│ │      │ ...                          │
│ └──────┴─────────────────────────────┘
│ For your information (4)             │
│ ┌ sheet ─────────────────────────────┐
│ │14:20 │ Sahyadri Cement: ₹420 cr order, about 9% of FY26 revenue
│ ├──────┼─────────────────────────────┤
│ │12:05 │ Tarang Fintech: AA− reaffirmed
│ └──────┴─────────────────────────────┘
│ 11 routine filings hidden   [Show]   │  plain text + button, no dashed box
│                                      │
│ Checked filings 08:10. Prices EOD 9 Nov.
├──────────────────────────────────────┤
│ Brief   Portfolio   Research   Alerts │  icons + labels, active = ink + 2px bar
└──────────────────────────────────────┘
```

### 5.3 Event detail, wireframe

```
│ ‹ Brief                       16:42   │
│ [Urgent] Kestrel Auto                 │
│ CFO resigns, second key exit in five  │  24px title
│ months                                │
│ Why: CFO exit, earlier CS exit, 8%    │
│                                       │
│ Weight 8.4%   Yesterday −6.2%   −₹52.1k│  three figures in one ruled row
│ ───────────────────────────────────── │
│ From the filing                Open PDF│  section label + link
│ ▌"I am stepping down for personal    ▐│  serif italic on highlighter
│ ▌ reasons, effective 30 November."   ▐│
│ Who        Rohan Mehta, CFO since 2021│  label/value rows, ruled
│ Successor  Anita Rao (interim)        │
│ ───────────────────────────────────── │
│ What FINN noticed                     │  sans, no box, no highlight
│ The Company Secretary resigned on 14 Jun.
│ The exit comes 7 days before results. │
│ −5.4% of the move is stock-specific.  │
│ ───────────────────────────────────── │
│ Anita Rao                             │  bio: name + 3 lines + sources
│ Deputy CFO, Kestrel Auto, 2023–now    │
│ ...                                   │
│ ───────────────────────────────────── │
│ Last time (14 Jun) you held: "watch   │
│ for more exits"                       │
│ Does this change your thesis?         │
│ [Strengthens] [No change] [Weakens]   │  segmented control
│                                       │
│ [Open company]      [Ask about this]  │  one primary (ink fill), one secondary
```

**Note the separation:** "From the filing" = serif on the highlighter. "What FINN noticed" = plain sans. No blue box needed; the typefaces do the work.

---

## 6. Components

### 6.1 Urgency marks (replace P0–P3 chips)

Users never see "P0". They see words, with hierarchy shown by weight:

| Internal | User label | Treatment |
|---|---|---|
| P0 | **Urgent** | Solid `--down` tag, white text, 12px 600, radius 4 |
| P1 | **Today** | 1px `--ink` outline tag, ink text |
| P2 | (none) | No tag; a single row in "For your information" |
| P3 | (none) | Counted in "routine filings hidden" |

### 6.2 Rows

- Full-width, `--sheet` background, `--rule` 1px between rows, padding 14px 16px.
- Tap target = the whole row (a real `<a>` or `<button>`), pressed state darkens to `--paper` for 80ms.
- No shadows, no individual radius.

### 6.3 Numbers

- Always Plex Sans Condensed + tabular figures. Signs always shown: `+0.5%`, `−6.2%` (true minus `−`, not hyphen). Indian grouping: `₹1,48,620` for rupee amounts in full; `₹52.1k`, `₹4.2 lakh`, `₹1.0 cr` when abbreviated; pick one abbreviation style and use it everywhere.
- Right-align numbers in tables; left-align labels.

### 6.4 Promise ledger rows

```
EBITDA margin                         Missed
"We expect EBITDA margins of 24 to 25%│ for FY27."      ← serif italic on highlighter
Delivered 23.8% in Q1, 21.8% in Q2
Q4 FY26 call, page 4 · Q2 FY27 results  ← link colour, opens source
```
Verdict word: **Kept** (`--up`, 600), **Missed** (`--down`, 600), **Late** and **Behind** (`--ink`, 600), **On track** (`--ink-2`, 500), **Dropped** (`--ink-3`, 500, strikethrough on the quote). Words and weight, not coloured pills.

The scorecard on top: "Management delivered **2 of 5** promises that came due" as a sentence, with a single segmented bar (kept / missed / late) labelled underneath.

### 6.5 Charts

- Revenue bars: `--ink` at 25% opacity for past quarters, solid `--ink` for the latest; margin as a line in `--link`, labelled at its last point (no legend box).
- No gridlines except a baseline; no chart-library default tooltips or colours. Values printed on the latest bar only; tap a bar to show its value.
- Every chart has a one-sentence title that states the finding ("Revenue grew every quarter; margin fell for two").

### 6.6 Buttons and controls

- Primary: `--ink` fill, `--sheet` text, 10px radius, 48px tall. **One primary per screen.**
- Secondary: 1px `--ink` outline. Tertiary: `--link` text.
- Segmented controls (window picker, thesis, list/swipe) instead of rows of pills.
- Visible focus ring: 2px `--link`, 2px offset, on every interactive element.

### 6.7 Icons

One set only: **Phosphor Icons, "regular" weight** (or draw the six custom icons needed as inline SVG at 1.75px stroke). Icons always paired with a text label in navigation. No emoji anywhere.

### 6.8 The highlighter mark

```css
.mark {
  background: linear-gradient(transparent 12%, var(--mark) 12%, var(--mark) 88%, transparent 88%);
  box-decoration-break: clone;   -webkit-box-decoration-break: clone;
  padding: 0 2px;
  font-family: "IBM Plex Serif", serif; font-style: italic;
}
```
The gradient here only shapes the band like a real marker stroke (a solid band with clipped edges); it is not a colour gradient. Use it **only** on words copied verbatim from a source document.

### 6.9 Bottom sheets (Ask, decision, source viewer)

`--sheet`, 20px top radius, drag handle, the one floating shadow, max 80% height. The context line at the top is a removable chip ("Kestrel Auto, CFO exit ×").

---

## 7. Motion

- **One orchestrated moment:** when the brief opens, the highlighter "draws" across the quote or key line of the first Urgent item once (background-size animates from 0 to 100% over 450ms, ease-out). Nothing else animates on load.
- Responsive motion only: sheets slide up (220ms, `cubic-bezier(0.2, 0, 0, 1)`), rows show pressed state, a decision tag fades in after tapping.
- Animate only `transform` and `opacity` (plus the one `background-size` above). No fade-up on scroll, no parallax, no hover effects on touch devices.
- `prefers-reduced-motion: reduce` → no draw animation; sheets appear instantly.

---

## 8. Words in the interface

The copy carries the design as much as colour does ([925 Studios](https://www.925studios.co/blog/ai-slop-design-tells): weightless copy is a tell).

| Instead of | Write |
|---|---|
| "P0 · CFO Resignation Alert" | "Urgent: CFO resigns, second key exit in five months" |
| "Needs your attention" (all caps) | "Needs you today (3)" |
| "Good to know" | "For your information (4)" |
| "Seen →" | "Seen" |
| "Unlock AI-powered insights" | "Ask about this" |
| "No data available" | "Nothing needs you today. 9 routine filings hidden." |
| "Something went wrong" | "Couldn't reach NSE. Showing filings checked at 08:10." |
| "Analyse" | "Read filings" (research button), then "Reading 4 transcripts…" |

Rules: sentence case; plain verbs; numbers first; name things the way an investor would ("your book", "results", "concall"); no filler verbs (empower, leverage, unlock, seamless, robust); no exclamation marks; one job per piece of text. Use real company names from the live data; never "Acme" or round invented stats.

---

## 9. Review gate (run before every frontend commit)

Take Playwright screenshots of Brief, Event detail, Company (Promises), Ask open, and Alerts at **390×844 light, 390×844 dark, and 360×780**, then check:

**Blockers (fix before committing)**
- [ ] Any colour outside the token table, any gradient used as colour, any glow
- [ ] Inter, monospace, or any face outside IBM Plex Sans / Sans Condensed / Serif
- [ ] Any ALL-CAPS label, Title Case heading, or "→" in a button
- [ ] Highlighter used on anything that is not a verbatim source quote
- [ ] More than one primary button on a screen
- [ ] Emoji anywhere; mixed icon styles
- [ ] Text below 12px or contrast below 4.5:1
- [ ] Horizontal scroll at 360px; touch targets under 44px
- [ ] Missing focus, pressed, loading (skeleton), empty or error state

**Majors**
- [ ] Items in identical separate cards instead of ledger rows
- [ ] Middle-dot meta strings ("A · B · C") in the UI
- [ ] Same radius on every element
- [ ] Animation on load other than the single highlighter draw
- [ ] Numbers not using tabular figures, or missing +/− signs
- [ ] A coloured dot or tag with no explained meaning

**Taste check (answer in `BUILD_LOG.md`)**
- [ ] If the logo were removed, would this still be recognisable as FINN and not a generic fintech app? Name the element that makes it so (it should be the highlighter + serif quotes).
- [ ] Remove one accessory: what decoration could go without losing meaning? Remove it.

---

## 10. Tailwind setup (sketch)

```ts
// tailwind.config.ts (extend)
colors: {
  paper: 'var(--paper)', sheet: 'var(--sheet)', ink: 'var(--ink)',
  'ink-2': 'var(--ink-2)', 'ink-3': 'var(--ink-3)', rule: 'var(--rule)',
  link: 'var(--link)', mark: 'var(--mark)', up: 'var(--up)', down: 'var(--down)',
},
fontFamily: {
  sans: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
  num: ['"IBM Plex Sans Condensed"', '"IBM Plex Sans"', 'sans-serif'],
  quote: ['"IBM Plex Serif"', 'Georgia', 'serif'],
},
borderRadius: { tag: '4px', ctl: '10px', head: '14px', sheet: '20px' },
```

Remove Tailwind's default colour palette from use (lint rule or code review): only the tokens above may appear in class names.

---

## 11. Extra help for Claude Code

Anthropic publishes an official **frontend-design** skill for Claude Code that pushes away from templated defaults ([listing](https://skills.sh/anthropics/claude-plugins-official/frontend-design)). Ask Claude Code to install it from the official plugin marketplace before frontend work begins. Where it and this file disagree, **this file wins**: it is the specific brief for FINN.
