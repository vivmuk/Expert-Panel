"""Connect: setup for ChatGPT, Claude, Cursor, the SDKs, and Grok Bot."""
import json
from html import escape

from .. import art
from ..icons import icon
from .keiki_connect import LABEL, fetch_line, mcp_connection
from .pages import connect_pill, page_head, shell

MARKS = (
    ("#cursor-setup", "/img/marks/cursor.svg", "Cursor cube, from the Cursor brand guidelines", "Cursor"),
    ("#claude-code", "/img/marks/claude-code.png", "Claude Code mark, from the Claude Code docs", "Claude Code"),
    ("#claude-app", "/img/marks/claude.svg", "Claude mark, from claude.com", "Claude"),
    ("#chatgpt", "/img/marks/openai-blossom.svg", "OpenAI blossom, from the OpenAI brand guidelines", "ChatGPT"),
    ("#openai-sdk", "/img/marks/openai-wordmark.svg", "OpenAI wordmark, from the OpenAI brand guidelines", "OpenAI SDK"),
    ("#anthropic-sdk", "/img/marks/anthropic.svg", "Anthropic mark, from anthropic.com", "Anthropic"),
    ("#get-started", "/img/marks/muse.svg", "Muse mark", "Muse"),
)


def _setups(origin):
    mcp = origin + "/mcp"
    base = origin + "/v1"
    bearer = "Authorization: Bearer YOUR_KEY"
    line = f"Set up AI Partner for me. Fetch {origin}/get-started.md and follow it."
    return (
        ("get-started", None, "Any agent", f"Paste one line into any agent that can fetch a URL. It reads the playbook, gets a key, and runs the engagement.", (("get-started-line", line),), ""),
        ("keiki", None, LABEL, "Through Keiki, any Keiki agent can run AI Partner engagements on its channels. Get a free key, add it in Keiki under Settings, then Secrets, as AI_PARTNER_API_KEY, turn on the agent's Sandbox and MCP features, and add this MCP connection. Or paste the line into your coding agent.", (("keiki-line", fetch_line(origin)), ("keiki-connection", json.dumps(mcp_connection(origin), indent=2))), "Coming soon: bring your own Keiki agent, with signed turns pushed to an endpoint for your account."),
        ("chatgpt", "/img/marks/openai-blossom.svg", "ChatGPT", "Add a custom connector and paste the MCP URL. Send the bearer token in the Authorization header.", (("gpt", f"MCP URL\n{mcp}\n\n{bearer}"),), ""),
        ("claude-code", "/img/marks/claude-code.png", "Claude Code", "Claude Code speaks stdio. This config runs the remote server through mcp-remote.", (("claude", json.dumps({"mcpServers": {"ai-partner": {"command": "npx", "args": ["-y", "mcp-remote", mcp, "--header", bearer]}}}, indent=2)),), ""),
        ("claude-app", "/img/marks/claude.svg", "Claude", "In the Claude app, add a custom connector and paste the MCP URL. Send the bearer token in the Authorization header.", (("claude-app-snippet", f"MCP URL\n{mcp}\n\n{bearer}"),), ""),
        ("cursor-setup", "/img/marks/cursor.svg", "Cursor", "Put this in .cursor/mcp.json.", (("cursor", json.dumps({"mcpServers": {"ai-partner": {"url": mcp, "headers": {"Authorization": "Bearer YOUR_KEY"}}}}, indent=2)),), ""),
        ("openai-sdk", "/img/marks/openai-wordmark.svg", "OpenAI SDK", "Point the client at the OpenAI-compatible base URL. The reply is the next turn of the same engagement. Send ai_partner_state back on the following request; the Python SDK keeps that field on the raw response.", (("openai", "\n".join([
            "from openai import OpenAI",
            "",
            f"client = OpenAI(base_url={json.dumps(base)}, api_key='YOUR_KEY')",
            "print(client.chat.completions.create(",
            "    model='ai-partner',",
            "    messages=[{'role': 'user', 'content': 'Decide how Maritime should host a public web agent for a team that already has a repo.'}]",
            ").choices[0].message.content)",
        ])),), ""),
        ("anthropic-sdk", "/img/marks/anthropic.svg", "Anthropic", "The Messages API can attach this MCP server. The MCP handshake on /mcp is verified; this repo does not call Anthropic's cloud.", (("anthropic", json.dumps([{"type": "url", "url": mcp, "authorization_token": "YOUR_KEY"}], indent=2)),), ""),
        ("grok-bot-setup", None, "Grok Bot", "Grok Bot is a desktop agent. It connects remote MCP servers as connectors and can follow a pasted instruction. Paste the line, or add a custom connector.", (("grok-prompt", line), ("grok-connector", f"URL\n{mcp}\nTransport: streamable HTTP\n\n{bearer}")), "Verify: ask Grok Bot to list the AI Partner tools."),
    )


def _code(snippet_id, text):
    return (
        f'<div class="code"><pre id="{snippet_id}" data-snippet="{snippet_id}">{escape(text)}</pre>'
        f'<button type="button" class="copy" data-copy="{snippet_id}" aria-label="Copy">{icon("copy")}<span>Copy</span></button></div>'
    )


def render_connect(origin):
    origin = origin.rstrip("/")
    tiles = "".join(
        f'<a class="mark-tile gb spot" href="{href}"><img src="{src}" alt="{escape(alt)}" height="30" loading="lazy" decoding="async"><span class="cap">{escape(cap)}</span></a>'
        for href, src, alt, cap in MARKS
    ) + '<a class="mark-tile gb spot" href="#grok-bot-setup" id="grok-bot"><span class="wordmark" aria-hidden="true">Grok Bot</span><span class="cap">Grok Bot</span></a>'
    cards = []
    for anchor, mark, title, text, snippets, note in _setups(origin):
        logo = f'<img src="{mark}" alt="" height="22" loading="lazy" decoding="async">' if mark else icon({"get-started": "plug", "keiki": "messages-square"}.get(anchor, "bot"))
        codes = "".join(_code(sid, body) for sid, body in snippets)
        tail = f'<p class="foot-small">{escape(note)}</p>' if note else ""
        cards.append(f'<section class="setup gb reveal" id="{anchor}"><h2>{logo}{escape(title)}</h2><p>{escape(text)}</p>{codes}{tail}</section>')
    hero = art.img("img/brand/hero.webp", "hero-img", eager=True) if art.exists("img/brand/hero.webp") else ""
    intro = page_head(
        "Connect",
        "Run AI Partner inside <em>the agent you already use</em>.",
        "Your team keeps its own agent. AI Partner adds the engagement: research, 20 AI experts, the Top 5, and the harness kit. Your first engagement is free.",
        connect_pill(origin)
        + f'<div class="cta-actions"><a class="btn primary" href="/signup">{icon("key-round")}Get your free key</a><a class="btn ghost" href="/get-started.md">{icon("file-text")}Read get-started.md</a></div>',
    )
    body = f"""<div class="connect-hero">
  {intro}
  {hero}
</div>
<p class="kicker">Works with</p>
<div class="marks">{tiles}</div>
<p class="foot-small">Trademarks belong to their owners. No endorsement is implied. Grok Bot is shown as a text wordmark until an official logo file is available.</p>
<p class="muted">The web chat stays open. The MCP server at <code>{escape(origin)}/mcp</code> and the API at <code>{escape(origin)}/v1</code> need a bearer key; without one they answer 401.</p>
<div class="setup-grid">{"".join(cards)}</div>
"""
    return shell("Connect · AI Partner", "/connect", body)
