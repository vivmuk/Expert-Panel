# ✦ AI Partner — Constellation Platform

An all-in-one replacement for a management-consulting engagement, powered by the
[Venice AI](https://venice.ai) API. Describe a problem; AI Partner assembles a
bespoke panel of up to **100 expert personas**, grounds them in **live web and X
search with citations**, and returns a synthesized report — or an agent-era
**Work Chart** of your process, complete with breakthrough redesign
opportunities. Every engagement is saved with full revision history and can be
updated later in plain language.

## Engagement modes

| Mode | What it does |
|---|---|
| **Deep Dive Panel** | Panel Architect designs a coverage blueprint → experts are cast in parallel → live market intelligence (web/X search, URL scraping) → per-expert analyses → synthesis with consensus & dissent map and Now/Next/Later recommendations |
| **Red Team** | Adversarial panel (pre-mortem lead, rival strategist, hostile regulator, short-seller…) attacks your plan and ranks what kills it, with mitigations |
| **Quick Pulse** | 50–100 lightweight personas give a quantitative read: stance distribution, per-discipline means, top concerns |
| **Board Meeting** | A simulated board debates your motion over multiple rounds, then delivers minutes and a vote |
| **Work Chart** | Your process today vs. its agent-era redesign: owners (Human / AI Agent / Hybrid / Digital Twin), agent functions, reusable agent-factory assets, time/cost/FTE deltas — plus a "Beyond the Chart" section of type-2 breakthrough opportunities from a thinking model. Revise any chart later in plain language; every version is kept with a change log |
| *Coming soon* | Scenario Planning, Due Diligence, AI Opportunity Scan, Digital Twin Blueprint (registered stubs — enabling one is a prompts-only change) |

## Architecture

- **`server/`** — Flask API.
  - `venice/` — thread-safe Venice client (structured outputs, streaming, web/X
    search with citations, URL scraping, image generation), live model catalog
    with capability-based role resolution, per-call cost ledger.
  - `pipeline/` — the run engine: Panel Architect → parallel persona batches →
    bounded-concurrency insights → market intelligence → synthesis (map-reduce
    for panels > 30). SSE events with `Last-Event-ID` replay.
  - `modes/` — mode registry; a mode is prompts + schemas over shared machinery.
  - `workchart/` — generate / clarify-refine / revise flows + breakthroughs.
  - `prompts/` — every prompt is a markdown template; edit without touching code.
  - `db/` — SQLite (WAL): engagements, revisions, run events.
- **`web/`** — React + Vite frontend ("star chart" design system). Live runs
  render the panel as a constellation: each expert is a star that ignites as its
  analysis completes.

Models are **discovered live** from `GET /models` — new Venice models appear in
Settings automatically, and every pipeline role is validated against capability
flags (web search, X search, reasoning) with graceful fallbacks.

### Cost governance

Pre-run estimates (`POST /api/estimate`), a confirm dialog above $2, a live cost
ticker during runs, per-engagement totals, and a circuit breaker that aborts any
run exceeding 3× its estimate.

## Local development

```bash
# Backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt
VENICE_API_KEY=... .venv/bin/python -m gunicorn --worker-class gthread \
  --workers 1 --threads 16 --timeout 0 --bind 0.0.0.0:5000 server.wsgi:app

# Frontend (dev server proxies /api to :5000)
cd web && npm install && npm run dev
```

Before first use, smoke-test the Venice integration (~$0.001):

```bash
VENICE_API_KEY=... python scripts/verify_venice.py
```

## Deploy (Railway)

1. Point Railway at this repo — the multi-stage `Dockerfile` builds the frontend
   and serves everything from one container (`/health` is the healthcheck).
2. **Create a volume** mounted at `/data` (engagements are SQLite; without a
   volume they vanish on redeploy). `DATA_DIR` defaults to `/data` in the image.
3. Set `VENICE_API_KEY` in service variables. Never commit keys.

> ⚠️ **Key rotation**: an old Venice API key was committed to this repository's
> git history. If you have not already, **revoke it in the Venice dashboard**
> and use a fresh key via environment variables only.

### Scaling note

The app intentionally runs **one gunicorn worker** with many threads: live runs
and their SSE subscribers must share a process (in-memory run registry). Run
events are also flushed to SQLite (`run_events`), which is the escape hatch if
multi-worker is ever needed.

## Brand Studio

The UI ships with a procedural SVG constellation identity, and the server
generates its own **watercolor artwork** via Venice image models on first visit
(cached in `DATA_DIR/branding`). Regenerate any time from **Settings → Brand
Studio**, or via the API: `GET /api/branding/assets`, `POST
/api/branding/ensure`, `POST /api/branding/generate {slot?, model?}`.
