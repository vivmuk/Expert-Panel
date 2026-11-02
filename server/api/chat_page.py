def render_page(welcome):
    return PAGE.replace("__WELCOME__", welcome.replace("</", "<\\/"))


PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Partner</title>
<link rel="stylesheet" href="/app.css">
</head>
<body>
<div class="bar"><span id="progress"></span></div>
<header class="top">
  <a class="brand" href="/"><span class="dot"></span> AI Partner</a>
  <nav class="links">
    <a href="/" aria-current="page">Chat</a>
    <a href="/deck">Deck</a>
    <a href="/connect">Connect</a>
  </nav>
</header>
<main class="wrap">
  <section id="hero" class="hero">
    <div>
      <p class="kicker">The First 1,000</p>
      <h1>Outcomes, not advice. <em>We hand you the agents that do the work.</em></h1>
      <p class="lede">Use AI Partner inside the agents you already use. <a href="/connect">Open Connect.</a></p>
    </div>
    <img src="/deck/img/01-title.webp" alt="Watercolor of a suitcase releasing small robots into a starry sky.">
  </section>
  <div id="steps" class="steps" hidden></div>
  <div id="log" class="log"></div>
  <div id="output" class="output" hidden></div>
  <p id="status" class="status" role="status"></p>
  <div id="downloads" class="row" hidden>
    <button type="button" id="report" class="ghost">Download report</button>
    <button type="button" id="kit" class="ghost">Download harness kit</button>
    <button type="button" id="pack" class="ghost">Download skill pack</button>
  </div>
  <form id="form">
    <label class="kicker" for="box">Message</label>
    <textarea id="box" rows="3" placeholder="Market entry for a medtech device into Germany"></textarea>
    <label class="kicker" for="file">Optional notes, txt, md, pdf, or docx</label>
    <input id="file" type="file" multiple accept=".txt,.md,.markdown,.pdf,.docx,text/plain">
    <div class="row">
      <button class="send" type="submit">Send</button>
      <button type="button" id="cont" class="ghost" hidden>Continue</button>
      <button type="button" id="fresh" class="ghost">New chat</button>
    </div>
  </form>
</main>
<script id="welcome" type="text/plain">__WELCOME__</script>
<script>
const STEPS = [
  ["intake", "Intake"],
  ["maturity", "Maturity"],
  ["panel", "Panel"],
  ["chart", "Work Chart"],
  ["research", "Research"],
  ["skills", "Skill Pack"],
  ["kit", "Kit"]
];
const STATUS = {
  panel: "Staffing a four-person panel.",
  red_team: "Running the red team.",
  blueprint: "Drawing the work chart.",
  research: "Searching public sources.",
  synthesize: "Writing the research brief.",
  skills: "Writing the skill pack."
};
const log = document.getElementById("log");
const output = document.getElementById("output");
const status = document.getElementById("status");
const form = document.getElementById("form");
const box = document.getElementById("box");
const cont = document.getElementById("cont");
const stepsEl = document.getElementById("steps");
const hero = document.getElementById("hero");
const downloads = document.getElementById("downloads");
const progress = document.getElementById("progress");
let state = null;
let messages = [];
let running = false;
let pendingUploads = [];
let view = null;

function phaseStep(phase) {
  if (phase === "ask_maturity") return 1;
  if (phase === "panel" || phase === "red_team") return 2;
  if (phase === "blueprint") return 3;
  if (phase === "ask_size" || phase === "research" || phase === "synthesize") return 4;
  if (phase === "skills") return 5;
  if (phase === "done") return 6;
  return 0;
}

function add(role, text) {
  messages.push({ role: role, text: text });
  const div = document.createElement("div");
  div.className = role;
  div.textContent = text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

function paintSteps() {
  const current = phaseStep(state && state.phase);
  stepsEl.hidden = false;
  stepsEl.textContent = "";
  progress.style.width = ((current + 1) / STEPS.length * 100) + "%";
  STEPS.forEach(function (step, index) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = step[1];
    button.disabled = index > current;
    if (index === (view == null ? current : view)) button.className = "on";
    else if (index < current) button.className = "done";
    button.addEventListener("click", function () {
      view = index === current ? null : index;
      paint();
    });
    stepsEl.appendChild(button);
  });
}

function card(title, text) {
  const el = document.createElement("div");
  el.className = "card";
  const h = document.createElement("h2");
  h.textContent = title;
  const p = document.createElement("p");
  p.textContent = text;
  el.appendChild(h);
  el.appendChild(p);
  return el;
}

function ownerClass(owner) {
  if (owner === "AI Agent") return "agent";
  if (owner === "Hybrid") return "hybrid";
  return "human";
}

function chartCard(title, steps) {
  const el = document.createElement("div");
  el.className = "card";
  const h = document.createElement("h2");
  h.textContent = title;
  el.appendChild(h);
  (steps || []).forEach(function (step) {
    const line = document.createElement("p");
    const tag = document.createElement("span");
    tag.className = "owner " + ownerClass(step.owner);
    tag.textContent = step.owner;
    line.appendChild(tag);
    line.appendChild(document.createTextNode(step.step + ". " + step.task));
    el.appendChild(line);
  });
  return el;
}

function showOutput(index) {
  output.textContent = "";
  output.hidden = false;
  log.hidden = true;
  const s = state || {};
  if (index === 0) output.appendChild(card("Intake", [s.problem, s.team, s.tools].filter(Boolean).join("\n\n") || "Name the job."));
  if (index === 1) output.appendChild(card("Maturity", s.maturity ? ("Maturity " + s.maturity) : "Waiting for a score from 1 to 4."));
  if (index === 2) {
    const panel = s.panel;
    const text = panel ? panel.personas.map(function (p) { return p.name + ", " + p.title + ". " + p.insight; }).join("\n\n") + "\n\n" + panel.consensus : "The panel has not run.";
    output.appendChild(card("Panel", text));
  }
  if (index === 3 && s.chart) {
    output.appendChild(chartCard("Today", s.chart.current));
    output.appendChild(chartCard("Agent era", s.chart.future));
  } else if (index === 3) output.appendChild(card("Work Chart", "The chart has not been drawn."));
  if (index === 4) {
    const brief = s.brief;
    const cites = brief && brief.citations ? brief.citations.map(function (c) { return c.title + ". " + c.url; }).join("\n") : "";
    output.appendChild(card("Research", brief ? (brief.summary + "\n\n" + cites) : "Research has not run."));
  }
  if (index === 5) output.appendChild(card("Skill Pack", s.pack ? ("Tier " + s.pack.tier + ". Download the pack from Kit.") : "The pack has not been written."));
  if (index === 6) output.appendChild(card("Kit", s.phase === "done" ? "The report, harness kit, and skill pack are ready." : "The kit is ready when the pack is written."));
}

function paint() {
  const phase = state && state.phase;
  const current = phaseStep(phase);
  const working = ["panel", "red_team", "blueprint", "research", "synthesize", "skills"].indexOf(phase) >= 0;
  cont.hidden = !working;
  const started = messages.some(function (m) { return m.role === "user"; });
  hero.hidden = started || !!(state && state.phase && state.phase !== "ask_problem");
  stepsEl.hidden = !started;
  if (started) paintSteps();
  const selected = view == null ? current : view;
  if ((started || hero.hidden) && view != null && view !== current) showOutput(view);
  else {
    output.hidden = true;
    log.hidden = false;
  }
  downloads.hidden = phase !== "done" && selected !== 6;
  if (selected === 6 && phase === "done") downloads.hidden = false;
}

function save() {
  localStorage.setItem("ai-partner-chat", JSON.stringify({ state: state, messages: messages }));
}

function setBusy(busy) {
  running = busy;
  form.querySelector(".send").disabled = busy;
  box.disabled = busy;
  cont.disabled = busy;
}

async function post(message) {
  const uploads = pendingUploads;
  pendingUploads = [];
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: message, state: state || {}, uploads: uploads })
  });
  const data = await res.json();
  if (data.state) state = data.state;
  if (data.reply) add("assistant", data.reply);
  view = null;
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
      if (file.size > 500000) { resolve(null); return; }
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
  })).then(function (items) { input.value = ""; return items.filter(Boolean); });
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
  if (!res.ok) { status.textContent = "That file is not ready yet."; return; }
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
document.getElementById("report").addEventListener("click", function () { download("/api/chat/report", "report.md"); });
document.getElementById("kit").addEventListener("click", function () { download("/api/chat/kit", "harness-kit.zip"); });
document.getElementById("pack").addEventListener("click", function () { download("/api/chat/skill-pack", "skill-pack.zip"); });
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
} catch (err) { state = null; }
if (!messages.length) add("assistant", document.getElementById("welcome").textContent);
paint();
</script>
</body>
</html>
"""
