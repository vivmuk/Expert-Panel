---
name: maritime-deploy-manifest
description: "Drafts a committed, provenance-tagged deploy manifest that declares the Maritime-hosted vs. team-operated seam before any public deploy. Use when a team with an existing repository is preparing to host a public web agent on Maritime and needs the hosting split written down and approved."
---

> AI-generated from public information for a demo engagement. Not commissioned by the company. Targets are targets, not results.

# Deploy Manifest (Hosting Seam)

## Overview
Before a public deploy, the team commits one deploy manifest to the repo that names, in two explicit columns, what Maritime hosts and what the team operates. This makes the seam auditable and prevents silent assumptions about who owns runtime, routing, and abuse exposure. The manifest is provenance-tagged with the source of each claim.

## When to use
- A team has a repo and wants a public web agent but has not yet declared the hosting split.
- A reviewer asks "who operates what" before `--public` is flipped.
- The repo lacks a single artifact describing the platform/team boundary.

## Inputs
- Repository tree and existing Dockerfile/entrypoint (if any).
- Maritime public docs and pricing pages (cite URLs).
- Team's stated runtime, port, and env contract.

## Steps
1. Read the repo and list every deploy-relevant artifact present or missing.
2. Fill the two-column manifest using `manifest-template.md`: left column = Maritime-hosted (build execution, runtime, routing, TLS, sleep/wake, log capture, public URL); right column = team-operated (repo, Dockerfile, entrypoint, port/env contract, health endpoint, rate limiter, secrets).
3. Tag each row with provenance: `docs:<url>`, `repo:<path>`, or `assumption` (flag assumptions for human confirmation).
4. Mark any row where ownership is ambiguous and propose a default.
5. Write `deploy-manifest.md` at repo root and open a PR.
6. Require human approval on the seam before the first public deploy.

## Output format
A committed `deploy-manifest.md` with two columns, a provenance tag per row, and an "Open questions" section. PR description summarizes the split in five lines.

## Guardrails
- Do not invent Maritime capabilities; cite public pages only.
- Do not claim the company commissioned this work.
- Never mark a row `docs:` without a real URL.
- Do not flip `--public` in this skill.

## Example
Team-operated row: `health endpoint | repo:app/server.py | team`. Maritime-hosted row: `TLS termination | docs:https://maritime.sh/docs | platform`. Ambiguous row flagged: `sleep/wake budget | assumption | confirm with Maritime docs`.
