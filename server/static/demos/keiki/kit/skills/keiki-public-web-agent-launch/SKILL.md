---
name: keiki-public-web-agent-launch
description: "Scopes and prepares a v1 customer-facing agent for Keiki's owned public web/help surface, limited to public-content questions with a hard human handoff. Use when the product team is choosing the first channel and defining v1 scope boundaries before launch."
---

> AI-generated from public information for a demo engagement. Not commissioned by the company. Targets are targets, not results.

# Keiki Public-Web Agent Launch Scope

## Overview
Defines the v1 channel decision and scope contract for a customer-facing agent on Keiki's owned, public-facing web surface (on-site help/FAQ-style widget or contact-form assistant). The agent answers only questions answerable from Keiki's own published pages; anything transactional or account-specific is out of scope at v1 and routed to a human. Based on public pages only; not a commissioned engagement.

## When to use
- The team must pick the single first channel for the agent.
- Scope, exclusions, and handoff behavior need to be written and signed off before build.
- A reviewer asks "what does v1 answer, and what does it refuse?"

## Inputs
- List of Keiki's public pages and help/FAQ URLs (public only).
- Candidate owned surfaces (help widget vs. contact-form assistant).
- Named human owner and handoff destination (email/form/queue).

## Steps
1. Inventory owned, public-facing surfaces; pick exactly one as v1. Prefer the surface with the most public-content traffic and lowest account dependency.
2. Write the in-scope intent list: only questions answerable from published pages.
3. Write the out-of-scope list: pricing quotes, orders, accounts, refunds, anything requiring login.
4. Define the hard human handoff: trigger conditions, handoff message, destination, and SLA owner.
5. Define refusal wording for out-of-scope questions (see `scope-checklist.md`).
6. Record the decision, owner, and date in the config repo; mark launch-blocking.
7. Re-review scope whenever a new page type or channel is proposed.

## Output format
A filled `scope-checklist.md` plus a one-paragraph channel decision record (surface, rationale, owner, date).

## Guardrails
- One channel only at v1; no email, in-app, or social DMs.
- No transactional or account-specific answers, even if the model "knows" them.
- Every out-of-scope question must end in a handoff, never a guess.
- Cite only public Keiki pages; do not invent customers, metrics, or quotes.

## Example
Input: help widget vs. contact form. Decision: contact-form assistant, because it is public, low-risk, and already collects handoff details. In scope: "how does Keiki work", "where do I find X feature". Out of scope: "what will my plan cost", "where is my order" → handoff to support form with a summary.
