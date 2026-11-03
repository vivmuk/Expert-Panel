---
name: maritime-predeploy-gate
description: "Converts the ordered pre-deploy artifact checklist into a CI gate that fails closed before a public Maritime deploy. Use when a repo is nearly deploy-ready and the team wants automated enforcement of Dockerfile, lockfile, dockerignore, EXPOSE, and health-check requirements."
---

> AI-generated from public information for a demo engagement. Not commissioned by the company. Targets are targets, not results.

# Pre-Deploy Artifact Gate

## Overview
A human-read checklist gets skipped. This skill turns the ordered pre-deploy checklist into a pipeline gate that fails closed: each artifact is checked in order and the pipeline stops at the first failure.

## When to use
- The repo has a deploy manifest and is approaching first public deploy.
- The team wants CI to enforce artifacts instead of relying on review.
- A previous deploy failed for a missing artifact.

## Inputs
- Repo tree, Dockerfile, lockfile, `.dockerignore`, `CONTRACT.md`.
- CI config location.

## Steps
1. Load `checklist.md`; it is the ordered, authoritative list.
2. For each item in order, write a CI step that exits non-zero on failure.
3. Enforce: root Dockerfile with digest-pinned base image; committed lockfile; `.dockerignore` excluding `.git`, `.env`, test fixtures; declared `EXPOSE` matching the actual listener; `GET /health` returning 200; `CONTRACT.md` present.
4. Wire the gate to run on every PR and block merge on failure.
5. Run the gate locally once and paste output into the PR.
6. Only after a green gate may the deploy step run.

## Output format
A CI job named `predeploy-gate` with ordered steps mirroring `checklist.md`, plus a PR comment showing a green local run.

## Guardrails
- Fail closed: missing item = non-zero exit, never a warning.
- Do not reorder checklist items.
- Do not auto-fix secrets; only flag them.
- Cite public docs for any Maritime-specific claim.

## Example
Step 4 fails because `EXPOSE 8080` does not match listener on `PORT` (default 3000). Gate exits 1; deploy blocked until fixed.
