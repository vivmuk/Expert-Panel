# Exposure architecture

Corrected proposal. Not approved. Not deployed. Database price unknown. `d71add1` remains an offline prototype; its tests do not make a production cap.

Source for the topology and the current gates: `README.md` (Railway `https://ai-partner.up.railway.app`, Vercel `https://ai-partner-hq.vercel.app`, Maritime `https://74da9def-954d-4df0-9234-04a7301c4740.mtm.sh`), `Dockerfile.railway` (one gunicorn worker, 16 threads, `DATA_DIR=/data`), `vercel.json` (`api/index.py`, 60 second limit), `start.py` (Maritime falls back to `/tmp/ai-partner`), `server/db/__init__.py` (SQLite off when `VERCEL` is set), `server/api/access.py` (one shared partner-key list), `server/keys.py` and `server/api/onboard.py` (signup stores nothing and issues a new `ap_` token for the same email), `server/venice/client.py` (`MAX_ATTEMPTS` and `_request` before `_exchange`), `server/exa_search.py` and `scripts/gen_voice.py` (Exa and voice use `VENICE_API_KEY`), `server/chatmemory.py` (`SUPERMEMORY_API_KEY`), `server/config.py` (image and chat use the Venice key). `server/exposure.py` is the in-process contract only.

## Recommended deployment

Railway is the only sender. These credentials stay on that service and are removed from Vercel and Maritime:

- `VENICE_API_KEY`, which this code uses for Venice chat, Venice-hosted Exa, voice, and image
- `SUPERMEMORY_API_KEY`, which this code uses for memory

Vercel and Maritime keep serving pages and unpaid routes. Their paid paths stay on `refuse_paid()`.

One Postgres database in that Railway project is the registry. Only the Railway service gets `DATABASE_URL`. The legacy `engagements.db` file is not this database (`total_cost_usd` defaults to 0 in `server/db/schema.sql`).

## Owner and project

A project is a business-authorized engagement, created by a server insert. Signup does not create one. A normalized email plus a self-issued `jti` is not an owner: the same person can type another email and get another budget, and anyone who can submit an address can replace a token that was stored under that address.

Initial pilot: an operator provisions the principal and the one project. Later, a verified account may create a project only when an entitlement row already allows it. Public `/chat` and `chat_id` do not create a project. The shared partner key does not create or read one. Reissuing a token does not create a second project.

The server creates the execution id. The client echoes the id the server returned. An id the server did not create is rejected.

## Quote, snapshot, replay, send

The server quotes from `price_schedule`. A row names the service, model, maximum input bytes, output tokens, duration, and item count, the upstream try count, the repair count, and `unit_microusd` for one logical call at those maximums including those tries. A missing row, a non-synthetic provenance in this repository, or a request over the maximum refuses before commit. This repository has no verified price row. A synthetic row is a test fixture. The reserved integer is not a provider invoice. Usage, calculated cost, and billed amount stay null until a feed exists. That feed is not required to count executions.

The insert stores one frozen snapshot and a fingerprint of principal, project, service, model, bounds, and the hash of the payload to be sent. The worker uses that snapshot only. It does not read the caller plan again. Replay returns the stored result only when the new request has the same fingerprint. A different payload with the old execution id is rejected. A different payload with no id is a new execution if the count and the ceiling still allow it.

Three counts executions in `reserved`, `settled`, and `uncertain`. A `void` row is a reservation that never authorized a send. It does not count and its amount is released. Stage calls and provider retries are lines inside the snapshot.

A socket runs only if a conditional update matches `status = reserved`, the capability, a live lease, and a remaining slot in the snapshot. Settlement and uncertainty rotate the capability in that same update. A copied task context that still holds the old capability does not match. If any execution on the project is `uncertain` and not reconciled, further authorizes fail. A sibling that already passed authorize may finish that socket and is then stored as `uncertain`, not as success. Reconcile does not change `reserved_microusd` and does not restore the capability.

If the process dies after the insert and before any authorize (`sends` still 0, lease expired), the row may be voided. If `sends >= 1` and there is no settlement, the row stays `uncertain` and keeps the reservation.

The cost report is that principal's rows on Railway: random report id, status, reserved amount, schedule bounds. No prompts. No shared-partner route.

## What this durability claim covers

Committed Postgres rows survive a process restart and a Railway redeploy, and concurrent authorizes serialize on the project row.

A same-generation snapshot restore is not detected by an environment integer. Restoring the database while the service is still armed loads the older reservations and the cap can be spent again. This design does not add a fake out-of-band counter. After any restore, dump load, or admin rewrite, paid sends stay off until a person reconciles that database and arms the service again. An operator who restores and re-arms has chosen the older ledger. Postgres does not prevent that.

## Alternative

Leave the provider keys on Railway, Vercel, and Maritime, and require each host to run this same transaction before every socket. Use that only if those origins must call the providers themselves. The schema is the same. A stale host can skip the database. It is the larger choice.

## Approval

Unapproved until all of these are chosen:

1. Railway is the only host with `VENICE_API_KEY` and `SUPERMEMORY_API_KEY`.
2. One Postgres database is attached only to that service. Its price was not verified.
3. Paid sends on that service stay disarmed across a database restore until a person reconciles and arms them. There is no automatic restore detector in this design.
4. The pilot project is operator-provisioned. Email signup does not grant a project. A later verified account needs an entitlement row before a project exists.

Without that approval, paid HTTP stays refused. The in-process contract in `server/exposure.py` can keep being tested with synthetic rows and no sockets. That work is not the production cap.
