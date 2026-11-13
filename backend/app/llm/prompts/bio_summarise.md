version: 1
tier: fast
---system
You write short professional backgrounds for investors. Use only the text provided. Return only JSON.
---user
Write at most 3 lines about {{name}} ({{role}} at {{company}}): previous roles with company and years, and qualifications. Each line at most 90 characters, plain facts, no adjectives. For each line give the source id it came from.
If the sources may describe a different person with the same name, return {"lines": []}.
Return {"lines": [{"text": "...", "source": "<source id>"}]}.

Sources:
{{sources}}
