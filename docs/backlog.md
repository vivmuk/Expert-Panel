# Backlog

Order is the delivery order. Dates are not estimates. Nothing below this line is in the hardening PR except the first row, which is this PR.

1. **Legacy auth, validation, CI, smoke, and these docs.** Shipped on master as `a8e5ec5`. Partner key before any legacy run, store, or brand-write work. Shared-store access is documented there.
2. **Same-browser project history.** Shipped on master as `d1dd46b` (#11). Multiple projects in `ai-partner-chat-v2`. No server account.
2a. **Paid work stays closed.** Shipped on master as `67e3a5c` (#13). Tested HTTP routes stay closed. A configured integer does not open them.
2b. **Per-project dollar ceiling.** Removed. The offline ledger still records reservations and keeps unknown observations null. It no longer stops at a dollar amount. The product limit is three paid questions per email, counted in Postgres on Railway. Maritime uses that same count by calling Railway. Payments are not built.
2c. **Engagement exposure.** This PR, still not production. `MemoryAuthority` is one process and a synthetic price schedule. A helper call must match the frozen line. Replay is that request, not an unbound execution id. A no-send void can be followed by a new execution of the same request. A sibling cannot settle success after project uncertainty. HTTP does not install it. Postgres is not connected. Verified prices, a shared store, principals, and restore handling are not done. The synthetic sum is not an invoice cap. The manufacturer engagement is not run.
3. **Artifact versions** for the report, deck, and kit on a saved job.
4. **Outcome milestones** on the work chart.
5. **Approval gates** before a chart step counts as accepted.
6. **A feedback note** stored in the same browser record.
7. **Connect check** that calls `GET /v1/models` with the pasted key and shows the status code, with no extra model call.

## Deferred on purpose

- Per-client engagement ownership. A partner key remains a key to the shared store until a separate design.
- A boolean stop/confirmation flag for Keiki and MCP. Prose is not that flag. Proposed test: flag true, intake complete, zero model calls.
- Supermemory search URL check. That needs an approved provider call. Cost unknown from this repo.
- Binding zip download names to a caller. Today a 32-hex name is the credential for 24 hours.
- HSTS and a script CSP.
- Deck edits. The FIRST 1000 file stays as it is. See `docs/report/deck-corrections.md`.
- Redis or any new runtime service.
- `GET /api/models` and `POST /api/estimate` still call the Venice catalog with no key. They are outside the legacy store and run gate.
