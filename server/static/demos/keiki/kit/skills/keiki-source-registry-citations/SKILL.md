---
name: keiki-source-registry-citations
description: "Builds a launch-blocking source-of-truth registry and citation contract so every agent answer links a canonical public Keiki page. Use when indexing public content, setting freshness SLAs, or enforcing citation-required answers."
---

> AI-generated from public information for a demo engagement. Not commissioned by the company. Targets are targets, not results.

# Keiki Source Registry and Citation Contract

## Overview
Creates the source registry and crawl/index pipeline that make grounded answers possible, plus a citation-required answer contract. Every public page or doc maps to an owner, canonical URL, and freshness SLA; every answer links its source. Public sources only.

## When to use
- Before the first agent session, to establish the knowledge base.
- When a page changes, is added, or goes stale.
- When auditing whether answers are grounded.

## Inputs
- Public page URLs from onkeiki.com and public help/FAQ pages.
- Page owners and review cadence.
- Index store and change-detection tooling.

## Steps
1. Crawl public pages; record canonical URL, title, owner, and last-verified date per entry using `registry-schema.json`.
2. Assign a freshness SLA per page type (e.g., help articles vs. marketing pages).
3. Stand up change detection; on diff, flag the entry and trigger re-index or owner review.
4. Index only registry-approved pages; block unregistered URLs from retrieval.
5. Enforce the citation contract: every answer includes the canonical URL of each source used.
6. If no registered source supports an answer, the agent says so and offers handoff.
7. Run a weekly staleness report; expired entries drop from retrieval until re-verified.

## Output format
A populated registry conforming to `registry-schema.json`, plus a citation block appended to every answer.

## Guardrails
- No answer without a registered, in-SLA source.
- Canonical URL only; no mirrors or cached copies in citations.
- Stale entries are excluded, not silently used.
- Public pages only; no internal docs at v1.

## Example
Entry: `{ "url": "https://onkeiki.com/help/how-it-works", "owner": "content", "sla_days": 30, "last_verified": "2025-01-10" }`. Answer: "Keiki works by … (source: https://onkeiki.com/help/how-it-works)."
