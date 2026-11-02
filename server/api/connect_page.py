def render_connect(origin):
    origin = origin.rstrip("/")
    mcp = origin + "/mcp"
    base = origin + "/v1"
    return PAGE.replace("__ORIGIN__", origin).replace("__MCP__", mcp).replace("__BASE__", base)


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Connect · AI Partner</title>
<link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png">
<link rel="icon" href="/favicon-512.png" sizes="512x512" type="image/png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="stylesheet" href="/app.css">
</head>
<body>
<div class="bar"><span id="progress"></span></div>
<header class="top">
  <a class="brand" href="/chat"><img class="persona" src="/img/brand/avatar.webp" alt="" width="36" height="36"> AI Partner</a>
  <nav class="links">
    <a href="/chat">Chat</a>
    <a href="/demos">Demos</a>
    <a href="/deck">Deck</a>
    <a href="/catalog">Catalog</a>
    <a href="/connect" aria-current="page">Connect</a>
    <a href="/pricing">Pricing</a>
    <a class="primary" href="/pricing">Get API key</a>
  </nav>
</header>
<main class="wrap">
  <p class="kicker">Connect</p>
  <img class="accent" src="/img/brand/character.webp" alt="AI Partner, a multi-arm robot with a floral calavera helmet and a marigold mandala halo." width="280" height="210">
  <h1>Use AI Partner inside the agents you already use.</h1>
  <p class="lede">The web chat stays open. These endpoints need a bearer token from <span class="mono">AI_PARTNER_API_KEYS</span>. If that variable is empty, they answer 401.</p>
  <div id="onboard-slot"></div>
  <p class="kicker">Works with</p>
  <div class="works-with">
    <a href="#cursor-setup"><img src="/img/marks/cursor.svg" alt="Cursor cube, from the Cursor brand guidelines" height="32"><span class="cap">Cursor</span></a>
    <a href="#claude-code"><img src="/img/marks/claude-code.png" alt="Claude Code mark, from the Claude Code docs" height="32"><span class="cap">Claude Code</span></a>
    <a href="#claude-app"><img src="/img/marks/claude.svg" alt="Claude mark, from claude.com" height="32"><span class="cap">Claude</span></a>
    <a href="#chatgpt"><img src="/img/marks/openai-blossom.svg" alt="OpenAI blossom, from the OpenAI brand guidelines" height="32"><span class="cap">ChatGPT</span></a>
    <a href="#openai-sdk"><img src="/img/marks/openai-wordmark.svg" alt="OpenAI wordmark, from the OpenAI brand guidelines" height="32"><span class="cap">OpenAI</span></a>
    <a href="#anthropic-sdk"><img src="/img/marks/anthropic.svg" alt="Anthropic mark, from anthropic.com" height="32"><span class="cap">Anthropic</span></a>
    <span class="mark"><img src="/img/marks/muse.svg" alt="Muse mark" height="32"><span class="cap">Muse</span></span>
    <span class="pending" id="grok-bot"><b>Grok Bot</b><span class="cap">Placeholder</span></span>
  </div>
  <p class="foot">Trademarks belong to their owners. No endorsement is implied. The Grok Bot slot is a placeholder until an official logo file is available.</p>
  <section class="card" id="chatgpt">
    <h2>ChatGPT</h2>
    <p>Add a custom connector and paste the MCP URL. Send the bearer token in the Authorization header.</p>
    <pre id="gpt" data-snippet="gpt"></pre>
    <button type="button" data-copy="gpt">Copy</button>
  </section>
  <section class="card" id="claude-code">
    <h2>Claude Code</h2>
    <p>Claude Code speaks stdio. This config runs the remote server through mcp-remote.</p>
    <pre id="claude" data-snippet="claude"></pre>
    <button type="button" data-copy="claude">Copy</button>
  </section>
  <section class="card" id="claude-app">
    <h2>Claude</h2>
    <p>In the Claude app, add a custom connector and paste the MCP URL. Send the bearer token in the Authorization header.</p>
    <pre id="claude-app-snippet"></pre>
    <button type="button" data-copy="claude-app-snippet">Copy</button>
  </section>
  <section class="card" id="cursor-setup">
    <h2>Cursor</h2>
    <p>Put this in <span class="mono">.cursor/mcp.json</span>.</p>
    <pre id="cursor" data-snippet="cursor"></pre>
    <button type="button" data-copy="cursor">Copy</button>
  </section>
  <section class="card" id="openai-sdk">
    <h2>OpenAI SDK</h2>
    <p>Point the client at the OpenAI-compatible base URL. The reply is the next turn of the same job. Send <span class="mono">ai_partner_state</span> back on the following request. The Python SDK keeps that field on the raw response.</p>
    <pre id="openai" data-snippet="openai"></pre>
    <button type="button" data-copy="openai">Copy</button>
  </section>
  <section class="card" id="anthropic-sdk">
    <h2>Anthropic</h2>
    <p>The Messages API can attach this MCP server. We verified the MCP handshake on <span class="mono">/mcp</span>. We did not call Anthropic's cloud from this repo.</p>
    <pre id="anthropic" data-snippet="anthropic"></pre>
    <button type="button" data-copy="anthropic">Copy</button>
  </section>
  <section class="card" id="grok-bot-setup">
    <h2>Grok Bot</h2>
    <p>Grok Bot is a desktop agent. It connects remote MCP servers as connectors and can follow a pasted instruction.</p>
    <p>Paste this into a Grok Bot chat:</p>
    <pre id="grok-prompt"></pre>
    <button type="button" data-copy="grok-prompt">Copy</button>
    <p>Or add a custom connector. The URL is streamable HTTP. The header is <span class="mono">Authorization: Bearer</span> and the AI Partner key.</p>
    <pre id="grok-connector"></pre>
    <button type="button" data-copy="grok-connector">Copy</button>
    <p>Verify: ask Grok Bot to list the AI Partner tools.</p>
  </section>
</main>
<footer class="site-foot">
  <a class="brand" href="/chat"><img class="persona" src="/img/brand/avatar.webp" alt="" width="28" height="28"> AI Partner</a>
  <p>Beta. Billing is not live.</p>
</footer>
<script>
const mcp = "__MCP__";
const base = "__BASE__";
const nl = String.fromCharCode(10);
const blocks = {
  gpt: ["MCP URL", mcp, "", "Authorization: Bearer YOUR_KEY"].join(nl),
  claude: JSON.stringify({mcpServers: {"ai-partner": {command: "npx", args: ["-y", "mcp-remote", mcp, "--header", "Authorization: Bearer YOUR_KEY"]}}}, null, 2),
  "claude-app-snippet": ["MCP URL", mcp, "", "Authorization: Bearer YOUR_KEY"].join(nl),
  cursor: JSON.stringify({mcpServers: {"ai-partner": {url: mcp, headers: {Authorization: "Bearer YOUR_KEY"}}}}, null, 2),
  openai: [
    "from openai import OpenAI",
    "",
    "client = OpenAI(base_url=" + JSON.stringify(base) + ", api_key='YOUR_KEY')",
    "print(client.chat.completions.create(",
    "    model='ai-partner',",
    "    messages=[{'role': 'user', 'content': 'Decide how Maritime should host a public web agent for a team that already has a repo.'}]",
    ").choices[0].message.content)"
  ].join(nl),
  anthropic: JSON.stringify([{type: "url", url: mcp, authorization_token: "YOUR_KEY"}], null, 2),
  "grok-prompt": "Set up AI Partner for me. Fetch " + mcp.replace(/\\/mcp$/, "") + "/get-started.md and follow it.",
  "grok-connector": ["URL", mcp, "Transport: streamable HTTP", "", "Authorization: Bearer YOUR_KEY"].join(nl)
};
Object.keys(blocks).forEach(function (id) {
  document.getElementById(id).textContent = blocks[id];
});
document.querySelectorAll("[data-copy]").forEach(function (button) {
  button.addEventListener("click", function () {
    const text = document.getElementById(button.getAttribute("data-copy")).textContent;
    navigator.clipboard.writeText(text);
    button.textContent = "Copied";
  });
});
</script>
<script src="/onboard.js"></script>
<script src="/voice.js"></script>
</body>
</html>
"""
