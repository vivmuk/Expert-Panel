---
name: run-engagement
description: Start one AI Partner strategy engagement from a business problem and keep the job state for the next turn.
---

# Run an engagement

Use this when the user's team wants a strategy engagement run by agents: research, a panel, a Top 5, a maturity score, and a work chart.

1. Read `AI_PARTNER_API_KEY` from the environment. If it is missing, follow section 1 of the AI Partner `get-started.md` for this host. Never print the key, write it into the chat, or commit it.
2. Call the MCP tool `start_job` with one plain-language problem. If MCP is not connected, `POST /api/chat` on that same host with `{"message": "<problem>", "state": {}}` and header `Authorization: Bearer $AI_PARTNER_API_KEY`.
3. Save the returned `state`. Send that same object back on the next turn. Do not drop fields.
4. Show the user the reply. The first engagement is free. It includes a research brief, a cited market analysis, a 20-expert panel with a two-round debate, the judge's Top 5, maturity score, work chart, 1 harness, and 3 skills.
