---
name: keiki-agent-config-and-evals
description: "Produces one versioned, schema-validated agent config with rollback plus a written eval plan with numeric thresholds and trace review. Use when authoring the canonical config, gating go-live, or running regression evals on prompt or model changes."
---

> AI-generated from public information for a demo engagement. Not commissioned by the company. Targets are targets, not results.

# Keiki Versioned Config and Eval Gate

## Overview
Ships the agent as a single canonical config in version control (versioned instructions with changelog, pinned model, feature toggles, env-scoped gateway, chat-only scoped credentials) and gates go-live on a written eval plan with numeric thresholds and sampled trace review. Public sources only.

## When to use
- Authoring or changing the agent config.
- Before go-live and on every prompt, model, or content change.
- When a rollback must be proven.

## Inputs
- Scope checklist and source registry from the other skills.
- Golden set seeded from public pages plus labeled paraphrases.
- Secrets manager and config repo access.

## Steps
1. Author config per `config-schema.json`: version, changelog, pinned model, per-channel and per-capability toggles, env gateway, chat-only credentials reference.
2. Validate config against the schema in CI; block merge on failure.
3. Write the eval plan: per-intent pass thresholds and a rubric covering groundedness, refusal correctness, boundary adherence, escalation, and tone.
4. Run the golden set; record scores per intent.
5. Sample traces for human review; log verdicts.
6. Gate go-live: all thresholds met, traces reviewed, rollback tested to the prior version.
7. Re-run the regression suite on every change; humans sign off releases.

## Output format
A schema-valid config file with changelog, an eval plan doc with numeric thresholds, and a score report with trace-review notes.

## Guardrails
- One canonical config; no drift across environments.
- Pinned model; upgrades are versioned changes with evals.
- Chat-only scoped credentials in the secrets manager, never in the repo.
- No go-live without met thresholds and a tested rollback.
- Thresholds and sign-off are human-owned.

## Example
Config v1.2 pins model, enables `web_widget` only, disables `transactions`. Eval: groundedness ≥ 0.9, refusal correctness ≥ 0.95; 20 traces reviewed; rollback to v1.1 tested; human signs off.
