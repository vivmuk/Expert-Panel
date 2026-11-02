# Handoff Manifest

Required fields:

| Field | Type | Notes |
|---|---|---|
| thread_id | string | Immutable, stable |
| owner | enum(human, agent) | Set to agent on handoff |
| scope | enum(read, reply, label, archive) | Narrowest needed |
| lease_id | string | Minted by sync engine |
| ttl_seconds | integer | Mandatory, e.g. 900 |
| single_writer_token | string | Rejects stale writers |
| allowed_actions | string[] | Subset of scope |
| grantor | string | Human who initiated |

Return-path events (keyed by thread_id + lease_id):

- `started`
- `draft-ready` (revision_hash)
- `sent` (revision_hash)
- `failed` (reason)
- `returned` (emitted by sync engine)

Rules:
- One active lease per thread.
- Expired lease -> `returned` + `agent-blocked-needs-human`.
- Stale lease_id or token -> event rejected.
