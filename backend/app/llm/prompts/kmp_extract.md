version: 1
tier: fast
---system
You extract facts from Indian stock-exchange filings. Use only the text provided. If a field is not present, return null. Do not infer or add outside knowledge. Return only JSON matching the schema.
---user
This filing is about a change in a director, key managerial person or auditor. Extract:
- person: full name of the person leaving or joining (the main subject of the filing)
- role: their role, e.g. "Chief Financial Officer", "Managing Director", "Company Secretary", "Statutory Auditor"
- change: one of resignation, appointment, cessation, retirement, re-appointment
- reason_stated: the reason exactly as written in the filing (verbatim), or null
- effective_date: as written
- successor: {name, role, interim (true/false)} if the filing names one, else null
- profile_text: the brief profile / background of the incoming person if the filing includes one (verbatim, up to 600 characters), else null
- tenure_text: how long the outgoing person held the role, if stated

Exchange subject: {{subject}}

Filing text:
{{text}}
