version: 2
tier: fast
---system
You extract facts from Indian stock-exchange filings and company documents. Use only the text provided. Copy numbers exactly as written in the statement (no rounding, no unit conversion), as plain numbers without commas. Losses and negative values are negative numbers. If a field is not present, return null. Do not infer, estimate or add outside knowledge. Return only JSON matching the schema.
---user
Find the statement of financial results in this filing. Identify the columns for the current quarter, the immediately preceding quarter, and the corresponding quarter of the previous year. Prefer the consolidated statement if both consolidated and standalone exist.

For each of the three columns give: revenue from operations, other income, total expenses, finance costs, depreciation and amortisation, exceptional items, profit before tax (after exceptional items), total tax expense, net profit for the period (PAT, before other comprehensive income). For banks and NBFCs that report "interest earned", also give interest_earned, operating_profit (before provisions and contingencies) and provisions, and set is_bank_format true.

Also give: basis (consolidated or standalone), unit as stated in the table header (lakh, crore, million or thousand), and the page number (1-based, as marked "=== page N ===") where the table is.

Filing text:
{{text}}
