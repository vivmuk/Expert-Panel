def render_page(welcome):
    return PAGE.replace("__WELCOME__", welcome.replace("</", "<\\/"))


PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Partner — Stop buying slides. Start shipping outcomes.</title>
<link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png">
<link rel="icon" href="/favicon-512.png" sizes="512x512" type="image/png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="stylesheet" href="/app.css">
</head>
<body>
<div class="bar"><span id="progress"></span></div>
<header class="top">
  <a class="brand" href="/chat"><img class="persona" src="/img/brand/avatar.webp" alt="AI Partner, a multi-arm robot with a floral calavera helmet." width="36" height="36"> AI Partner</a>
  <nav class="links">
    <a href="/chat" aria-current="page">Chat</a>
    <a href="/demos">Demos</a>
    <a href="/deck">Deck</a>
    <a href="/catalog">Catalog</a>
    <a href="/connect">Connect</a>
    <a href="/pricing">Pricing</a>
    <a class="primary" href="/pricing">Get API key</a>
  </nav>
</header>
<main class="wrap">
  <section id="hero" class="landing-hero">
    <img src="/img/brand/hero.webp" alt="A multi-arm robot with floral helmet art stands on the right of a blank sheet of paper, holding a chart, a plan, a pen, and a magnifying glass.">
    <div class="landing-copy">
      <p class="kicker">Outcomes, not blueprints.</p>
      <h1>Stop buying slides. Start shipping outcomes.</h1>
      <p class="lede">Describe the business problem. A panel of AI experts debates it, picks the top 5 moves, and ships the harness, skills and artifacts your team runs.</p>
      <div id="landing-form">
      <form id="form">
        <label class="kicker" for="box">What problem is costing you money?</label>
        <textarea id="box" rows="3" placeholder="Decide how Maritime should host a public web agent for a team that already has a repo."></textarea>
        <label class="kicker" for="file">Optional notes, txt, md, pdf, or docx</label>
        <input id="file" type="file" multiple accept=".txt,.md,.markdown,.pdf,.docx,text/plain">
        <div class="row">
          <button class="send" type="submit">Solve it</button>
          <button type="button" id="cont" class="ghost" hidden>Continue</button>
          <button type="button" id="fresh" class="ghost">New chat</button>
        </div>
      </form>
      </div>
      <div class="chips" id="chips"></div>
    </div>
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
  <div id="dock"></div>
</main>
<script id="welcome" type="text/plain">__WELCOME__</script>
<script>
const STEPS = [
  ["intake", "Intake"],
  ["maturity", "Maturity"],
  ["panel", "Panel"],
  ["chart", "Work Chart"],
  ["artifacts", "Artifacts"],
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
  if (phase === "ask_size" || phase === "research" || phase === "synthesize") return 5;
  if (phase === "skills") return 6;
  if (phase === "done") return 7;
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
  if (index === 4) renderArtifacts();
  if (index === 5) {
    const brief = s.brief;
    const cites = brief && brief.citations ? brief.citations.map(function (c) { return c.title + ". " + c.url; }).join("\n") : "";
    output.appendChild(card("Research", brief ? (brief.summary + "\n\n" + cites) : "Research has not run."));
  }
  if (index === 6) output.appendChild(card("Skill Pack", s.pack ? ("Tier " + s.pack.tier + ". Download the pack from Kit.") : "The pack has not been written."));
  if (index === 7) output.appendChild(card("Kit", s.phase === "done" ? "The report, harness kit, skill pack, and any generated artifacts are ready." : "The kit is ready when the pack is written."));
}

function renderArtifacts() {
  const holder = document.createElement("div");
  holder.id = "artifact-grid";
  output.appendChild(holder);
  const note = document.createElement("p");
  note.className = "kicker";
  note.textContent = "Strategy includes 5 catalog artifacts. Harness Build covers the full catalog.";
  output.appendChild(note);
  const all = document.createElement("button");
  all.type = "button";
  all.className = "ghost";
  all.textContent = "Download all";
  all.addEventListener("click", function () { download("/api/chat/kit", "harness-kit.zip"); });
  output.appendChild(all);
  fetch("/api/catalog").then(function (res) { return res.json(); }).then(function (data) {
    const recommended = recommendIds(state || {});
    data.groups.forEach(function (group) {
      const h = document.createElement("h2");
      h.textContent = group.task;
      holder.appendChild(h);
      const grid = document.createElement("div");
      grid.className = "deliver-grid";
      group.artifacts.forEach(function (item) {
        grid.appendChild(artifactCard(item, recommended.indexOf(item.id) >= 0));
      });
      holder.appendChild(grid);
    });
  });
}

function recommendIds(s) {
  const text = ((s.problem || "") + " " + (s.service_line || "")).toLowerCase();
  const picks = ["research-brief", "market-sizing", "issue-tree", "work-chart", "exec-memo"];
  if (text.indexOf("pric") >= 0) picks.push("pricing-analysis");
  if (text.indexOf("cost") >= 0 || text.indexOf("inventory") >= 0) picks.push("cost-reduction");
  return picks.slice(0, 6);
}

function artifactCard(item, recommended) {
  const card = document.createElement("article");
  card.className = "deliver";
  const h = document.createElement("h3");
  h.textContent = item.title;
  card.appendChild(h);
  if (recommended) {
    const badge = document.createElement("p");
    badge.className = "kicker";
    badge.textContent = "Recommended";
    card.appendChild(badge);
  }
  const p = document.createElement("p");
  p.textContent = item.purpose;
  card.appendChild(p);
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = (state && state.artifacts && state.artifacts[item.id]) ? "Regenerate" : "Generate";
  button.addEventListener("click", function () { generateArtifact(item.id, card); });
  card.appendChild(button);
  if (state && state.artifacts && state.artifacts[item.id]) showArtifact(card, item.id, state.artifacts[item.id]);
  return card;
}

function showArtifact(card, id, markdown) {
  let pre = card.querySelector("pre");
  if (!pre) {
    pre = document.createElement("pre");
    card.appendChild(pre);
  }
  pre.textContent = markdown;
  let row = card.querySelector(".row");
  if (!row) {
    row = document.createElement("div");
    row.className = "row";
    const copy = document.createElement("button");
    copy.type = "button";
    copy.className = "ghost";
    copy.textContent = "Copy";
    copy.addEventListener("click", function () {
      navigator.clipboard.writeText(pre.textContent);
      copy.textContent = "Copied";
      setTimeout(function () { copy.textContent = "Copy"; }, 1500);
    });
    const save = document.createElement("button");
    save.type = "button";
    save.className = "ghost";
    save.textContent = "Download .md";
    save.addEventListener("click", function () {
      const blob = new Blob([pre.textContent], {type: "text/markdown"});
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = id + ".md";
      link.click();
      URL.revokeObjectURL(url);
    });
    row.appendChild(copy);
    row.appendChild(save);
    card.appendChild(row);
  }
}

async function generateArtifact(id, card) {
  status.textContent = "Writing the artifact.";
  const res = await fetch("/api/chat/artifact", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({state: state || {}, artifact_id: id})
  });
  const data = await res.json();
  if (!res.ok) {
    status.textContent = (data.error && data.error.message) || "The artifact was not written.";
    return;
  }
  if (data.state) state = data.state;
  save();
  showArtifact(card, id, data.markdown);
  status.textContent = "";
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
  downloads.hidden = phase !== "done" && selected !== 7;
  if (selected === 7 && phase === "done") downloads.hidden = false;
  document.body.classList.toggle("chatting", hero.hidden);
  const slot = document.getElementById(hero.hidden ? "dock" : "landing-form");
  if (form.parentElement !== slot) slot.appendChild(form);
  const send = form.querySelector(".send");
  if (send) send.textContent = hero.hidden ? "Send" : "Solve it";
  const label = form.querySelector("label");
  if (label) label.textContent = hero.hidden ? "Message" : "What problem is costing you money?";
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
const EXAMPLES = [
  ["Maritime", "Decide how Maritime should host a public web agent for a team that already has a repo."],
  ["Keiki", "Choose which channels a Keiki customer agent should answer first."],
  ["Orchid", "Design how Orchid, at orchid.ai, hands an email thread to an agent."]
];
const chips = document.getElementById("chips");
EXAMPLES.forEach(function (item) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "ghost";
  button.textContent = item[0];
  button.addEventListener("click", function () {
    box.value = item[1];
    box.focus();
  });
  chips.appendChild(button);
});
let chip = 0;
setInterval(function () {
  if (document.body.classList.contains("chatting")) return;
  chip = (chip + 1) % EXAMPLES.length;
  box.placeholder = EXAMPLES[chip][1];
}, 4000);
paint();
</script>
<script src="/voice.js"></script>
</body>
</html>
"""
