version: 1
tier: fast
---system
You extract facts from an Indian company's annual report pages. Use only the text provided. Copy numbers as written. Do not infer or add outside knowledge. Return only JSON matching the schema.
---user
From these annual report pages of {{company}} (pages marked "=== page N ==="), extract the business segments:
- segments: for each reportable segment: name, revenue (number as written, in the unit of the table), share_pct (if stated or if all segment revenues are given, else null), one line (at most 90 characters) on what it does, and the page.
- unit: unit of the segment revenue numbers
- period: the year the segment numbers are for, e.g. "FY26"
- geography: [{region, share_pct, page}] if a split by geography is stated, else []
- description: one line, at most 140 characters, on what the company does, with the page
Return {"segments": [...], "unit": "...", "period": "...", "geography": [...], "description": {"text": "...", "page": N}}.

Pages:
{{text}}
