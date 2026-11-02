---
name: frozen-envelope-approval
description: "Builds a frozen thread envelope and binds human approval to a specific draft revision hash, draft-only by default, with a thread-local time-boxed capability grant and an ownership header plus audit trail. Use when implementing the approval gate, the envelope the agent may draft inside, or the visible ownership state and audit logging."
---

> AI-generated from public information for a demo engagement. Not commissioned by the company. Targets are targets, not results.

# Frozen Envelope & Approval

## Overview
The agent receives a frozen thread envelope (participants, ordered message-ID set with watermark, attachments, labels, stated intent) and may only produce draft revisions inside it. Nothing sends until a human approves a specific revision hash. Handoff is a thread-local, time-boxed capability grant, and ownership state is rendered in the thread header and logged to an append-only audit trail.

## When to use
- When implementing the approval gate or the envelope the agent drafts within.
- When adding ownership state to the thread header or audit logging.
- When a send happened without approval or the agent acted outside scope.

## Inputs
- Thread participants, ordered message-ID set, attachments, labels.
- Human's stated intent for the thread.
- Grant scopes and TTL.

## Steps
1. Human initiates handoff; mint a signed, thread-local, time-boxed capability grant (thread ID, grantor, scopes, TTL).
2. Freeze the envelope: participants, ordered message-ID set with watermark, attachments, labels, intent. Hash it.
3. Agent drafts only inside the envelope; each revision gets a content hash.
4. Render owner state in the header: `human-owned`, `agent-proposed`, `agent-acting`, `agent-blocked-needs-human`, `returned`.
5. Human approves a specific revision hash; approval binds to that hash and the envelope hash.
6. Send only the approved revision; if the envelope changed, require re-approval.
7. Log every transition and action to the append-only audit trail with rationale.

## Output format
- The envelope object (from `checklist.md`).
- The grant record (scopes, TTL, grantor).
- Header state list and audit event fields.

## Guardrails
- Draft-only by default; no send without approval of a specific revision hash.
- Envelope change invalidates prior approval.
- Grant is thread-local and time-boxed, not account-wide.
- Every transition is visible in the header and logged.

## Example
Envelope hash e1, revision hash r1. Header shows `agent-proposed`. Human approves r1; send allowed. If a new message arrives (watermark moves), envelope hash changes and re-approval is required. See `checklist.md`.
