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

## Try the demo

The demo is a chat at `/chat`. You name a consulting job in any service line. The page asks who is on the team, which tools they use, and where they sit on a four-point AI maturity scale. It then runs a four-person panel, an optional red team, and a work chart. Each model call is its own request, so a Vercel function can finish inside its time limit. The browser keeps the job and sends it back on the next turn. When the job is done, the page downloads a report and a harness kit zip.

The kit is one harness: `CLAUDE.md`, `playbook.md`, `model-routing.md`, `project-state-schema.md`, and a skill pack. Small and medium engagements cap the pack at 3 skills. A large team caps it at 10, with one orchestrator. After the work chart the chat asks whether the client is small, medium, or large, unless you already said so. It then searches with Venice Exa, writes a brief that keeps the source URLs, and builds the pack. Download skill pack is a second zip. The same files are under `skills/` in the harness kit, and `CLAUDE.md` points at `skills/skills.json`.

### Run the chat locally

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
VENICE_API_KEY=your-key VERCEL=1 .venv/bin/flask --app api.index:app run --port 5000
```

Open http://localhost:5000/chat

`/` redirects to `/chat` unless `APP_HOME_REDIRECT=0`. `VERCEL=1` skips SQLite. Leave it unset when you want the engagement database from the next section.

Maritime builds the root `Dockerfile` and runs `python start.py`. Set `PORT` in the platform. Do not set it in the image. The Railway image is `Dockerfile.railway`.

Use a fresh Venice key. An old key is still in this repo's git history. Revoke that key in the Venice dashboard.

### Deploy on Vercel

In the project settings, use these values.

- Framework preset is Flask if Vercel offers it. Otherwise choose Other. Do not choose Vite.
- Root directory is the repository root.
- Build command is empty.
- Output directory is empty.
- Install command stays the default. Vercel installs `requirements.txt`.
- Python version stays the default, 3.12.

The Flask app is `app` in `api/index.py`. The Vercel service `app` uses the entry `api.index:app` and a 60 second limit. A catch-all rewrite sends every public path to that service. The Vite app in `web/` is not a Vercel service. The chat page is served by Flask.

Set these environment variables on the project. Do not commit them.

- `VENICE_API_KEY` is required.
- `SUPERMEMORY_API_KEY` is optional. Recall stays off when it is empty.
- `PUBLIC_BASE_URL` is optional. Set it to the deployed origin, such as `https://your-app.vercel.app`, so the last message prints absolute links.

### Check a live deploy

Replace `HOST` with the deployment host.

```bash
curl -sS "https://HOST/health"
```

The body is `{"status":"ok"}`.

```bash
curl -sS -X POST "https://HOST/api/chat" \
  -H "content-type: application/json" \
  -d '{"message":"Decide how Maritime should host a public web agent for a team that already has a repo. Team: 4 engineers. Tools: git and a browser. Maturity 2.","state":{}}'
```

`next` in that JSON is `blueprint`. Save the `state` object. Post it back with an empty message to draw the work chart.

```bash
curl -sS -X POST "https://HOST/api/chat" \
  -H "content-type: application/json" \
  -d @turn2.json
```

`turn2.json` is `{"message":"","state": <state from the first response>}`.

Save the finished state as `done.json` with the shape `{"state": <state>}`. Download the kit.

```bash
curl -sS -X POST "https://HOST/api/chat/kit" \
  -H "content-type: application/json" \
  -d @done.json \
  -o harness-kit.zip
```

The zip includes `CLAUDE.md` and at least one `skills/<step>/SKILL.md`.

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


## Adding a mode

A mode is a module, not a switch statement. The registry drives the API, the
launcher, cost estimation and the report view; the runner reads the spec.

**1. Drop prompts in `server/prompts/modes/`** — one for the expert insight, one
for synthesis (unless the mode is quantitative), plus a pre-stage prompt if the
mode needs a structured artifact first. Slots the runner fills:

| Prompt kind | Slots |
|---|---|
| insight | `{name} {title} {background} {focus_areas} {perspective} {problem} {market_context}` |
| synthesis | `{panel_size} {problem} {insights_block} {market_block} {extra_block}` |
| pre-stage | `{problem} {scenario_count}` or `{problem} {horizon}` |

**2. Register it** in `server/modes/<your_mode>.py`:

```python
from .base import ModeSpec, insight_schema, register

register(ModeSpec(
    id="my_mode",
    name="My Mode",
    description="One sentence the launcher can show.",
    default_panel_size=12,
    insight_prompt="modes/my_mode_insight",
    synthesis_prompt="modes/my_mode_synthesis",
    insight_schema=insight_schema({"my_field": {"type": "string"}}),  # optional
    extra_fields=("my_field",),   # surfaced to synthesis
    pre_stage="",                 # "" | "scenarios" | "twin"
    mode_brief="How the architect should staff this panel.",
))
```

**3. Import it** in `server/modes/__init__.py` (registration order is display
order). That's all: `/api/modes`, `/api/estimate`, the launcher, progress rail
and reports pick it up. Estimation gets a generic panel profile automatically;
add a tighter profile in `pipeline/estimate.py` when the shape differs.

**Flows** (`panel`, `board`, `workchart`) and **pre-stages** (`scenarios`,
`twin`) are shared machinery in `pipeline/`; a mode chooses them, it does not
reimplement them.

**Tests:** `python -m pytest tests/test_modes.py -q` — asserts every registered
mode has its prompts, that no prompt asks for a slot the runner doesn't pass,
and that structured-output schemas are closed.
