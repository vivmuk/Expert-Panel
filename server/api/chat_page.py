"""The front page: one chatbot and the Connect pill. The engagement runs in place, driven by /chat.js."""
import json
from html import escape

from ..icons import icon
from .pages import FOOT, connect_pill, dots, head, header

EXAMPLES = (
    ("Maritime", "globe", "Decide how Maritime should host a public web agent for a team that already has a repo."),
    ("Keiki", "messages-square", "Choose which channels a Keiki customer agent should answer first."),
    ("Orchid", "send", "Design how Orchid, at orchid.ai, hands an email thread to an agent without dropping the conversation."),
)

CLIENT_ICONS = (
    "arrow-right", "check", "copy", "download", "external-link", "file-text", "globe", "link", "loader-circle",
    "package", "puzzle", "refresh-cw", "rotate-ccw", "search", "shield-check", "sparkles", "trophy", "users",
    "workflow", "messages-square", "triangle-alert", "plug", "chevron-down", "x", "file-search",
)


def render_page(welcome, origin=""):
    chips = "".join(
        f'<button type="button" class="chip" data-example="{escape(text)}">{icon(glyph)}{escape(name)}</button>'
        for name, glyph, text in EXAMPLES
    )
    icons = json.dumps({name: icon(name) for name in CLIENT_ICONS}).replace("</", "<\\/")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head("AI Partner · Your team directs. AI Partner agents do the work.")}
</head>
<body class="home">
{header("/chat")}
<main class="wrap" id="main">
  <section class="home-stage" id="hero" aria-labelledby="home-title">
    {dots()}
    <h1 class="home-title" id="home-title">What problem is costing you <em>money</em>?</h1>
    <p class="home-sub">AI Partner agents research it, 20 AI experts debate it, and your team gets the Top 5 moves and the harness kit. Your first engagement is free.</p>
    <form id="form" class="composer gb" autocomplete="off">
      <label class="sr-only" for="box">Describe the business problem</label>
      <textarea id="box" rows="3" placeholder="{escape(EXAMPLES[0][2])}" enterkeyhint="send"></textarea>
      <div class="composer-bar">
        <label class="icon-btn" title="Attach notes: txt, md, pdf, or docx">{icon("paperclip", "ico", "Attach notes")}<input id="file" type="file" multiple accept=".txt,.md,.markdown,.pdf,.docx,text/plain"></label>
        <div class="files" id="files"></div>
        <span class="hint"><kbd>Enter</kbd> to send · <kbd>Shift</kbd>+<kbd>Enter</kbd> new line</span>
        <button class="send" type="submit"><span class="send-label">Solve it</span>{icon("arrow-up")}</button>
      </div>
    </form>
    <div class="examples" role="group" aria-label="Example engagements"><span class="lbl">Try</span>{chips}</div>
    {connect_pill(origin)}
  </section>
  <section class="session" id="session" hidden aria-label="Engagement">
    <aside class="rail" aria-label="Progress">
      <div class="rail-head"><p class="kicker">Engagement</p><h2 id="rail-title">New engagement</h2></div>
      <ol class="stages" id="stages"></ol>
      <div class="meter-line" aria-hidden="true"><i id="meter"></i></div>
      <div class="rail-actions">
        <button type="button" class="btn small ghost" id="fresh">{icon("rotate-ccw")}New engagement</button>
      </div>
    </aside>
    <div class="thread">
      <ol class="log" id="log" aria-live="polite"></ol>
      <div class="typing" id="typing" hidden role="status"><span class="dotty" aria-hidden="true"><i></i><i></i><i></i></span><span class="shimmer" id="typing-text">Working</span><span class="elapsed" id="elapsed"></span></div>
      <div class="dock" id="dock"></div>
    </div>
  </section>
  <div id="onboard-slot" hidden></div>
</main>
{FOOT}
<script id="welcome" type="text/plain">{welcome.replace("</", "<\\/")}</script>
<script id="chat-icons" type="application/json">{icons}</script>
<script src="/chat.js" data-endpoint="/api/chat" defer></script>
<script src="/onboard.js" defer></script>
<script src="/voice.js"></script>
</body>
</html>
"""
