---
name: thread-handoff-contract
description: "Defines and validates a versioned Thread Handoff Contract (state machine, event log, lease, approval gate) that lets an email client hand a thread to an agent by ID without dropping the conversation. Use when designing or reviewing the handoff data model, state transitions, or the CAS-guarded state record before any agent UX is built."
---

> AI-generated from public information for a demo engagement. Not commissioned by the company. Targets are targets, not results.

# Thread Handoff Contract

## Overview
Produce a single versioned thread-state record and its state machine so a thread can be handed to an agent by ID (not by copy) and returned safely. The record is the first artifact: immutable `thread_id`, append-only event log with content hashes, `owner` field, approval gate, agent lease with TTL, and a monotonically increasing `state_version` guarded by compare-and-swap (CAS).

## When to use
- Before building any agent takeover UX.
- When defining or reviewing the thread state machine, event log, or lease semantics.
- When a handoff or return bug suggests the state model is underspecified.

## Inputs
- Current thread/message data model (IDs, message-ID set, labels, participants).
- Sync engine capabilities (event emission, lease ownership).
- Product decisions on allowed actions and approval levels.

## Steps
1. Draft the record schema from `schema.json`; keep `thread_id` immutable and add `state_version` starting at 1.
2. Encode the state machine: `unassigned -> offered -> agent-held -> awaiting-approval -> returned` (plus `agent-blocked-needs-human`, `failed`, `revoked`). Reject illegal transitions.
3. Make every transition append an event with `(thread_id, state_version, actor, action, content_hash, timestamp)`; never mutate history.
4. Require CAS on `state_version` for every write; on mismatch, reload and retry or surface a conflict.
5. Attach the agent lease: `lease_id`, `ttl_seconds`, single-writer token; expire lease on TTL and revert to `agent-blocked-needs-human`.
6. Add the approval gate: `awaiting-approval` blocks send until a human approves a specific revision hash.
7. Validate a sample thread against `schema.json` and run the illegal-transition cases.

## Output format
- The JSON schema (from `schema.json`, adapted).
- A transition table listing from-state, to-state, actor, guard, and emitted event.
- A short list of CAS conflict and lease-expiry handling rules.

## Guardrails
- Hand off by ID, never by copy.
- No state write without CAS and an appended event.
- No send from `agent-held`; only from an approved revision in `awaiting-approval`.
- Keep the event log append-only; content hashes, not full bodies, in events.

## Example
Thread `t_123` at `state_version` 4, owner `human`. Human offers it: CAS 4->5, event `offered`, lease minted (TTL 900s). Agent accepts: CAS 5->6, state `agent-held`. Agent emits `draft-ready` with revision hash; state `awaiting-approval`. Human approves hash; send allowed. See `schema.json`.
