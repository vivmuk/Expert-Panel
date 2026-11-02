def render_page(welcome):
    safe = welcome.replace("</", "<\\/")
    return PAGE.replace("__WELCOME__", safe)


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Partner</title>
<style>
  * { box-sizing: border-box; }
  html, body { height: 100%; }
  body {
    margin: 0;
    font: 17px/1.45 Georgia, "Iowan Old Style", Palatino, serif;
    background: #f6f3ec;
    color: #1c1917;
  }
  main {
    max-width: 40rem;
    height: 100dvh;
    margin: 0 auto;
    padding: 1rem 1rem 0.75rem;
    display: flex;
    flex-direction: column;
  }
  h1 { font-size: 1.7rem; font-weight: 600; margin: 0 0 0.25rem; }
  .sub { color: #57534e; margin: 0; }
  .log {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    margin: 0.75rem 0;
    flex: 1;
    min-height: 0;
    overflow: auto;
  }
  .user, .assistant {
    padding: 0.8rem 0.95rem;
    border-radius: 0.7rem;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .assistant { background: #fff; border: 1px solid #e7e5e4; }
  .user { background: #312e81; color: #f5f5f4; margin-left: 1.5rem; }
  form { display: flex; flex-direction: column; gap: 0.45rem; margin-top: 0.5rem; }
  textarea {
    width: 100%;
    font: inherit;
    padding: 0.65rem 0.7rem;
    border-radius: 0.55rem;
    border: 1px solid #d6d3d1;
    background: #fff;
    resize: vertical;
  }
  button {
    font: inherit;
    background: #312e81;
    color: #fff;
    border: 0;
    border-radius: 0.55rem;
    padding: 0.6rem 0.95rem;
    cursor: pointer;
  }
  button.secondary { background: transparent; color: #312e81; border: 1px solid #312e81; }
  button:disabled { opacity: 0.6; cursor: default; }
  .row { display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 0.75rem 0; }
  #status { min-height: 1.4em; margin: 0.25rem 0; }
  button:focus-visible, textarea:focus-visible { outline: 2px solid #312e81; outline-offset: 2px; }
</style>
</head>
<body>
<main>
  <h1>AI Partner</h1>
  <p class="sub">One consulting job, from the first question to a harness kit.</p>
  <div id="log" class="log"></div>
  <p id="status" class="sub" role="status"></p>
  <div class="row">
    <button type="button" id="cont" class="secondary" hidden>Continue</button>
    <button type="button" id="report" class="secondary" hidden>Download report</button>
    <button type="button" id="kit" class="secondary" hidden>Download harness kit</button>
    <button type="button" id="pack" class="secondary" hidden>Download skill pack</button>
    <button type="button" id="fresh" class="secondary">New chat</button>
  </div>
  <form id="form">
    <label class="sub" for="box">Message</label>
    <textarea id="box" rows="3" placeholder="Market entry for a medtech device into Germany"></textarea>
    <label class="sub" for="file">Optional templates or notes, txt, md, pdf, or docx</label>
    <input id="file" type="file" multiple accept=".txt,.md,.markdown,.pdf,.docx,text/plain">
    <button type="submit">Send</button>
  </form>
</main>
<script id="welcome" type="text/plain">__WELCOME__</script>
<script>
const STATUS = {
  panel: "Staffing a four-person panel.",
  red_team: "Running the red team.",
  blueprint: "Drawing the work chart.",
  research: "Searching public sources.",
  synthesize: "Writing the research brief.",
  skills: "Writing the skill pack."
};
const log = document.getElementById("log");
const status = document.getElementById("status");
const form = document.getElementById("form");
const box = document.getElementById("box");
const cont = document.getElementById("cont");
const reportBtn = document.getElementById("report");
const kitBtn = document.getElementById("kit");
const packBtn = document.getElementById("pack");
let pendingUploads = [];
let state = null;
let messages = [];
let running = false;

function add(role, text) {
  messages.push({ role: role, text: text });
  const div = document.createElement("div");
  div.className = role;
  div.textContent = text;
  log.appendChild(div);
}

function paint() {
  const phase = state && state.phase;
  const working = phase === "panel" || phase === "red_team" || phase === "blueprint" || phase === "research" || phase === "synthesize" || phase === "skills";
  cont.hidden = !working;
  const done = phase === "done";
  reportBtn.hidden = !done;
  kitBtn.hidden = !done;
  packBtn.hidden = !done;
}

function save() {
  localStorage.setItem("ai-partner-chat", JSON.stringify({ state: state, messages: messages }));
}

function setBusy(busy) {
  running = busy;
  form.querySelector("button").disabled = busy;
  box.disabled = busy;
  cont.disabled = busy;
}

async function post(message) {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: message, state: state || {}, uploads: pendingUploads })
  });
  const data = await res.json();
  pendingUploads = [];
  if (data.state) state = data.state;
  if (data.reply) add("assistant", data.reply);
  save();
  paint();
  if (data.error || !data.next) return null;
  return data.next;
}

async function run(message) {
  if (running) return;
  setBusy(true);
  try {
    let next = await post(message);
    let guard = 0;
    while (next && guard < 6) {
      guard += 1;
      status.textContent = STATUS[next] || "Working.";
      next = await post("");
    }
    status.textContent = "";
  } catch (err) {
    add("assistant", "The request failed. Your earlier answers are still in this chat. Send the message again.");
    status.textContent = "";
    save();
  } finally {
    setBusy(false);
    box.focus();
  }
}

function readUploads() {
  const input = document.getElementById("file");
  const files = Array.from(input.files || []).slice(0, 4);
  return Promise.all(files.map(function (file) {
    return new Promise(function (resolve) {
      if (file.size > 500000) {
        resolve(null);
        return;
      }
      const ext = (file.name.split(".").pop() || "").toLowerCase();
      const reader = new FileReader();
      reader.onload = function () {
        if (ext === "txt" || ext === "md" || ext === "markdown") {
          resolve({ name: file.name, text: String(reader.result || "") });
          return;
        }
        const bytes = new Uint8Array(reader.result);
        let binary = "";
        for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
        resolve({ name: file.name, base64: btoa(binary) });
      };
      if (ext === "txt" || ext === "md" || ext === "markdown") reader.readAsText(file);
      else reader.readAsArrayBuffer(file);
    });
  })).then(function (items) {
    input.value = "";
    return items.filter(Boolean);
  });
}

form.addEventListener("submit", function (ev) {
  ev.preventDefault();
  const text = box.value.trim();
  if (!text || running) return;
  add("user", text);
  box.value = "";
  readUploads().then(function (uploads) {
    pendingUploads = uploads;
    save();
    run(text);
  });
});

cont.addEventListener("click", function () { run(""); });

async function download(path, filename) {
  status.textContent = "Preparing the file.";
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state: state })
  });
  if (!res.ok) {
    status.textContent = "That file is not ready yet.";
    return;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  status.textContent = "";
}

reportBtn.addEventListener("click", function () { download("/api/chat/report", "report.md"); });
kitBtn.addEventListener("click", function () { download("/api/chat/kit", "harness-kit.zip"); });
packBtn.addEventListener("click", function () { download("/api/chat/skill-pack", "skill-pack.zip"); });

document.getElementById("fresh").addEventListener("click", function () {
  localStorage.removeItem("ai-partner-chat");
  location.reload();
});

try {
  const saved = JSON.parse(localStorage.getItem("ai-partner-chat") || "null");
  if (saved && Array.isArray(saved.messages)) {
    state = saved.state || null;
    saved.messages.forEach(function (item) { add(item.role, item.text); });
  }
} catch (err) {
  state = null;
}
if (!messages.length) add("assistant", document.getElementById("welcome").textContent);
paint();
</script>
</body>
</html>
"""
