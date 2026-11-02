(function () {
  "use strict";
  var script = document.currentScript || document.querySelector('script[src="/chat.js"]');
  var ENDPOINT = (script && script.getAttribute("data-endpoint")) || "/api/chat";
  var STORE = "ai-partner-chat-v2";
  var AUTO = ["research", "synthesize", "panel", "debate", "judge", "red_team", "blueprint", "skills"];
  var ICONS = {};
  try { ICONS = JSON.parse(document.getElementById("chat-icons").textContent); } catch (e) { ICONS = {}; }

  var STAGES = [
    { label: "Brief", count: function () { return ""; } },
    { label: "Research", count: function (s) { return (s.sources || []).length ? (s.sources || []).length + " sources" : ""; } },
    { label: "20 experts", count: function (s) { return (s.experts || []).length ? (s.experts || []).length + "/20" : ""; } },
    { label: "Debate", count: function (s) { return (s.debate || []).length ? String((s.debate || []).length) : ""; } },
    { label: "Top 5", count: function (s) { return (s.top5 || []).length ? "ranked" : ""; } },
    { label: "Work chart", count: function (s) { return s.chart ? "drawn" : ""; } },
    { label: "Skill pack", count: function (s) { return s.pack ? "written" : ""; } },
    { label: "Harness kit", count: function () { return ""; } }
  ];
  var STATUS = {
    research: "Research agents are searching public sources",
    synthesize: "Writing the cited research brief",
    panel: "Seating the panel of 20 AI experts, five at a time",
    debate: "The experts are debating, two rounds",
    judge: "The judge is ranking the Top 5",
    red_team: "The red team is attacking the plan",
    blueprint: "Drawing the work chart",
    skills: "Writing the skill pack"
  };
  var MATURITY = [["1", "Invoice-led"], ["2", "Pilot-led"], ["3", "Hybrid"], ["4", "Machine-led"]];
  var SIZES = [["small", "Small", "one team"], ["medium", "Medium", "several teams"], ["large", "Large", "company-wide"]];

  var form = document.getElementById("form");
  var box = document.getElementById("box");
  var send = form.querySelector(".send");
  var sendLabel = form.querySelector(".send-label");
  var fileInput = document.getElementById("file");
  var filesEl = document.getElementById("files");
  var hero = document.getElementById("hero");
  var session = document.getElementById("session");
  var log = document.getElementById("log");
  var dock = document.getElementById("dock");
  var typing = document.getElementById("typing");
  var typingText = document.getElementById("typing-text");
  var elapsedEl = document.getElementById("elapsed");
  var stagesEl = document.getElementById("stages");
  var meter = document.getElementById("meter");
  var railTitle = document.getElementById("rail-title");

  var state = null;
  var items = [];
  var running = false;
  var lastMessage = "";
  var timer = null;

  function ico(name) {
    var span = document.createElement("span");
    span.innerHTML = ICONS[name] || "";
    return span.firstChild || document.createTextNode("");
  }

  function h(tag, attrs, kids) {
    var el = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (key) {
      var v = attrs[key];
      if (v == null || v === false) return;
      if (key === "class") el.className = v;
      else if (key === "text") el.textContent = v;
      else if (key.indexOf("on") === 0) el.addEventListener(key.slice(2), v);
      else el.setAttribute(key, v === true ? "" : v);
    });
    (kids || []).forEach(function (kid) {
      if (kid == null || kid === false) return;
      el.appendChild(typeof kid === "string" ? document.createTextNode(kid) : kid);
    });
    return el;
  }

  function hue(name) {
    var n = 0;
    for (var i = 0; i < (name || "").length; i++) n = (n * 31 + name.charCodeAt(i)) >>> 0;
    return 200 + (n % 140);
  }

  function initials(name) {
    var words = (name || "").replace(/\./g, " ").split(/\s+/).filter(function (w) { return w && ["dr", "prof", "mr", "ms", "mrs"].indexOf(w.toLowerCase()) < 0; });
    if (!words.length) return "AI";
    return (words[0][0] + (words.length > 1 ? words[words.length - 1][0] : "")).toUpperCase();
  }

  function avatar(name) {
    return h("span", { class: "initials", style: "--h:" + hue(name), "aria-hidden": "true", text: initials(name) });
  }

  function level(label, raw, cls) {
    var v = String(raw || "").toLowerCase();
    return h("span", { class: "level " + (cls || ""), "data-v": v }, [
      h("span", { text: label }),
      h("span", { class: "bars", "aria-hidden": "true" }, [h("i"), h("i"), h("i")]),
      h("b", { text: v ? v[0].toUpperCase() + v.slice(1) : "—" })
    ]);
  }

  function host(url) {
    try { return new URL(url).host.replace(/^www\./, ""); } catch (e) { return url; }
  }

  function owner(raw) {
    var v = String(raw || "Human").toLowerCase();
    var cls = v.indexOf("agent") >= 0 ? "agent" : v.indexOf("hybrid") >= 0 ? "hybrid" : "human";
    return h("span", { class: "own " + cls, text: raw || "Human" });
  }

  function cardShell(icon, title, sub, body) {
    return h("article", { class: "card gb" }, [
      h("header", { class: "card-head" }, [
        h("h3", {}, [ico(icon), " ", title]),
        sub ? h("span", { class: "pill cobalt", text: sub }) : null
      ])
    ].concat(body));
  }

  /* ---------- cards ---------- */
  function researchCard(card) {
    var queries = h("div", { class: "queries" }, (card.queries || []).map(function (q) { return h("span", { class: "pill", text: q }); }));
    var sources = h("ul", { class: "sources" }, (card.sources || []).map(function (s) {
      return h("li", {}, [h("a", { href: s.url, target: "_blank", rel: "noopener" }, [h("small", { text: host(s.url) }), h("b", { text: s.title })])]);
    }));
    return cardShell("search", "Research", (card.sources || []).length + " sources", [
      h("p", { class: "sub", text: (card.queries || []).length + " parallel web searches. Every source URL is kept." }), queries, sources
    ]);
  }

  function briefCard() {
    var brief = (state && state.brief) || {};
    return cardShell("file-search", "Cited research brief", (brief.citations || []).length + " citations", [
      h("p", { class: "brief-text", text: brief.summary || "" })
    ]);
  }

  function expertsCard(card) {
    var grid = h("div", { class: "expert-grid" }, (card.items || []).map(function (e, i) {
      return h("div", { class: "expert-card", style: "--i:" + i }, [
        h("header", {}, [avatar(e.name), h("div", {}, [h("b", { text: e.name }), h("small", { text: e.role })])]),
        h("p", { text: e.insight || e.lens || "" })
      ]);
    }));
    return cardShell("users", "Experts " + card.from + " to " + card.to + " of 20", "seated", [grid]);
  }

  function debateCard(card) {
    var list = h("ol", { class: "debate-list" }, (card.items || []).map(function (d, i) {
      var stance = String(d.stance || "").toLowerCase();
      return h("li", { style: "--i:" + i }, [avatar(d.name), h("div", {}, [
        h("p", { class: "who" }, [
          h("b", { text: d.name }),
          d.responding_to ? h("span", { class: "to", text: "to " + d.responding_to }) : null,
          stance ? h("span", { class: "stance " + stance, text: stance }) : null
        ]),
        h("p", { text: d.statement })
      ])]);
    }));
    return cardShell("messages-square", "Debate, round " + card.round, "part " + card.part + " of 2", [list]);
  }

  function top5Card(card) {
    var list = h("ol", { class: "top5" }, (card.items || []).map(function (t, i) {
      var backers = (t.backers || []).map(function (b) { return h("span", { class: "pill", text: b }); });
      var dissent = (t.dissenters || []).map(function (d) { return h("li", {}, [h("b", { text: d.name + ". " }), d.why || ""]); });
      return h("li", { style: "--i:" + i }, [
        h("span", { class: "rank", text: String(i + 1) }),
        h("div", {}, [
          h("h4", { text: t.title }),
          h("p", { text: t.detail }),
          h("div", { class: "levels" }, [
            level("Confidence", t.confidence), level("Impact", t.impact), level("Effort", t.effort, "effort"),
            t.citation_url ? h("a", { class: "cite", href: t.citation_url, target: "_blank", rel: "noopener" }, [ico("link"), "Source"]) : null
          ]),
          backers.length ? h("div", { class: "backers" }, [h("span", { text: "Backed by" })].concat(backers)) : null,
          dissent.length ? h("details", { class: "more" }, [h("summary", {}, ["Dissent", ico("chevron-down")]), h("ul", { class: "risk-list" }, dissent)]) : null
        ])
      ]);
    }));
    var panel = (state && state.panel) || {};
    return cardShell("trophy", "Top 5 moves", "judge's rank", [
      list,
      panel.consensus ? h("p", { class: "sub" }, [h("b", { text: "Consensus. " }), panel.consensus]) : null
    ]);
  }

  function redTeamCard() {
    var attacks = (state && state.attacks) || {};
    return cardShell("shield-check", "Red team", "adversarial pass", [
      h("p", {}, [h("b", { text: "Top risk. " }), attacks.top_risk || ""]),
      h("ul", { class: "risk-list" }, (attacks.attacks || []).map(function (a) {
        return h("li", {}, [h("b", { text: a.threat }), h("span", { text: (a.why ? a.why + " " : "") + "Mitigation: " + (a.mitigation || "") })]);
      }))
    ]);
  }

  function steps(rows) {
    return h("ol", { class: "steps-list" }, (rows || []).map(function (s) {
      return h("li", {}, [owner(s.owner), h("b", { text: s.step }), h("span", { class: "task", text: s.task })]);
    }));
  }

  function chartCard() {
    var chart = (state && state.chart) || {};
    return cardShell("workflow", "Work chart", "today and agent era", [
      h("div", { class: "chart-cols" }, [
        h("div", { class: "chart-col" }, [h("h4", { text: "Today" }), steps(chart.current)]),
        h("div", { class: "chart-col" }, [h("h4", { text: "Agent era" }), steps(chart.future)])
      ])
    ]);
  }

  function doneCard() {
    var s = state || {};
    var stats = [
      [(s.sources || []).length, "sources"], [(s.experts || []).length, "AI experts"], [(s.debate || []).length, "debate turns"],
      [(s.top5 || []).length, "top moves"], [s.maturity ? s.maturity + "/4" : "—", "AI maturity"]
    ].map(function (r) { return h("div", { class: "stat" }, [h("strong", { text: String(r[0]) }), h("span", { text: r[1] })]); });
    var status = h("p", { class: "status-line", role: "status" });
    var out = h("div", { class: "artifact-out" });
    var picks = h("div", { class: "artifact-picks" });
    loadArtifacts(picks, out, status);
    return h("article", { class: "card gb done-card live" }, [
      h("header", { class: "card-head" }, [h("h3", {}, [ico("package"), " The harness kit is ready"]), h("span", { class: "pill cobalt", text: "done" })]),
      h("div", { class: "stats" }, stats),
      h("div", { class: "downloads" }, [
        h("button", { type: "button", class: "btn primary small", onclick: function () { download("/api/chat/kit", "harness-kit.zip", status); } }, [ico("package"), "Harness kit"]),
        h("button", { type: "button", class: "btn small", onclick: function () { download("/api/chat/skill-pack", "skill-pack.zip", status); } }, [ico("puzzle"), "Skill pack"]),
        h("button", { type: "button", class: "btn small", onclick: function () { download("/api/chat/report", "report.md", status); } }, [ico("file-text"), "Report"]),
        h("button", { type: "button", class: "btn small ghost", onclick: saveJson }, [ico("download"), "JSON"])
      ]),
      h("p", { class: "sub", text: "Generate any catalog artifact from this engagement." }),
      picks, out, status,
      h("a", { class: "btn ghost small", href: "/connect" }, [ico("plug"), "Run the kit in your own agent"])
    ]);
  }

  function recommend() {
    var text = ((state && state.problem) || "").toLowerCase();
    var ids = ["research-brief", "exec-memo", "issue-tree", "work-chart", "roadmap"];
    if (text.indexOf("pric") >= 0) ids.unshift("pricing-analysis");
    if (text.indexOf("cost") >= 0) ids.unshift("cost-reduction");
    return ids.slice(0, 6);
  }

  function loadArtifacts(picks, out, status) {
    fetch("/api/catalog").then(function (res) { return res.json(); }).then(function (data) {
      var byId = {};
      (data.groups || []).forEach(function (g) { (g.artifacts || []).forEach(function (a) { byId[a.id] = a; }); });
      recommend().forEach(function (id) {
        var item = byId[id];
        if (!item) return;
        picks.appendChild(h("button", { type: "button", class: "chip", onclick: function (ev) { generate(item, ev.currentTarget, out, status); } }, [ico("sparkles"), item.title]));
      });
      picks.appendChild(h("a", { class: "chip", href: "/catalog" }, ["All artifacts", ico("arrow-right")]));
    }).catch(function () {});
  }

  function generate(item, button, out, status) {
    if (button.disabled) return;
    button.disabled = true;
    status.textContent = "Writing " + item.title + ".";
    fetch("/api/chat/artifact", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state: state || {}, artifact_id: item.id })
    }).then(read).then(function (data) {
      button.disabled = false;
      if (!data.ok) { status.textContent = (data.error && data.error.message) || "The artifact was not written. Try again."; return; }
      if (data.state) { state = data.state; save(); }
      status.textContent = "";
      var pre = h("pre", { text: data.markdown || "" });
      out.insertBefore(h("div", { class: "card" }, [
        h("header", { class: "card-head" }, [h("h3", { text: item.title }), h("div", { class: "downloads" }, [
          h("button", { type: "button", class: "btn small ghost", onclick: function (ev) { copyText(pre.textContent, ev.currentTarget); } }, [ico("copy"), "Copy"]),
          h("button", { type: "button", class: "btn small ghost", onclick: function () { blobSave(pre.textContent, item.id + ".md", "text/markdown"); } }, [ico("download"), ".md"])
        ])]), pre
      ]), out.firstChild);
    }).catch(function () { button.disabled = false; status.textContent = "The request failed. Try again."; });
  }

  function renderCard(card) {
    if (!card || !card.kind) return null;
    if (card.kind === "research") return researchCard(card);
    if (card.kind === "brief") return briefCard();
    if (card.kind === "experts") return expertsCard(card);
    if (card.kind === "debate") return debateCard(card);
    if (card.kind === "top5") return top5Card(card);
    if (card.kind === "red_team") return redTeamCard();
    if (card.kind === "chart") return chartCard();
    if (card.kind === "done") return doneCard();
    return null;
  }

  /* ---------- thread ---------- */
  function avatarImg() {
    return h("img", { class: "av", src: "/img/brand/avatar.webp", alt: "", width: "32", height: "32" });
  }

  function quick(kind) {
    var rows = kind === "maturity" ? MATURITY.map(function (m) { return [m[0], m[0] + " · " + m[1]]; })
      : SIZES.map(function (s) { return [s[0], s[1] + " · " + s[2]]; });
    return h("div", { class: "quick" }, rows.map(function (r) {
      return h("button", { type: "button", class: "chip", "data-quick": r[0], onclick: function () { if (!running) submit(r[0]); } }, [r[1]]);
    }));
  }

  function renderItem(item, index) {
    if (item.role === "user") return h("li", { class: "msg me" }, [h("div", { class: "bubble", text: item.text })]);
    if (item.role === "card") {
      var card = renderCard(item.card);
      return card ? h("li", { class: "msg card-msg" }, [avatarImg(), h("div", { class: "body" }, [card])]) : null;
    }
    if (item.role === "error") return h("li", { class: "msg" }, [avatarImg(), errorCard(item, index)]);
    var last = index === items.length - 1;
    var phase = state && state.phase;
    var extra = null;
    if (last && item.ask === "maturity" && phase === "ask_maturity") extra = quick("maturity");
    if (last && item.ask === "size" && phase === "ask_size") extra = quick("size");
    return h("li", { class: "msg" }, [avatarImg(), h("div", {}, [h("div", { class: "bubble", text: item.text }), extra])]);
  }

  function errorCard(item, index) {
    var last = index === items.length - 1;
    var canRetry = last && item.retry;
    return h("div", { class: "error-card" }, [
      h("p", {}, [ico("triangle-alert"), " ", item.text]),
      canRetry || (last && item.fresh) ? h("div", { class: "downloads" }, [
        canRetry ? h("button", { type: "button", class: "btn small primary", onclick: retry }, [ico("refresh-cw"), item.resume ? "Continue" : "Retry"]) : null,
        last && item.fresh ? h("button", { type: "button", class: "btn small ghost", onclick: fresh }, [ico("rotate-ccw"), "New engagement"]) : null
      ]) : null
    ]);
  }

  function paintLog() {
    log.textContent = "";
    items.forEach(function (item, i) {
      var node = renderItem(item, i);
      if (node) log.appendChild(node);
    });
  }

  function append(item) {
    items.push(item);
    paintLog();
    save();
    scrollDown();
  }

  function scrollDown() {
    var last = log.lastElementChild;
    if (!last) return;
    var top = last.getBoundingClientRect().top + window.scrollY - 90;
    window.scrollTo({ top: Math.max(top, 0), behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }

  function stageIndex(phase) {
    if (!phase || phase.indexOf("ask_") === 0 && phase !== "ask_size") return 0;
    if (phase === "research" || phase === "synthesize") return 1;
    if (phase === "panel") return 2;
    if (phase === "debate") return 3;
    if (phase === "judge" || phase === "red_team") return 4;
    if (phase === "blueprint") return 5;
    if (phase === "ask_size" || phase === "skills") return 6;
    if (phase === "done") return 8;
    return 0;
  }

  function paintRail() {
    var s = state || {};
    var current = stageIndex(s.phase);
    stagesEl.textContent = "";
    STAGES.forEach(function (stage, i) {
      var done = i < current;
      var active = i === current;
      stagesEl.appendChild(h("li", { class: done ? "done" : active ? "active" : "", "aria-current": active ? "step" : null }, [
        h("span", { class: "n" }, [done ? ico("check") : String(i + 1)]),
        h("span", { class: "lbl", text: stage.label }),
        h("span", { class: "count", text: stage.count(s) })
      ]));
    });
    var pct = Math.min(100, Math.round(current / STAGES.length * 100));
    if (s.phase === "panel" || s.phase === "debate") {
      var part = s.phase === "panel" ? (s.experts || []).length / 20 : (s.debate || []).length / 40;
      pct = Math.round((current + part) / STAGES.length * 100);
    }
    meter.style.setProperty("--v", pct + "%");
    railTitle.textContent = s.problem ? (s.problem.length > 110 ? s.problem.slice(0, 107) + "…" : s.problem) : "New engagement";
  }

  function paint() {
    var started = items.some(function (i) { return i.role === "user"; });
    document.body.classList.toggle("chatting", started);
    session.hidden = !started;
    hero.hidden = started;
    var slot = started ? dock : hero;
    if (form.parentElement !== slot) {
      if (started) dock.appendChild(form);
      else hero.insertBefore(form, hero.querySelector(".examples"));
    }
    sendLabel.textContent = started ? "Send" : "Solve it";
    box.placeholder = started ? placeholder() : box.placeholder;
    if (started) { paintRail(); paintLog(); }
  }

  function placeholder() {
    var phase = state && state.phase;
    if (phase === "ask_context") return "Who is on the team, and which tools do they use?";
    if (phase === "ask_maturity") return "Score 1 to 4, or pick one above.";
    if (phase === "ask_size") return "Small, medium, or large.";
    if (phase === "done") return "Describe a new problem to start another engagement.";
    return "Message AI Partner";
  }

  /* ---------- network ---------- */
  function read(res) {
    return res.json().catch(function () { return {}; }).then(function (data) { data.ok = res.ok; data.status = res.status; return data; });
  }

  function setBusy(busy, phase) {
    running = busy;
    send.disabled = busy;
    box.disabled = busy;
    typing.hidden = !busy;
    clearInterval(timer);
    if (!busy) { elapsedEl.textContent = ""; return; }
    var start = Date.now();
    typingText.textContent = STATUS[phase] || "Reading your answer";
    elapsedEl.textContent = "0s";
    timer = setInterval(function () { elapsedEl.textContent = Math.round((Date.now() - start) / 1000) + "s"; }, 1000);
    dock.parentElement.insertBefore(typing, dock);
  }

  function post(message) {
    return fetch(ENDPOINT, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: message, state: state || {}, uploads: message ? takeUploads() : [] })
    }).then(read);
  }

  function handle(data) {
    if (data.state) state = data.state;
    var err = data.error;
    if (!data.ok || err) {
      var code = err && err.code;
      var text = (err && err.message) || "The request failed. Your earlier answers are still here.";
      append({ role: "error", text: text, retry: code !== "budget" && code !== "tamper", fresh: code === "budget" || code === "tamper" || code === "spend_limit" });
      return null;
    }
    if (data.card) {
      append({ role: "card", card: data.card });
      if (data.card.kind === "chart" && state && state.phase === "ask_size") append({ role: "assistant", text: tail(data.reply), ask: "size" });
    } else if (data.reply) {
      var phase = state && state.phase;
      append({ role: "assistant", text: data.reply, ask: phase === "ask_maturity" ? "maturity" : phase === "ask_size" ? "size" : null });
    }
    paintRail();
    return data.next || null;
  }

  function tail(reply) {
    var parts = String(reply || "").split("\n\n");
    return parts[parts.length - 1] || "Is the client small, medium, or large?";
  }

  function run(message) {
    if (running) return Promise.resolve();
    lastMessage = message;
    setBusy(true, message ? null : state && state.phase);
    var guard = 0;
    function step(msg) {
      return post(msg).then(function (data) {
        var next = handle(data);
        if (next && guard < 20) {
          guard += 1;
          lastMessage = "";
          typingText.textContent = STATUS[next] || "Working";
          return step("");
        }
      });
    }
    return step(message).catch(function () {
      append({ role: "error", text: "The connection dropped. Your earlier answers are still here.", retry: true });
    }).then(function () {
      setBusy(false);
      paint();
      if (window.matchMedia("(pointer: fine)").matches) box.focus();
    });
  }

  function retry() {
    if (running) return;
    var phase = state && state.phase;
    items = items.filter(function (i, idx) { return !(i.role === "error" && idx === items.length - 1); });
    paintLog();
    run(AUTO.indexOf(phase) >= 0 ? "" : lastMessage);
  }

  function submit(text) {
    text = String(text || "").trim();
    if (!text || running) return;
    if (state && state.phase === "done" && text.length > 15) {
      state = null;
      items = [{ role: "assistant", text: welcome() }];
    }
    append({ role: "user", text: text });
    paint();
    box.value = "";
    autosize();
    run(text);
  }

  /* ---------- uploads ---------- */
  var uploads = [];
  function takeUploads() { var u = uploads; uploads = []; paintFiles(); return u; }
  function paintFiles() {
    filesEl.textContent = "";
    uploads.forEach(function (u, i) {
      filesEl.appendChild(h("span", { class: "pill" }, [u.name, h("button", { type: "button", class: "linkish", "aria-label": "Remove " + u.name, onclick: function () { uploads.splice(i, 1); paintFiles(); } }, [ico("x")])]));
    });
  }
  fileInput.addEventListener("change", function () {
    Array.prototype.slice.call(fileInput.files || [], 0, 4).forEach(function (file) {
      if (file.size > 500000) return;
      var ext = (file.name.split(".").pop() || "").toLowerCase();
      var reader = new FileReader();
      var text = ext === "txt" || ext === "md" || ext === "markdown";
      reader.onload = function () {
        if (text) uploads.push({ name: file.name, text: String(reader.result || "") });
        else {
          var bytes = new Uint8Array(reader.result);
          var bin = "";
          for (var i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
          uploads.push({ name: file.name, base64: btoa(bin) });
        }
        paintFiles();
      };
      if (text) reader.readAsText(file); else reader.readAsArrayBuffer(file);
    });
    fileInput.value = "";
  });

  /* ---------- files out ---------- */
  function blobSave(body, name, type) {
    var url = URL.createObjectURL(body instanceof Blob ? body : new Blob([body], { type: type }));
    var a = h("a", { href: url, download: name });
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  function download(path, name, status) {
    status.textContent = "Preparing " + name + ".";
    fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ state: state }) })
      .then(function (res) {
        if (!res.ok) throw new Error("not ready");
        return res.blob();
      })
      .then(function (blob) { blobSave(blob, name); status.textContent = ""; })
      .catch(function () { status.textContent = "That file is not ready yet. Try again in a moment."; });
  }

  function saveJson() {
    var s = state || {};
    var keep = { problem: s.problem, team: s.team, tools: s.tools, maturity: s.maturity, brief: s.brief, experts: s.experts, debate: s.debate, top5: s.top5, panel: s.panel, attacks: s.attacks, chart: s.chart };
    blobSave(JSON.stringify(keep, null, 2), "engagement.json", "application/json");
  }

  function copyText(text, button) {
    if (navigator.clipboard) navigator.clipboard.writeText(text);
    var label = button.lastChild;
    var was = label.textContent;
    label.textContent = "Copied";
    setTimeout(function () { label.textContent = was; }, 1400);
  }

  /* ---------- persistence ---------- */
  function save() {
    try { localStorage.setItem(STORE, JSON.stringify({ state: state, items: items })); } catch (e) { /* storage full or blocked */ }
  }

  function welcome() { return document.getElementById("welcome").textContent; }

  function fresh() {
    try { localStorage.removeItem(STORE); } catch (e) { /* ignore */ }
    state = null;
    items = [{ role: "assistant", text: welcome() }];
    uploads = [];
    paintFiles();
    paint();
    window.scrollTo(0, 0);
    box.focus();
  }

  /* ---------- composer ---------- */
  function autosize() {
    box.style.height = "auto";
    box.style.height = Math.min(box.scrollHeight, window.innerHeight * 0.4) + "px";
  }
  box.addEventListener("input", autosize);
  box.addEventListener("keydown", function (ev) {
    if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing) {
      ev.preventDefault();
      submit(box.value);
    }
  });
  form.addEventListener("submit", function (ev) { ev.preventDefault(); submit(box.value); });
  document.querySelectorAll("[data-example]").forEach(function (chip) {
    chip.addEventListener("click", function () { submit(chip.getAttribute("data-example")); });
  });
  document.getElementById("fresh").addEventListener("click", fresh);

  /* ---------- boot ---------- */
  try {
    var saved = JSON.parse(localStorage.getItem(STORE) || "null");
    if (saved && Array.isArray(saved.items)) { state = saved.state || null; items = saved.items; }
  } catch (e) { state = null; items = []; }
  if (!items.length) items = [{ role: "assistant", text: welcome() }];
  var paused = state && AUTO.indexOf(state.phase) >= 0;
  var lastItem = items[items.length - 1];
  if (paused && !(lastItem && lastItem.role === "error")) {
    items.push({ role: "error", text: "The engagement paused while the agents were working. Continue from where it stopped.", retry: true, resume: true });
  }
  paint();
  if (!items.some(function (i) { return i.role === "user"; }) && window.matchMedia("(pointer: fine)").matches) box.focus();
  var tick = 0;
  var placeholders = Array.prototype.map.call(document.querySelectorAll("[data-example]"), function (c) { return c.getAttribute("data-example"); });
  setInterval(function () {
    if (document.body.classList.contains("chatting") || document.activeElement === box && box.value) return;
    tick = (tick + 1) % placeholders.length;
    box.placeholder = placeholders[tick];
  }, 4500);
})();
