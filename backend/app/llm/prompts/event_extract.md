version: 1
tier: fast
---system
You extract facts from Indian stock-exchange filings. Use only the text provided. Copy numbers as written. If a field is not present, return null. Do not infer or add outside knowledge. Return only JSON matching the schema.
---user
Category: {{category}}
Extract the key facts of this filing:
- amount_text: the money amount as written (e.g. "Rs 420 crore", "USD 25 million"), or null
- amount_crore: that amount converted to Rs crore if it is stated in rupees (1 crore = 100 lakh = 10 million), else null
- counterparty: the other party (customer, target, lender, agency), or null
- rating_old, rating_new, outlook, agency, instrument: for credit ratings, else null
- direction: for ratings one of upgrade, downgrade, reaffirm, assigned, withdrawn; else null
- pledge_before_pct, pledge_after_pct: promoter shares pledged as % of promoter holding, for pledge filings, else null
- key_quote: the single most important sentence of the filing, verbatim (at most 220 characters)

Subject: {{subject}}
Filing text:
{{text}}
