# AI Partner PRD

AI Partner takes one operating problem from a team and returns a cited brief, a 20-expert panel, a Top 5, a work chart, and a harness kit. The public page is `/chat`. The first engagement is free. The team keeps the files.

This document records the product boundary as of the legacy-auth hardening. It does not add a login, an account, or a private store per caller.

## What this PR changes

`/api/runs` (start, read, events, answers, cancel), `/api/engagements` (list, read, revision read, rename, delete), and `POST /api/branding/ensure` and `POST /api/branding/generate` require the existing partner key before any database or provider work. `/chat` stays open. `GET /api/branding/assets` stays open.

A valid key is an `AI_PARTNER_API_KEYS` entry or a signed `ap_` key. Every valid key can see and change every row in the one SQLite engagement database, and every run held in that process. That is shared-store access. It is not per-client isolation. Authenticated cross-client sharing remains open. Closing it would be a new ownership model and is out of scope.

## Caps that already exist

These counters are in the one server process. A restart clears them. They are not a shared quota across Railway and Maritime.

| Cap | Where it applies |
|---|---|
| 16 signed model calls per chat | `/api/chat`, `/v1`, MCP spend tools |
| 5 new chat ids per IP per day (`AI_PARTNER_DAILY_ENGAGEMENTS`) | those same spend paths |
| 20 turns / 10 minutes / IP, and 200 turns / 10 minutes in the process | those paths, stateless `POST /chat`, and voice |
| 3× the pre-run estimate | `POST /api/runs` only, after the key check |
| $2 confirm dialog | React launcher (`web/src/pages/NewEngagement.tsx`) only |

An unsigned chat call count is treated as zero. The in-memory high-water mark is what stops a client from dropping the signature. After a restart, that mark is gone.

## Keiki

Email delivery on Nov 6, 2026 is a roundtrip reported by AI Partner. This repo run did not observe it. iMessage is unverified. Production spend for that email is unknown. Reply wording is not a spend measurement.

The server has no prose control contract. A message that says "do not run the panel" still starts research once it also contains a team, tools, and a maturity score. Push mode then continues while `next` is set. An echo token in that prose is not copied into the reply. `tests/test_keiki_intake.py` counts model and search calls with doubles. `run_turn` is called directly in one test, so that test does not check the signature header. A second test POSTs a signed body to `/keiki/turn` and still uses the local double. Neither test delivers email or iMessage, and neither calls Keiki, Venice, or Exa.

An explicit stop or confirmation flag, if wanted, needs a separate decision. Proposed gate for that later change: a boolean field on `start_job`, `chat_turn`, and the signed turn payload, defaulting to the current continue-while-`next` behavior, and a test where the flag is true, intake is complete, and the model callable stays at zero calls. Do not infer that flag from English sentences.

## Next feature, not in this PR

Same-browser project history. Keep `localStorage` key `ai-partner-chat-v2`, save more than one job, keep the intake fields, and list artifacts already on that job. Reloading `/chat` reopens a saved job. No server account.

## Release gates

- `python -m pytest tests -q` exits 0. The known skip is the OpenAI SDK import in `tests/test_agents.py`. Provider doubles are not live integration. The test guard blocks `socket.create_connection`, `socket.socket.connect`, and `requests.Session.request` for non-local hosts. It does not block `connect_ex`, `sendto`, subprocess, or proxies.
- `scripts/smoke_public_get.py` checks public GET shape. Matching builds on two hosts can both be stale. `--build` requires one id. `--expect-gated` checks only anonymous `GET /api/engagements` and `GET /api/runs/r_does_not_exist`. It is not the key matrix. A pass before deploy is not proof this PR is deployed.
- GitHub Actions pytest for commit `3603a7b58c552d099026150348bf6ef7df4656b2` succeeded: https://github.com/vivmuk/Expert-Panel/actions/runs/42332995532/job/128283523105. That run does not include later commits.
- Deck files under `server/static/deck/` stay unchanged. Corrections for a later file are in `docs/report/deck-corrections.md`.
