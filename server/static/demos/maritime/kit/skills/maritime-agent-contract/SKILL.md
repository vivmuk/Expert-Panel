---
name: maritime-agent-contract
description: "Generates a plain single-port HTTP server skeleton with a CONTRACT.md documenting port, health path, request/response shape, and env vars, plus edge abuse controls. Use when a team needs a deployable agent entrypoint and contract before flipping --public on Maritime."
---

> AI-generated from public information for a demo engagement. Not commissioned by the company. Targets are targets, not results.

# Agent Contract and Edge Controls

## Overview
Default the agent to a plain web app: one HTTP server bound to `0.0.0.0` on a single `PORT`-configurable port, a `GET /health` returning 200, and one request-handling route. Commit a short `CONTRACT.md`. Add an app-level rate limiter and input validator at the edge before `--public`, because public exposure shifts abuse and cost to the team.

## When to use
- The repo has no server entrypoint or an unclear one.
- The team is about to flip `--public` and needs abuse/cost controls.
- A conversational agent needs a chat contract decision.

## Inputs
- Language/runtime of the repo.
- Whether the agent is conversational.
- Env vars required.

## Steps
1. Run the one-question classifier: is the agent conversational? If no, use the plain HTTP contract only. If yes, add a chat contract section.
2. Scaffold one server bound to `0.0.0.0:$PORT` with `GET /health` -> 200 and one handler route.
3. Add a per-IP rate limiter and an input validator at the edge.
4. Document a max-wake budget and deliberate idle-sleep setting.
5. Fill `CONTRACT.md` from the template: port, health path, request/response shape, required env vars.
6. Add `.env.example`; never commit real secrets.
7. Smoke-test locally: health 200, handler responds, limiter returns 429 past threshold.

## Output format
Server file(s), `CONTRACT.md`, `.env.example`, and a smoke-test log showing health, handler, and 429 behavior.

## Guardrails
- Single port only; bind `0.0.0.0`.
- Health must be unauthenticated and always 200 when up.
- Do not commit secrets.
- Do not claim Maritime-specific behavior without a public citation.

## Example
`GET /health` -> `200 ok`. `POST /run` with valid body -> 200. 61st request in a minute from one IP -> `429`.
