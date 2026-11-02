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
  <section class="card">
    <h2>ChatGPT</h2>
    <p>Add a custom connector and paste the MCP URL. Send the bearer token in the Authorization header.</p>
    <pre id="gpt"></pre>
    <button type="button" data-copy="gpt">Copy</button>
  </section>
  <section class="card">
    <h2>Claude</h2>
    <p>On claude.ai, add a custom connector with the same MCP URL and bearer token. Claude Desktop speaks stdio, so this config runs the remote server through mcp-remote.</p>
    <pre id="claude"></pre>
    <button type="button" data-copy="claude">Copy</button>
  </section>
  <section class="card">
    <h2>Cursor</h2>
    <p>Put this in <span class="mono">.cursor/mcp.json</span>.</p>
    <pre id="cursor"></pre>
    <button type="button" data-copy="cursor">Copy</button>
  </section>
  <section class="card">
    <h2>OpenAI SDK</h2>
    <p>Point the client at the OpenAI-compatible base URL. The reply is the next turn of the same job. Send <span class="mono">ai_partner_state</span> back on the following request. The Python SDK keeps that field on the raw response.</p>
    <pre id="openai"></pre>
    <button type="button" data-copy="openai">Copy</button>
  </section>
  <section class="card">
    <h2>Anthropic SDK</h2>
    <p>The Messages API can attach this MCP server. We verified the MCP handshake on <span class="mono">/mcp</span>. We did not call Anthropic's cloud from this repo.</p>
    <pre id="anthropic"></pre>
    <button type="button" data-copy="anthropic">Copy</button>
  </section>
</main>
<script>
const mcp = "__MCP__";
const base = "__BASE__";
const nl = String.fromCharCode(10);
const blocks = {
  gpt: ["MCP URL", mcp, "", "Authorization: Bearer YOUR_KEY"].join(nl),
  claude: JSON.stringify({mcpServers: {"ai-partner": {command: "npx", args: ["-y", "mcp-remote", mcp, "--header", "Authorization: Bearer YOUR_KEY"]}}}, null, 2),
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
  anthropic: JSON.stringify([{type: "url", url: mcp, authorization_token: "YOUR_KEY"}], null, 2)
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
</body>
</html>
"""
