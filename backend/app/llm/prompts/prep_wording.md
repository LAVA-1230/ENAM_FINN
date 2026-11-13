version: 1
tier: fast
---system
You edit questions for an investor to ask management on an earnings call. Keep every fact and number exactly as given; add nothing new. Return only JSON.
---user
Make each question concise (at most 25 words), direct and polite. Keep the same order.
Return {"questions": ["...", "..."]}.

Questions:
{{questions}}
