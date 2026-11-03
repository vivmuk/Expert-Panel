"""Let any visitor put AI Partner in their own messaging channels through Keiki.

The visitor's Keiki agent calls AI Partner's MCP server with their own ap_ key, kept in Keiki's
organization secrets. No secret is exchanged with AI Partner beyond that bearer key.
"""
import json
import os
from html import escape

from flask import Blueprint, Response

from ..icons import icon
from .access import request_origin

bp = Blueprint("keiki_connect", __name__)

KEIKI_URL = "https://onkeiki.com"
TITLE = "Put AI Partner in your chats"
CHANNELS = (
    ("imessage", "iMessage", "imessage"),
    ("whatsapp", "WhatsApp", "whatsapp"),
    ("slack", "Slack", "slack"),
    ("telegram", "Telegram", "telegram"),
    ("email", "Email (AgentMail)", "agentmail"),
    ("x", "X", "x"),
    ("sms", "SMS", "sms"),
    ("teams", "Microsoft Teams", "teams"),
)

SYSTEM_PROMPT = (
    "When someone describes a business problem, run an AI Partner engagement with the AI Partner tools. "
    "Call start_job with their message and keep the job_id. Send them every reply. "
    "For each answer they give, call chat_turn with the job_id and their message. "
    "While a result has next set, call chat_turn again with the job_id and an empty message, and send each reply. "
    "When the engagement is done, call get_kit with the job_id and send them the link."
)


def fetch_line(origin):
    return f"Fetch {origin.rstrip('/')}/keiki.md and follow it."


def mcp_connection(origin):
    return {
        "name": "AI Partner",
        "endpoint": origin.rstrip("/") + "/mcp",
        "auth_mode": "headers",
        "headers": {"Authorization": "Bearer {{secret.AI_PARTNER_API_KEY}}"},
        "default_permission": "allow",
    }


def live_channels():
    """Channel slugs listed in KEIKI_LIVE_CHANNELS, the only ones the site may call live."""
    wanted = {c.strip().lower() for c in os.environ.get("KEIKI_LIVE_CHANNELS", "").split(",") if c.strip()}
    return [slug for slug, _, _ in CHANNELS if slug in wanted]


def _mark(mark, size=22, title=""):
    tip = f' title="{escape(title)}"' if title else ""
    return f'<img src="/img/marks/channels/{mark}.svg" alt="" width="{size}" height="{size}" loading="lazy" decoding="async"{tip}>'


def keiki_badge():
    return (
        f'<a class="keiki-badge" href="{KEIKI_URL}" target="_blank" rel="noopener">'
        '<img src="/img/marks/keiki.svg" alt="" width="14" height="14" decoding="async">Integrated with Keiki</a>'
    )


def channel_pill(origin):
    line = fetch_line(origin).rstrip(".")
    names = ", ".join(name for _, name, _ in CHANNELS)
    marks = "".join(_mark(mark, title=name) for _, name, mark in CHANNELS)
    return f"""<div class="pill-row">
  <div class="connect-pill channel-pill gb spot">
    <span class="pill-marks channel-marks" role="img" aria-label="{escape(names)}">{marks}</span>
    <span class="pill-copy"><span class="pill-title"><b>{escape(TITLE)}</b>{keiki_badge()}</span><code>{escape(line)}</code></span>
    <button type="button" class="pill-open" data-open-dialog="keiki-dialog" aria-haspopup="dialog" aria-label="{escape(TITLE)}: open the setup">{icon("arrow-right", "ico pill-go")}</button>
  </div>
  <button type="button" class="copy-btn" data-copy-text="{escape(line)}." aria-label="Copy the Keiki setup line">{icon("copy")}<span class="copied" aria-live="polite"></span></button>
</div>"""


def _channel_list():
    live = set(live_channels())
    tag = '<em class="live-tag">Live</em>'
    items = "".join(
        f"<li>{_mark(mark, 20)}<span>{escape(name)}</span>{tag if slug in live else ''}</li>" for slug, name, mark in CHANNELS
    )
    return f'<ul class="keiki-channels" aria-label="Channels">{items}</ul>'


def _code(snippet_id, text):
    return (
        f'<div class="code"><pre id="{snippet_id}">{escape(text)}</pre>'
        f'<button type="button" class="copy" data-copy="{snippet_id}" aria-label="Copy">{icon("copy")}<span>Copy</span></button></div>'
    )


def channel_dialog(origin):
    line = fetch_line(origin)
    connection = json.dumps(mcp_connection(origin), indent=2)
    return f"""<dialog class="keiki-dialog" id="keiki-dialog" aria-labelledby="keiki-title"><div class="dialog-body">
  <form method="dialog" class="dialog-close"><button type="submit" class="icon-btn" aria-label="Close">{icon("x")}</button></form>
  <p class="dialog-kicker">{keiki_badge()}</p>
  <h2 id="keiki-title">{escape(TITLE)}</h2>
  <p class="muted">Keiki runs your agent on the messaging channels your Keiki account offers. Add AI Partner to that agent as an MCP tool, and anyone who messages it can run an engagement. Your key stays in your Keiki account.</p>
  {_channel_list()}
  <p class="foot-small">A channel is marked Live once we have run AI Partner on it end to end. Your Keiki dashboard shows which channels your account can connect.</p>
  <div class="agent-line"><span class="lbl">Let your coding agent do it</span>
    <div class="pill-row"><code>{escape(line)}</code><button type="button" class="copy-btn" data-copy-text="{escape(line)}" aria-label="Copy the setup line">{icon("copy")}<span class="copied" aria-live="polite"></span></button></div>
  </div>
  <ol class="keiki-steps">
    <li><b>Get a free AI Partner key.</b> It is shown once.
      <form class="keiki-signup" id="keiki-signup"><label class="sr-only" for="keiki-email">Work email</label><input id="keiki-email" type="email" required autocomplete="email" placeholder="you@company.com"><button class="btn small primary" type="submit">{icon("key-round")}Get the key</button></form>
      <p class="status-line" id="keiki-signup-status" role="status"></p>
      <div class="code" id="keiki-key-out" hidden><pre id="keiki-key"></pre><button type="button" class="copy" data-copy="keiki-key" aria-label="Copy the key">{icon("copy")}<span>Copy</span></button></div>
    </li>
    <li><b>Store it in Keiki.</b> In the Keiki dashboard, open Settings, then Secrets, and add <code>AI_PARTNER_API_KEY</code> with the key.</li>
    <li><b>Add AI Partner to a Keiki agent.</b> Create an agent, turn on its Sandbox and MCP features, and add this MCP connection on the Global MCP page (or in <code>deploy_agent</code>'s <code>mcp_connections</code>).{_code("keiki-mcp", connection)}</li>
    <li><b>Tell the agent when to use it.</b> Add this to its system prompt.{_code("keiki-prompt", SYSTEM_PROMPT)}</li>
    <li><b>Connect a channel and message it.</b> Pick a channel for the agent in Keiki, then send it a business problem.</li>
  </ol>
  <p class="foot-small">Keiki is invite-only, and its agents need a Keiki plan to call MCP tools. See <a href="https://onkeiki.com/setup.md" rel="noopener">Keiki's setup guide</a>.</p>
  <div class="keiki-soon"><span class="soon">Coming soon</span><p><b>Bring your own Keiki agent.</b> Keiki pushes signed turns to an endpoint for your account and AI Partner runs the whole turn.</p></div>
  <p class="foot-small"><a href="/connect#keiki">All setups on Connect</a> · <a href="/keiki.md">keiki.md</a></p>
</div></dialog>"""


_PLAYBOOK = """# Put AI Partner in your chats with Keiki

AI Partner is integrated with Keiki (https://onkeiki.com). Use this playbook when someone wants to reach AI Partner from a messaging channel. You build them a Keiki agent that uses AI Partner's MCP server as a tool. Anyone who messages that agent can run an AI Partner engagement: research, 20 AI experts, a debate, the judge's Top 5, a work chart and the harness kit.

The person's AI Partner key stays in their own Keiki organization's secrets. Keiki sends it to `https://HOST/mcp` as a bearer token. Nothing else is shared.

## Before you start

- Keiki is invite-only. If the person is not in yet, follow step 2 of https://onkeiki.com/setup.md to request access, then continue once they are.
- A Keiki organization needs a plan before its agents can call MCP tools: https://onkeiki.com/billing
- Never put the AI Partner key or a Keiki key in the chat, a commit, or a file you show the person.
- Ask before anything that spends money or reaches real people: buying a line, connecting a production channel, or messaging contacts.

## 1. Get a free AI Partner key

```sh
curl -sS -X POST "https://HOST/api/signup" \\
  -H "content-type: application/json" \\
  -d '{"email":"USER_EMAIL"}'
```

The response contains `key` once. It looks like `ap_...`. Or open https://HOST/signup for the person.

## 2. Store the key in Keiki

The person adds an organization secret named `AI_PARTNER_API_KEY`, with the key as its value, in the Keiki dashboard under Settings, then Secrets. Pause until they confirm. Do not ask them to paste the key into the chat.

## 3. Connect to Keiki

Add `https://onkeiki.com/mcp` as a remote Streamable HTTP MCP server. The person signs in through the browser. For example:

- Claude Code: `claude mcp add --transport http keiki https://onkeiki.com/mcp`
- Codex: `codex mcp add keiki --url https://onkeiki.com/mcp`
- Cursor: add `{ "mcpServers": { "keiki": { "url": "https://onkeiki.com/mcp" } } }` to `.cursor/mcp.json`

Call `current_context` to confirm the organization. Without MCP, use the Keiki developer API with the person's `KEIKI_API_KEY` (see https://onkeiki.com/docs/partner-deployments.md).

## 4. Create the agent

Call `deploy_agent` with this body. It is the same body as `POST https://onkeiki.com/api/v1/developer/deployments`.

```json
DEPLOYMENT
```

Check the response: `deployment.mcpConnections` lists `AI Partner` with `status` `connected`, and `deployment.missingSecrets` is empty. If the connection shows `error` or `needs_auth`, confirm the secret is named exactly `AI_PARTNER_API_KEY`.

## 5. Test it

Call `talk_to_agent` with agent `AI Partner` and a real first message, for example: `Decide how a four-person software team should host a public web agent.` The agent should call `start_job` and reply with AI Partner's first question about the team. Nothing is delivered to a real line.

## 6. Go live

Call `list_channel_types` for the channels the person's Keiki organization can connect and the fields each one needs, for example iMessage, SMS, WhatsApp, Slack, Telegram or email through AgentMail. Then call `deploy_agent` again with the same `external_ref`, `"agent": {}`, and a `channels` list. Ask the person before connecting a production channel. Call `get_deployment` with `{ "externalRef": "ai-partner" }` and check that each channel is `connected`.

## 7. Report

```text
AI Partner on Keiki is ready
AI Partner key: stored in Keiki secrets as AI_PARTNER_API_KEY <yes|blocked: reason>
Agent: <name> with the AI Partner MCP connection <connected|blocked: reason>
Test: <talk_to_agent first reply|not run: reason>
Channels: <how to reach it, such as the number to text|none yet>
```

## How the tools work

- `start_job` takes the first message and returns a `reply` and a `job_id`.
- `chat_turn` takes the `job_id` and the person's next message. While a result has `next` set, call it again with an empty message.
- `get_kit`, `get_skill_pack` and `get_work_chart` take the `job_id` once the engagement is done.
- AI Partner keeps the job on its server for that key, so the agent only carries the `job_id`.

## Coming soon

Bring your own Keiki agent: Keiki pushes signed turns to an endpoint for your account, and AI Partner runs the whole turn.

## Sources

- https://HOST/connect#keiki
- https://HOST/get-started.md
- https://onkeiki.com/setup.md
- https://onkeiki.com/docs/partner-deployments.md
"""


def deployment(origin):
    return {
        "external_ref": "ai-partner",
        "agent": {"name": "AI Partner", "system_prompt": SYSTEM_PROMPT, "features": {"sandbox": True, "mcp": True}},
        "mcp_connections": [mcp_connection(origin)],
    }


def render_keiki_md(origin):
    origin = origin.rstrip("/")
    body = _PLAYBOOK.replace("DEPLOYMENT", json.dumps(deployment(origin), indent=2))
    return body.replace("https://HOST", origin)


@bp.get("/keiki.md")
def keiki_md():
    return Response(render_keiki_md(request_origin()), mimetype="text/markdown")
