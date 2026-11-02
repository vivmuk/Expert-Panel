---
name: lease-return-path
description: "Implements the agent return path as a TTL lease owned by the sync engine, keyed by thread ID, with a handoff manifest and return-path events (started, draft-ready, sent, failed, returned). Use when wiring the handoff/return mechanics between client, sync engine, and agent so the conversation is never dropped."
---

> AI-generated from public information for a demo engagement. Not commissioned by the company. Targets are targets, not results.

# Lease Return Path

## Overview
Hand a thread to an agent by ID with a handoff manifest (owner, scope, lease_id, TTL, single-writer token, allowed actions). The agent acts only against that ID and emits return-path events keyed by `(thread_id, lease_id)`. The sync engine owns the lease and reclaims the thread on TTL expiry or failure.

## When to use
- When implementing the handoff/return transport between client, sync engine, and agent.
- When defining the manifest, lease lifecycle, or return-path event set.
- When a thread is stuck with an agent or a return is lost.

## Inputs
- Thread ID and current owner.
- Allowed actions and scope for this handoff.
- Sync engine lease API and TTL policy.

## Steps
1. Human initiates handoff in-thread; client sends `thread_id` plus a manifest (see `manifest.md`).
2. Sync engine mints a lease (`lease_id`, `ttl_seconds`, `single_writer_token`) and records the manifest.
3. Agent confirms `started` keyed by `(thread_id, lease_id)`; it may act only within scope.
4. Agent emits `draft-ready` with revision hash, then `sent` after approval, or `failed` with reason.
5. On completion or TTL expiry, sync engine emits `returned` and restores human ownership.
6. Reject any agent event whose `lease_id` or single-writer token is stale.
7. Log every event to the audit trail.

## Output format
- The manifest object (from `manifest.md`).
- The ordered return-path event list with payload fields.
- Lease expiry and stale-token handling rules.

## Guardrails
- Key everything by `thread_id`; never copy the thread.
- One active lease per thread; single-writer token enforced.
- TTL is mandatory; no infinite leases.
- Agent acts only within manifest scope and allowed actions.

## Example
Manifest: `{thread_id: t_123, owner: agent, scope: reply, lease_id: l_9, ttl_seconds: 900, allowed_actions: [draft_reply]}`. Agent emits `started`, then `draft-ready` (hash h1). After approval, `sent`. Sync engine emits `returned`. See `manifest.md`.
