# Backlog

Order is the delivery order. Dates are not estimates. Nothing below this line is in the hardening PR except the first row, which is this PR.

1. **Legacy auth, validation, CI, smoke, and these docs.** Shipped on master as `a8e5ec5`. Partner key before any legacy run, store, or brand-write work. Shared-store access is documented there.
2. **Same-browser project history.** Shipped on master as `d1dd46b` (#11). Multiple projects in `ai-partner-chat-v2`. No server account.
2a. **Paid-work gate and phase replay.** This PR. Provider calls stay closed unless one host has an explicit SQLite ledger and a calculated ceiling. That ceiling is not a bill. Completed phases replay. Uncertain sends are not repeated. Unpaid intake stays open. The manufacturer engagement is not run, and its currency amount stays unset.
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
