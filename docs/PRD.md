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

## Same-browser projects

`/chat` keeps a list of projects in `localStorage` key `ai-partner-chat-v2`, schema 3. A project stores the server job state and the transcript without shortening fields. The whole record must be at most 2,000,000 characters. A larger record, a value JSON cannot store, or a `__proto__`, `constructor`, or `prototype` key is refused. The previous value of that key stays. New and switching projects also stay on the current transcript when that save is refused. A transcript entry that is null or not a role object is left in the stored record and shown as an entry that could not be displayed. Reload reopens the selected project and does not call the model while a phase is still running. Continue uses the existing `/api/chat` body. Downloads of the kit, deck, skill pack, and report are rebuilt from that saved state when clicked. They are not server files. `/api/downloads/<id>` links expire after 24 hours and are not listed. Catalog text saved on the job opens as text. This storage is one browser profile on one origin. It is not an account, not a sync, and not the SQLite engagement store. Two browser profiles do not share it. A shared browser profile does. Two open tabs of that profile notice when the other tab has written a newer copy and refuse to replace it. The visitor id in `ai-partner-visitor` stays separate from which project is selected. At 12 projects, New refuses and deletes nothing, and it does not cancel work already in flight. Unreadable JSON and a newer schema stay byte for byte until the user chooses Keep a copy and start fresh. That copies the old text to `ai-partner-chat-v2-held` and only then writes a new list. The warning is shown even when the project list is empty. A refused write says it was not saved.

## Paid work stays closed

Public intake questions do not call a provider. Chat, Exa, Supermemory, speech, brand images, the model list, cost estimate, and `/api/runs` are refused before a provider call. A configured positive integer is not an authoritative provider bill, so those settings do not open a call. Voice and images stay closed. The manufacturer engagement stays unrun and its currency amount stays unset.

The Venice client can record one socket write in a real file when a caller passes that file in. A dropped response is not retried, and a later call with the same request does not write again. `:memory:` is refused. That file is not a bill cap and the HTTP routes do not pass one. The 16-call counter is still not a currency cap. `/api/runs` is refused before the legacy engine.

## Release gates

- `python -m pytest tests -q` exits 0. The known skip is the OpenAI SDK import in `tests/test_agents.py`. Provider doubles are not live integration. The test guard blocks `socket.create_connection`, `socket.socket.connect`, and `requests.Session.request` for non-local hosts. It does not block `connect_ex`, `sendto`, subprocess, or proxies.
- `scripts/smoke_public_get.py` checks public GET shape. Matching builds on two hosts can both be stale. `--build` requires one id. `--expect-gated` checks only anonymous `GET /api/engagements` and `GET /api/runs/r_does_not_exist`. It is not the key matrix. A pass before deploy is not proof this PR is deployed.
- GitHub Actions pytest for commit `3603a7b58c552d099026150348bf6ef7df4656b2` succeeded: https://github.com/vivmuk/Expert-Panel/actions/runs/42332995532/job/128283523105. That run does not include later commits.
- `node tests/test_history.js` checks migration, the 12-project cap, two storage objects, a failed write, and response routing. `tests/test_browser_history.py` runs that file. A browser profile check is separate from CI.
- Deck files under `server/static/deck/` stay unchanged. Corrections for a later file are in `docs/report/deck-corrections.md` and `docs/report/history-authoring.md`.
