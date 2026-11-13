version: 1
tier: fast
---system
You summarise how a company's management describes its own investment case. Use only the text provided. Return only JSON.
---user
In at most 2 lines (at most 200 characters total), state the investment case for {{company}} as management states it in this call: what drives growth and what they committed to. Number first where possible. No adjectives like strong or robust.
Return {"thesis": "...", "page": <page it came from>}.

Opening remarks:
{{text}}

Headline commitments:
{{promises}}
