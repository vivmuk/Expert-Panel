(function () {
  function copyText(button, text) {
    var write = navigator.clipboard && navigator.clipboard.writeText(text);
    var done = function () {
      button.textContent = "Copied";
      window.setTimeout(function () {
        button.textContent = "Copy";
      }, 1500);
    };
    if (write && write.then) write.then(done, done);
    else done();
  }
  window.copyText = copyText;

  function blocks(key) {
    var origin = location.origin;
    var mcp = origin + "/mcp";
    var base = origin + "/v1";
    var schema = origin + "/openapi.json";
    var nl = String.fromCharCode(10);
    var auth = "Authorization: Bearer " + key;
    var cursorConfig = btoa(JSON.stringify({ url: mcp, headers: { Authorization: auth } }));
    return {
      gpt: ["MCP URL", mcp, "", "GPT Actions schema", schema, "", auth].join(nl),
      claude: JSON.stringify(
        { mcpServers: { "ai-partner": { url: mcp, headers: { Authorization: auth } } } },
        null,
        2
      ),
      cursor: JSON.stringify(
        { mcpServers: { "ai-partner": { url: mcp, headers: { Authorization: auth } } } },
        null,
        2
      ),
      cursorLink:
        "cursor://anysphere.cursor-deeplink/mcp/install?name=ai-partner&config=" +
        encodeURIComponent(cursorConfig),
      openai: [
        "from openai import OpenAI",
        "",
        "client = OpenAI(base_url=" + JSON.stringify(base) + ", api_key=" + JSON.stringify(key) + ")",
        "print(client.chat.completions.create(",
        "    model='ai-partner',",
        "    messages=[{'role': 'user', 'content': 'Market entry for a medtech device into Germany.'}]",
        ").choices[0].message.content)",
      ].join(nl),
      openaijs: [
        "import OpenAI from 'openai';",
        "",
        "const client = new OpenAI({ baseURL: " + JSON.stringify(base) + ", apiKey: " + JSON.stringify(key) + " });",
        "const reply = await client.chat.completions.create({",
        "  model: 'ai-partner',",
        "  messages: [{ role: 'user', content: 'Market entry for a medtech device into Germany.' }]",
        "});",
        "console.log(reply.choices[0].message.content);",
      ].join(nl),
      anthropic: [
        "claude mcp add --transport http ai-partner " + mcp + " --header " + JSON.stringify(auth),
        "",
        JSON.stringify(
          { type: "url", url: mcp, name: "ai-partner", authorization_token: key },
          null,
          2
        ),
      ].join(nl),
      curl: [
        "curl " + base + "/chat/completions \\",
        "  -H " + JSON.stringify(auth) + " \\",
        "  -H 'Content-Type: application/json' \\",
        "  -d " +
          JSON.stringify(
            JSON.stringify({
              model: "ai-partner",
              messages: [{ role: "user", content: "Market entry for a medtech device into Germany." }],
            })
          ),
      ].join(nl),
    };
  }
  window.snippetBlocks = blocks;

  function fill(key) {
    var data = blocks(key || "YOUR_KEY");
    document.querySelectorAll("[data-snippet]").forEach(function (el) {
      var name = el.getAttribute("data-snippet");
      if (Object.prototype.hasOwnProperty.call(data, name)) el.textContent = data[name];
    });
    var link = document.getElementById("cursor-link");
    if (link) link.href = data.cursorLink;
  }
  window.fillSnippets = fill;

  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-copy]");
    if (!button) return;
    var id = button.getAttribute("data-copy");
    var node = id && document.getElementById(id);
    copyText(button, node ? node.textContent : "");
  });

  document.addEventListener("DOMContentLoaded", function () {
    if (document.body.getAttribute("data-snippets") === "1") {
      fill(document.body.getAttribute("data-key") || "YOUR_KEY");
    }
    document.querySelectorAll("pre, .mono").forEach(function (el) {
      if (el.closest("header")) return;
      if (el.id && document.querySelector('[data-copy="' + el.id + '"]')) return;
      var button = document.createElement("button");
      button.type = "button";
      button.className = "ghost";
      button.textContent = "Copy";
      button.addEventListener("click", function () {
        copyText(button, el.textContent.trim());
      });
      el.insertAdjacentElement("afterend", button);
    });
  });
})();
