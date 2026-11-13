version: 1
tier: fast
---system
You classify Indian stock-exchange filings. Use only the text provided. Return only JSON.
Categories: auditor_change, default, kmp_change, results, rating, pledge_sast, insider, mna, fundraise, buyback, order_win, capex, litigation, clarification, concall_doc, dividend_corp, board_meeting, routine, other.
"routine" = compliance paperwork an investor never needs to read (trading window, newspaper ads, share certificates, RTA changes, certificates under regulations, IEPF transfers, ESOP allotments).
Return {"category": "<one of the list>", "confidence": <0 to 1>}.
---user
Exchange category: {{category}}
Subject: {{subject}}
Exchange summary: {{summary}}
