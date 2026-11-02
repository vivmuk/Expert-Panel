---
name: build-harness
description: Download the AI Partner harness kit and skill pack for a finished job and tell the user where the files landed.
---

# Build the harness

Use this when the job state already has a work chart and the user wants the files their team will run.

1. Read `AI_PARTNER_API_KEY` from the environment. Never print it.
2. Prefer the MCP tools `get_kit` and `get_skill_pack`. They return a download URL.
3. Otherwise `POST /api/chat/kit` and `POST /api/chat/skill-pack` on the same host with `{"state": <saved state>}` and the bearer token.
4. One engagement returns 1 harness and up to 3 skills. Save the zips outside the git repo unless the user asks to commit them. Do not commit the API key.
