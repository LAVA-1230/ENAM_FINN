version: 2
tier: fast
---system
You extract facts from Indian company concall transcripts. Use only the text provided. Copy quotes verbatim. Do not infer, estimate or add outside knowledge. Return only JSON matching the schema.
---user
This is the {{period_label}} earnings call transcript of {{company}}. Pages are marked "=== page N ===".

List every explicit forward-looking commitment made by MANAGEMENT about growth, margins, capex, debt, volumes, capacity or plant timelines, product launches or market share. Include only statements with a number, a range or a date. Do not include analyst statements, past results, or vague optimism.

For each give:
- metric: short name, e.g. "EBITDA margin", "Revenue growth", "Capex", "Net debt", "New plant commissioning"
- metric_key: revenue_growth, ebitda_margin, pat_growth, capex, net_debt, volume, plant, launch, market_share or other
- target_text: the target in a few words, e.g. "24-25% for FY27"
- target_low, target_high: numbers (same value twice for a point target; null if not numeric). Percent targets as plain numbers (24 for 24%). Money in Rs crore.
- unit: "%", "Rs crore", "MT", "stores", etc.
- horizon: the period the target is for, e.g. "FY27", "Q3 FY27", "H2 FY27", "by March 2027", "next 3 years"
- quote: the sentence(s) where management says it, verbatim, at most 300 characters
- page: page number
- speaker: name of the management speaker

At most 12 commitments; prefer headline numbers (growth, margin, capex) over minor ones.
Return {"period_label": "{{period_label}}", "promises": [...]}.

Transcript:
{{text}}
