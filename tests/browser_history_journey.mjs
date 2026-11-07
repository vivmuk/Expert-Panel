import fs from "fs";
import http from "http";
import { spawn } from "child_process";

const ORIGIN = "http://127.0.0.1:8766";
const report = { steps: [] };
function note(name, value) {
  report.steps.push({ name, value });
  console.log(name, typeof value === "string" ? value : JSON.stringify(value));
}
function fail(reasons) {
  fs.writeFileSync("/opt/cursor/artifacts/history-browser.json", JSON.stringify(report, null, 2));
  console.error("FAILED", reasons.join(", "));
  process.exit(1);
}

function request(method, path, body) {
  return new Promise((resolve, reject) => {
    const data = body ? JSON.stringify(body) : null;
    const req = http.request({
      hostname: "127.0.0.1", port: 8766, path, method,
      headers: data ? { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(data) } : {}
    }, (res) => {
      let text = "";
      res.on("data", (chunk) => { text += chunk; });
      res.on("end", () => resolve({ status: res.statusCode, text }));
    });
    req.on("error", reject);
    if (data) req.write(data);
    req.end();
  });
}

const pending = new Map();
const events = [];
let nextId = 1;
let ws;

function send(method, params = {}) {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
}
function waitFor(method, timeout = 8000) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const timer = setInterval(() => {
      const index = events.findIndex((event) => event.method === method);
      if (index >= 0) {
        clearInterval(timer);
        resolve(events.splice(index, 1)[0]);
      } else if (Date.now() - start > timeout) {
        clearInterval(timer);
        reject(new Error("timeout " + method));
      }
    }, 40);
  });
}
async function evaluate(expression) {
  const result = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails).slice(0, 700));
  return result.result.value;
}
async function shot(name) {
  const image = await send("Page.captureScreenshot", { format: "png" });
  const file = "/opt/cursor/artifacts/" + name + ".png";
  fs.writeFileSync(file, Buffer.from(image.data, "base64"));
  return file;
}
async function connect(debuggerUrl) {
  pending.clear();
  events.length = 0;
  ws = new WebSocket(debuggerUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener("open", resolve);
    ws.addEventListener("error", reject);
  });
  ws.addEventListener("message", (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const job = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) job.reject(new Error(JSON.stringify(msg.error)));
      else job.resolve(msg.result);
    } else if (msg.method) events.push(msg);
  });
  await send("Page.enable");
  await send("Runtime.enable");
  await send("Emulation.setFocusEmulationEnabled", { enabled: true });
}
async function navigate(url) {
  events.length = 0;
  const loaded = waitFor("Page.loadEventFired");
  await send("Page.navigate", { url });
  await loaded;
  await new Promise((resolve) => setTimeout(resolve, 250));
}
async function reload() {
  events.length = 0;
  const loaded = waitFor("Page.loadEventFired");
  await send("Page.reload", { ignoreCache: true });
  await loaded;
  await new Promise((resolve) => setTimeout(resolve, 300));
}
async function key(name, code, vk) {
  const down = { type: name === "Enter" ? "keyDown" : "rawKeyDown", key: name, code, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk };
  if (name === "Enter") down.text = "\r";
  await send("Input.dispatchKeyEvent", down);
  await send("Input.dispatchKeyEvent", { type: "keyUp", key: name, code, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk });
}
async function focusInfo() {
  return evaluate(`(() => {
    const el = document.activeElement;
    return { tag: el && el.tagName, id: el && el.id, text: ((el && el.innerText) || "").replace(/\\s+/g, " ").slice(0, 60) };
  })()`);
}
async function tabUntil(pred, limit = 70) {
  await evaluate("document.body && document.body.focus()");
  for (let i = 0; i < limit; i++) {
    const info = await focusInfo();
    if (pred(info)) return { steps: i, info };
    await key("Tab", "Tab", 9);
    await new Promise((resolve) => setTimeout(resolve, 40));
  }
  return null;
}
async function waitForValue(read, pred, timeout = 12000) {
  const start = Date.now();
  let last;
  while (Date.now() - start < timeout) {
    last = await read();
    if (pred(last)) return last;
    await new Promise((resolve) => setTimeout(resolve, 80));
  }
  throw new Error("timeout " + JSON.stringify(last).slice(0, 300));
}
function overlap(a, b) {
  if (!a || !b) return false;
  return !(a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top);
}

const doneRes = await request("GET", "/__test/done-state");
const doneState = JSON.parse(doneRes.text);
const researchId = "aaaaaaaaaaaaaaaa";
const clinicId = "bbbbbbbbbbbbbbbb";
const doneId = "cccccccccccccccc";
function researchState() {
  return {
    chat_id: "researchpause01",
    phase: "research",
    problem: "Market entry for a medtech device into Germany.",
    team: "4 analysts",
    tools: "Excel and Veeva",
    maturity: 2,
    calls: 0
  };
}
function longItems() {
  const items = [];
  for (let i = 0; i < 14; i++) {
    items.push({ role: "user", text: "Note " + i + " on the German payer path and the local partner. " + "detail ".repeat(12) });
    items.push({ role: "assistant", text: "Recorded note " + i + " for this engagement." });
  }
  items.push({
    role: "card",
    card: { kind: "research", queries: {}, sources: [null], html: '<img src=x onerror="window.__xss=1">' }
  });
  return items;
}
function book(selected, projects) {
  return { schema: 3, selected, projects };
}
function researchProject(updated) {
  return { id: researchId, updated, state: researchState(), items: longItems() };
}
function clinicProject(updated) {
  return {
    id: clinicId,
    updated,
    state: { chat_id: "clinicpause0001", phase: "ask_context", problem: "Clinic scheduling for two nurses.", team: "", tools: "", maturity: null },
    items: [
      { role: "user", text: "Clinic scheduling for two nurses." },
      { role: "assistant", text: "Who is on the team, and which tools do they use today?" }
    ]
  };
}
function doneProject(updated) {
  return {
    id: doneId,
    updated,
    state: doneState,
    items: [
      { role: "user", text: doneState.problem },
      { role: "assistant", text: "The engagement is ready to reopen." }
    ]
  };
}
async function installHooks() {
  await send("Page.addScriptToEvaluateOnNewDocument", { source: `
    window.__chat = [];
    window.__files = [];
    window.__errors = [];
    window.addEventListener("error", function (ev) { window.__errors.push(String(ev.message)); });
    var orig = window.fetch;
    window.fetch = function (url, opts) {
      var path = String(url);
      var response = orig.apply(this, arguments);
      try {
        if (path === "/api/chat") {
          var body = JSON.parse((opts && opts.body) || "{}");
          window.__chat.push({ phase: body.state && body.state.phase, problem: body.state && body.state.problem, chat_id: body.state && body.state.chat_id });
        } else if (path.indexOf("/api/chat/") === 0) {
          response.then(function (res) {
            window.__files.push({ path: path, status: res.status, type: res.headers.get("content-type") });
          });
        }
      } catch (e) {}
      return response;
    };
  ` });
}
async function storeAndReload(value) {
  await evaluate(`localStorage.setItem("ai-partner-chat-v2", ${JSON.stringify(typeof value === "string" ? value : JSON.stringify(value))});`);
  await reload();
}
function stored() {
  return evaluate(`localStorage.getItem("ai-partner-chat-v2")`);
}

const chrome = spawn("/usr/local/bin/google-chrome", [
  "--headless=new", "--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage",
  "--remote-debugging-port=9222", "--user-data-dir=/tmp/chrome-history-fix",
  "--window-size=1280,900", "about:blank"
], { stdio: "ignore" });
for (let i = 0; i < 30; i++) {
  try { await request("GET", "/health"); break; } catch (err) { await new Promise((resolve) => setTimeout(resolve, 200)); }
}
let version = "";
for (let i = 0; i < 30; i++) {
  try {
    version = await new Promise((resolve, reject) => {
      http.get("http://127.0.0.1:9222/json/version", (res) => {
        let data = "";
        res.on("data", (chunk) => { data += chunk; });
        res.on("end", () => resolve(data));
      }).on("error", reject);
    });
    break;
  } catch (err) { await new Promise((resolve) => setTimeout(resolve, 200)); }
}
if (!version) fail(["chrome did not open"]);
const list = JSON.parse(await new Promise((resolve, reject) => {
  http.get("http://127.0.0.1:9222/json/list", (res) => {
    let data = "";
    res.on("data", (chunk) => { data += chunk; });
    res.on("end", () => resolve(data));
  }).on("error", reject);
}));
await connect(list.find((item) => item.type === "page").webSocketDebuggerUrl);
await installHooks();
await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
await navigate(ORIGIN + "/chat");

const corrupt = JSON.stringify({ schema: 99, secret: "keep-these-bytes", projects: [] });
await storeAndReload(corrupt);
const corruptView = await evaluate(`(() => ({
  raw: localStorage.getItem("ai-partner-chat-v2"),
  hidden: document.getElementById("project-bar").hidden,
  note: document.getElementById("history-note").textContent,
  recover: document.getElementById("recover-storage").hidden,
  errors: window.__errors.slice()
}))()`);
note("corrupt-open", corruptView);
await evaluate(`document.getElementById("fresh").click()`);
await evaluate(`document.getElementById("box").value = "A new problem that must not replace the stored bytes."; document.getElementById("form").requestSubmit();`);
await new Promise((resolve) => setTimeout(resolve, 400));
await reload();
const corruptAfter = await stored();
note("corrupt-after", corruptAfter === corrupt);

await request("POST", "/__test/reset", {});
const mainBook = book(researchId, [researchProject(30), clinicProject(20), doneProject(10)]);
await storeAndReload(mainBook);
await new Promise((resolve) => setTimeout(resolve, 400));
const paused = await evaluate(`(() => ({
  chats: window.__chat.length,
  errors: window.__errors.slice(),
  xss: window.__xss || null,
  onerror: document.body.innerHTML.indexOf("onerror=") >= 0,
  sources: (document.body.textContent.match(/0 sources/) || [])[0] || "",
  continue: Array.from(document.querySelectorAll("button")).some((button) => button.textContent.indexOf("Continue") >= 0),
  selected: document.getElementById("projects").value
}))()`);
note("paused-reload", paused);

const layout = await evaluate(`(() => {
  document.querySelector(".dock").scrollIntoView({ block: "end" });
  const dock = document.querySelector(".dock").getBoundingClientRect();
  const last = document.querySelector(".log").lastElementChild.getBoundingClientRect();
  const box = (r) => ({ top: Math.round(r.top), bottom: Math.round(r.bottom), left: Math.round(r.left), right: Math.round(r.right) });
  return {
    dock: box(dock), last: box(last),
    overlap: !(dock.right <= last.left || last.right <= dock.left || dock.bottom <= last.top || last.bottom <= dock.top),
    scrollWidth: document.documentElement.scrollWidth,
    width: document.documentElement.clientWidth,
    dockPosition: getComputedStyle(document.querySelector(".dock")).position
  };
})()`);
note("390-composer", layout);
note("shot-390-composer", await shot("history-390-composer"));
const contLayout = await evaluate(`(() => {
  const button = Array.from(document.querySelectorAll("button")).find((el) => el.textContent.indexOf("Continue") >= 0);
  button.scrollIntoView({ block: "center" });
  const b = button.getBoundingClientRect();
  const prev = button.closest("li").getBoundingClientRect();
  const dock = document.querySelector(".dock").getBoundingClientRect();
  const box = (r) => ({ top: Math.round(r.top), bottom: Math.round(r.bottom), left: Math.round(r.left), right: Math.round(r.right) });
  const bb = box(b), dd = box(dock);
  return { button: bb, dock: dd, overlapDock: !(bb.right <= dd.left || dd.right <= bb.left || bb.bottom <= dd.top || dd.bottom <= bb.top), inView: bb.top >= 0 && bb.bottom <= window.innerHeight };
})()`);
note("390-continue", contLayout);
note("shot-390-continue", await shot("history-390-continue"));

const tabbed = await tabUntil((info) => info.text && info.text.indexOf("Continue") >= 0);
note("tab-continue", tabbed);
await key("Enter", "Enter", 13);
const firstWave = await waitForValue(() => evaluate("window.__chat"), (rows) => rows.length >= 1);
note("continue-request", firstWave[0]);
await waitForValue(() => evaluate("window.__chat.length"), (n) => n >= 2, 4000).catch(() => null);
const advanced = await waitForValue(
  () => evaluate(`document.body.textContent.indexOf("German reimbursement") >= 0 && document.getElementById("projects").value`),
  (value) => value === researchId
);
note("after-continue", advanced);
const afterChats = await evaluate("window.__chat");
note("continue-ids", afterChats.map((row) => row.chat_id));

await evaluate(`(() => {
  const select = document.getElementById("projects");
  select.value = ${JSON.stringify(clinicId)};
  select.dispatchEvent(new Event("change", { bubbles: true }));
})()`);
await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
const intakeTab = await tabUntil((info) => info.id === "box" || info.tag === "TEXTAREA");
note("tab-intake", intakeTab);
if (intakeTab) {
  await send("Input.insertText", { text: "Team: 2 nurses. Tools: paper." });
  await key("Enter", "Enter", 13);
}
const intake = await waitForValue(
  () => evaluate("window.__chat"),
  (rows) => rows.some((row) => row.problem && row.problem.indexOf("Clinic") >= 0)
).catch((err) => ({ error: String(err), rows: null }));
const intakeRow = intake && intake.filter ? intake.filter((row) => row.problem && row.problem.indexOf("Clinic") >= 0)[0] : intake;
note("intake-390", intakeRow || intake);

await send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });
await evaluate(`(() => {
  const select = document.getElementById("projects");
  select.value = ${JSON.stringify(doneId)};
  select.dispatchEvent(new Event("change", { bubbles: true }));
})()`);
await reload();
const beforeFiles = await evaluate("window.__chat.length");
for (const label of ["Harness kit", "Client deck", "Skill pack", "Report"]) {
  await evaluate(`(() => {
    const button = Array.from(document.querySelectorAll("#project-files button")).find((el) => el.textContent === ${JSON.stringify(label)});
    if (!button) throw new Error("missing " + ${JSON.stringify(label)});
    button.click();
  })()`);
  await new Promise((resolve) => setTimeout(resolve, 200));
}
const files = await waitForValue(() => evaluate("window.__files"), (rows) => rows.length >= 4);
note("files-after-reload", { chatPosts: beforeFiles, files });
note("shot-desktop", await shot("history-desktop-done"));

await storeAndReload(book(researchId, [researchProject(30), clinicProject(20)]));
await request("POST", "/__test/hold", { hold: true });
await evaluate(`Array.from(document.querySelectorAll("button")).find((el) => el.textContent.indexOf("Continue") >= 0).click()`);
await waitForValue(() => evaluate("window.__chat.length"), (n) => n >= 1);
await evaluate(`(() => {
  const select = document.getElementById("projects");
  select.value = ${JSON.stringify(clinicId)};
  select.dispatchEvent(new Event("change", { bubbles: true }));
})()`);
await request("POST", "/__test/hold", { hold: false });
await new Promise((resolve) => setTimeout(resolve, 800));
const late = await evaluate(`(() => {
  const raw = JSON.parse(localStorage.getItem("ai-partner-chat-v2"));
  const research = raw.projects.find((project) => project.id === ${JSON.stringify(researchId)});
  const clinic = raw.projects.find((project) => project.id === ${JSON.stringify(clinicId)});
  return {
    selected: document.getElementById("projects").value,
    rail: document.getElementById("rail-title").textContent,
    logHasResearch: document.body.innerText.indexOf("German reimbursement") >= 0,
    storedPhase: research.state.phase,
    clinicProblem: clinic.state.problem
  };
})()`);
note("late-switch", late);

await request("POST", "/__test/reset", {});
const dozen = [researchProject(50)];
for (let i = 0; i < 11; i++) {
  const id = "d00000000000000" + i.toString(16);
  dozen.push({
    id,
    updated: i,
    state: { chat_id: id, phase: "ask_context", problem: "Filled project " + i },
    items: [{ role: "user", text: "Filled project " + i }]
  });
}
await storeAndReload(book(researchId, dozen));
await request("POST", "/__test/hold", { hold: true });
await evaluate(`Array.from(document.querySelectorAll("button")).find((el) => el.textContent.indexOf("Continue") >= 0).click()`);
await waitForValue(() => evaluate("window.__chat.length"), (n) => n >= 1);
await evaluate(`document.getElementById("fresh").click()`);
const refused = await evaluate(`(() => ({
  note: document.getElementById("history-note").textContent,
  count: document.getElementById("projects").options.length,
  selected: document.getElementById("projects").value
}))()`);
note("cap-refused", refused);
await request("POST", "/__test/hold", { hold: false });
const applied = await waitForValue(
  () => evaluate(`document.body.innerText.indexOf("German reimbursement") >= 0 && document.getElementById("projects").value`),
  (value) => value === researchId
).catch((err) => "timeout " + err.message);
note("cap-still-advanced", applied);

await request("POST", "/__test/reset", {});
await storeAndReload(book(clinicId, [clinicProject(5)]));
const created = JSON.parse(await new Promise((resolve, reject) => {
  const req = http.request({
    hostname: "127.0.0.1",
    port: 9222,
    method: "PUT",
    path: "/json/new?" + encodeURIComponent(ORIGIN + "/chat")
  }, (res) => {
    let data = "";
    res.on("data", (chunk) => { data += chunk; });
    res.on("end", () => resolve(data));
  });
  req.on("error", reject);
  req.end();
}));
const firstWs = ws;
await connect(created.webSocketDebuggerUrl);
await installHooks();
await waitForValue(() => evaluate("!!document.getElementById('fresh')"), (ready) => ready);
const pageB = ws;
ws = firstWs;
await evaluate(`document.getElementById("box").focus()`);
await send("Input.insertText", { text: "hello from tab a" });
await key("Enter", "Enter", 13);
await waitForValue(() => stored(), (raw) => raw && raw.indexOf("hello from tab a") >= 0);
ws = pageB;
await evaluate(`document.getElementById("fresh").click()`);
await new Promise((resolve) => setTimeout(resolve, 300));
const tabs = await evaluate(`(() => ({
  note: document.getElementById("history-note").textContent,
  raw: localStorage.getItem("ai-partner-chat-v2")
}))()`);
note("two-tabs", { note: tabs.note, kept: tabs.raw.indexOf("hello from tab a") >= 0 });

chrome.kill();
ws.close();
fs.writeFileSync("/opt/cursor/artifacts/history-browser.json", JSON.stringify(report, null, 2));

const failed = [];
if (corruptView.hidden) failed.push("warning hidden");
if (!corruptView.note.includes("not replaced")) failed.push("corrupt note");
if (corruptView.recover) failed.push("recover hidden");
if (corruptView.errors.length) failed.push("corrupt errors");
if (corruptAfter !== corrupt) failed.push("corrupt overwritten");
if (paused.chats !== 0) failed.push("auto request");
if (paused.errors.length) failed.push("render errors " + paused.errors.join(";"));
if (paused.xss) failed.push("xss");
if (paused.onerror) failed.push("onerror html");
if (!paused.sources) failed.push("malformed card");
if (!paused.continue) failed.push("no continue");
if (layout.overlap) failed.push("composer overlap");
if (layout.scrollWidth > layout.width + 1) failed.push("390 overflow");
if (!contLayout.inView) failed.push("continue offscreen");
if (contLayout.overlapDock) failed.push("continue overlap");
if (!tabbed) failed.push("tab continue");
if (!firstWave[0] || firstWave[0].phase !== "research" || firstWave[0].chat_id !== "researchpause01") failed.push("continue body");
if (advanced !== researchId) failed.push("continue project");
if (afterChats.some((row) => row.chat_id !== "researchpause01")) failed.push("continue other project");
if (!intakeTab) failed.push("tab composer");
if (!intakeRow || intakeRow.error || !String(intakeRow.problem || "").includes("Clinic")) failed.push("intake");
if (beforeFiles !== 0) failed.push("reload chat");
for (const path of ["/api/chat/kit", "/api/chat/deck.pptx", "/api/chat/skill-pack", "/api/chat/report"]) {
  const hit = files.find((row) => row.path === path);
  if (!hit || hit.status !== 200) failed.push("file " + path);
}
if (late.selected !== clinicId) failed.push("late selected");
if (late.logHasResearch) failed.push("late log");
if (late.storedPhase !== "research") failed.push("late stored " + late.storedPhase);
if (!String(late.clinicProblem).includes("Clinic")) failed.push("late clinic");
if (!refused.note.includes("Nothing was deleted")) failed.push("cap note");
if (refused.count !== 12 || refused.selected !== researchId) failed.push("cap switch");
if (applied !== researchId) failed.push("cap aborted");
if (!tabs.note.includes("Another tab")) failed.push("tab conflict note");
if (!tabs.raw.includes("hello from tab a")) failed.push("tab overwrite");
if (failed.length) fail(failed);
console.log("browser journey ok");
