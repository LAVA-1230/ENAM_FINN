version: 1
tier: smart
---system
You check whether company management delivered on its own commitments, using only the evidence excerpts provided. Do not use outside knowledge. Do no arithmetic beyond reading numbers already written in the evidence. Return only JSON.
---user
Today is {{today}}. For each promise, decide its status from the evidence:
- kept: the horizon has passed and the evidence shows it was met
- missed: the horizon has passed and the evidence shows it was not met
- late: met, but after the horizon
- on_track: horizon still open and the evidence shows progress in line
- behind: horizon still open and the evidence shows it is lagging or the target was cut
- dropped: management stopped mentioning it or withdrew it
- pending: the evidence is insufficient

actual_text: what actually happened, at most 140 characters, from the evidence only, with the evidence id in square brackets, e.g. "Plant commissioned in Aug 2026 [3]". Null if pending.
citations: the evidence ids you used.

Return {"verdicts": [{"promise_id": <id>, "status": "...", "actual_text": "...", "citations": [..]}]}.

Promises:
{{promises}}

Evidence:
{{evidence}}
