(function () {
  "use strict";
  var script = document.currentScript || document.querySelector('script[src="/chat.js"]');
  var ENDPOINT = (script && script.getAttribute("data-endpoint")) || "/api/chat";
  var STORE = "ai-partner-chat-v2";
  var VISITOR_KEY = "ai-partner-visitor";
  var HISTORY_KEY = "ai-partner-has-history";
  var AUTO = ["research", "synthesize", "panel", "debate", "judge", "frame", "red_team", "plan", "blueprint", "skills"];
  var ICONS = {};
  try { ICONS = JSON.parse(document.getElementById("chat-icons").textContent); } catch (e) { ICONS = {}; }

  var STAGES = [
    { label: "Brief", count: function () { return ""; } },
    { label: "Research", count: function (s) { return (s.sources || []).length ? (s.sources || []).length + " sources" : ""; } },
    { label: "20 experts", count: function (s) { return (s.experts || []).length ? (s.experts || []).length + "/20" : ""; } },
    { label: "Debate", count: function (s) { return (s.debate || []).length ? String((s.debate || []).length) : ""; } },
    { label: "Top 5", count: function (s) { return (s.top5 || []).length ? "ranked" : ""; } },
    { label: "Plan", count: function (s) { return s.plan ? "90 days" : s.frame ? "framed" : ""; } },
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
    frame: "The partner is framing the question, the options, and the value at stake",
    red_team: "The red team is attacking the plan",
    plan: "The engagement manager is writing the risk register, the measures, and the first 90 days",
    blueprint: "Drawing the work chart",
    skills: "Writing the skill pack"
  };
  var NAV = [
    ["summary", "Summary", function () { return ""; }],
    ["question", "The question", function (s) { return (s.frame && s.frame.options || []).length + " options"; }, function (s) { return !!s.frame; }],
    ["market", "Research", function (s) { return (s.sources || []).length + " sources"; }],
    ["experts", "20 experts", function (s) { return (s.experts || []).length + "/20"; }],
    ["debate", "Debate", function (s) { return String((s.debate || []).length); }],
    ["synthesis", "Judge", function () { return "synthesis"; }],
    ["top5", "Top 5", function () { return "ranked"; }],
    ["value", "Value at stake", function (s) { return (s.frame && s.frame.value_drivers || []).length + " drivers"; }, function (s) { return !!s.frame; }],
    ["risks", "Risk register", function (s) { return (s.plan && s.plan.risks || []).length + " risks"; }, function (s) { return !!s.plan; }],
    ["maturity", "Maturity", function (s) { return s.maturity ? s.maturity + "/4" : ""; }],
    ["chart", "Work chart", function () { return "swimlanes"; }],
    ["plan", "First 90 days", function (s) { return (s.plan && s.plan.milestones || []).length + " milestones"; }, function (s) { return !!s.plan; }],
    ["skills", "Skill pack", function () { return "kit"; }],
    ["artifacts", "Deliverables", function () { return "deck + 4"; }],
    ["method", "Method", function () { return "appendix"; }]
  ];
  var STAGE_OF = { research: 1, brief: 1, experts: 2, debate: 3, top5: 4, frame: 5, red_team: 5, plan: 5, chart: 6, done: 7 };
  var DOWNLOADS = {
    kit: ["/api/chat/kit", "harness-kit.zip"],
    "skill-pack": ["/api/chat/skill-pack", "skill-pack.zip"],
    report: ["/api/chat/report", "report.md"],
    pptx: ["/api/chat/deck.pptx", "client-deck.pptx"]
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
  var reportNode = null;
  var viewing = false;
  var booted = false;
  var doneStatus = null;
  var docs = {};
  var H = window.AIPartnerHistory;
  var book = H.blank();
  var seen = { raw: null, blocked: false };
  var generation = 0;
  var controller = null;
  var historyNote = "";

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

  function safeUrl(url) {
    return /^https?:\/\//i.test(String(url || "")) ? String(url) : "";
  }

  function host(url) {
    var safe = safeUrl(url);
    if (!safe) return "";
    try { return new URL(safe).host.replace(/^www\./, ""); } catch (e) { return ""; }
  }

  function list(value) {
    return Array.isArray(value) ? value : [];
  }

  function objects(value) {
    return list(value).filter(function (item) { return !!item && typeof item === "object"; });
  }

  function texts(value) {
    return list(value).filter(function (item) { return typeof item === "string" && item; });
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
    var queries = texts(card.queries);
    var sources = objects(card.sources);
    var queryRow = h("div", { class: "queries" }, queries.map(function (q) { return h("span", { class: "pill", text: q }); }));
    var sourceList = h("ul", { class: "sources" }, sources.map(function (s) {
      var href = safeUrl(s.url);
      var label = h("span", {}, [h("small", { text: host(s.url) || "source" }), h("b", { text: s.title || "" })]);
      return h("li", {}, [href ? h("a", { href: href, target: "_blank", rel: "noopener" }, [label]) : label]);
    }));
    return cardShell("search", "Research", sources.length + " sources", [
      h("p", { class: "sub", text: queries.length + " parallel web searches. Every source URL is kept." }), queryRow, sourceList
    ]);
  }

  function briefCard() {
    var brief = (state && state.brief) || {};
    return cardShell("file-search", "Cited research brief", list(brief.citations).length + " citations", [
      h("p", { class: "brief-text", text: brief.summary || "" })
    ]);
  }

  function expertsCard(card) {
    var grid = h("div", { class: "expert-grid" }, objects(card.items).map(function (e, i) {
      return h("div", { class: "expert-card", style: "--i:" + i }, [
        h("header", {}, [avatar(e.name || ""), h("div", {}, [h("b", { text: e.name || "" }), h("small", { text: e.role || "" })])]),
        h("p", { text: e.insight || e.lens || "" })
      ]);
    }));
    return cardShell("users", "Experts " + card.from + " to " + card.to + " of 20", "seated", [grid]);
  }

  function debateCard(card) {
    var list = h("ol", { class: "debate-list" }, objects(card.items).map(function (d, i) {
      var stance = typeof d.stance === "string" ? d.stance.toLowerCase() : "";
      return h("li", { style: "--i:" + i }, [avatar(d.name || ""), h("div", {}, [
        h("p", { class: "who" }, [
          h("b", { text: d.name || "" }),
          d.responding_to ? h("span", { class: "to", text: "to " + d.responding_to }) : null,
          stance ? h("span", { class: "stance " + stance, text: stance }) : null
        ]),
        h("p", { text: d.statement || "" })
      ])]);
    }));
    return cardShell("messages-square", "Debate, round " + card.round, "part " + card.part + " of 2", [list]);
  }

  function top5Card(card) {
    var list = h("ol", { class: "top5" }, objects(card.items).map(function (t, i) {
      var backers = texts(t.backers).map(function (b) { return h("span", { class: "pill", text: b }); });
      var dissent = objects(t.dissenters).map(function (d) { return h("li", {}, [h("b", { text: (d.name || "") + ". " }), d.why || ""]); });
      return h("li", { style: "--i:" + i }, [
        h("span", { class: "rank", text: String(i + 1) }),
        h("div", {}, [
          h("h4", { text: t.title }),
          h("p", { text: t.detail }),
          h("div", { class: "levels" }, [
            level("Confidence", t.confidence), level("Impact", t.impact), level("Effort", t.effort, "effort"),
            safeUrl(t.citation_url) ? h("a", { class: "cite", href: safeUrl(t.citation_url), target: "_blank", rel: "noopener" }, [ico("link"), "Source"]) : null
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
      h("ul", { class: "risk-list" }, objects(attacks.attacks).map(function (a) {
        return h("li", {}, [h("b", { text: a.threat || "" }), h("span", { text: (a.why ? a.why + " " : "") + "Mitigation: " + (a.mitigation || "") })]);
      }))
    ]);
  }

  function sentence(text) {
    var t = String(text || "").replace(/\s+/g, " ").trim();
    return !t || /[.!?]$/.test(t) ? t : t + ".";
  }

  function verdictPill(verdict) {
    var v = String(verdict || "").toLowerCase();
    var cls = v === "recommended" ? "cobalt" : v === "conditional" ? "amber" : "ink";
    return h("span", { class: "pill " + cls, text: v || "option" });
  }

  function frameCard() {
    var frame = (state && state.frame) || {};
    var scq = h("div", { class: "scq" }, [
      ["Situation", frame.situation], ["Complication", frame.complication], ["Question", frame.key_question]
    ].filter(function (r) { return r[1]; }).map(function (r) {
      return h("p", {}, [h("b", { text: r[0] + ". " }), r[1]]);
    }));
    var options = h("ol", { class: "option-list" }, objects(frame.options).map(function (o, i) {
      return h("li", { style: "--i:" + i }, [
        verdictPill(o.verdict),
        h("div", {}, [
          h("b", { text: (o.name || "") + ". " + (o.summary || "") }),
          h("span", { text: [sentence(o.why), o.upside ? "Upside: " + sentence(o.upside) : "", o.downside ? "Downside: " + sentence(o.downside) : ""].filter(Boolean).join(" ") })
        ])
      ]);
    }));
    var drivers = h("ul", { class: "risk-list" }, objects(frame.value_drivers).map(function (v) {
      return h("li", {}, [h("b", { text: v.driver || "" }), h("span", { text: (v.mechanism || "") + (v.how_to_size ? " How to size it: " + v.how_to_size : "") })]);
    }));
    var must = texts(frame.assumptions).map(function (a) { return h("li", {}, [h("b", { text: "Must be true. " }), a]); });
    var open = objects(frame.open_questions).map(function (q) { return h("li", {}, [h("b", { text: "Open. " }), (q.question || "") + (q.how_to_answer ? " " + q.how_to_answer : "")]); });
    return cardShell("crosshair", "The question and the options", objects(frame.options).length + " options", [
      scq,
      h("h4", { text: "Options considered" }), options,
      h("h4", { text: "Value at stake" }), drivers,
      h("p", { class: "sub", text: "Figures not in the cited sources are assumptions for your finance team to size." }),
      must.length || open.length ? h("details", { class: "more" }, [h("summary", {}, ["Assumptions and open questions", ico("chevron-down")]), h("ul", { class: "risk-list" }, must.concat(open))]) : null
    ]);
  }

  function planCard() {
    var plan = (state && state.plan) || {};
    var decisions = h("ol", { class: "decision-list" }, objects(plan.decisions).map(function (d) {
      return h("li", {}, [h("b", { text: sentence(d.decision) }), h("span", { text: [d.owner ? "Owner: " + sentence(d.owner) : "", d.by_when ? "By " + sentence(d.by_when) : ""].filter(Boolean).join(" ") })]);
    }));
    var risks = h("ul", { class: "risk-list" }, objects(plan.risks).map(function (r) {
      return h("li", {}, [
        h("b", { text: r.risk || "" }),
        h("div", { class: "levels" }, [level("Likelihood", r.likelihood), level("Impact", r.impact)]),
        h("span", { text: (r.mitigation || "") + (r.owner ? " Owner: " + r.owner + "." : "") })
      ]);
    }));
    var windows = ["Days 1-30", "Days 31-60", "Days 61-90"].map(function (w) {
      var rows = objects(plan.milestones).filter(function (m) { return m.window === w; });
      return h("div", { class: "chart-col" }, [h("h4", { text: w })].concat(rows.length ? [h("ul", { class: "risk-list" }, rows.map(function (m) {
        return h("li", {}, [h("b", { text: m.milestone || "" }), h("span", { text: [m.owner ? "(" + m.owner + ")" : "", m.gate ? "Gate: " + m.gate : ""].filter(Boolean).join(" ") })]);
      }))] : [h("p", { class: "sub", text: "No milestone in this window." })]));
    });
    var kpis = h("ul", { class: "risk-list" }, objects(plan.kpis).map(function (k) {
      return h("li", {}, [h("b", { text: (k.metric || "") + (k.direction ? ", " + k.direction : "") + (k.cadence ? ", " + k.cadence : "") }), h("span", { text: k.why || "" })]);
    }));
    var people = objects(plan.stakeholders).map(function (p) { return h("li", {}, [h("b", { text: (p.who || "") + " " }), h("span", { class: "pill", text: p.role || "" }), " ", p.needs || ""]); });
    return cardShell("milestone", "Decisions, risks, and the first 90 days", objects(plan.milestones).length + " milestones", [
      h("h4", { text: "Decisions required" }), decisions,
      h("h4", { text: "Risk register" }), risks,
      h("h4", { text: "First 90 days" }), h("div", { class: "chart-cols three" }, windows),
      plan.cadence ? h("p", { class: "sub" }, [h("b", { text: "Cadence. " }), plan.cadence]) : null,
      h("h4", { text: "Measures" }), kpis,
      people.length ? h("details", { class: "more" }, [h("summary", {}, ["Who needs to be aligned", ico("chevron-down")]), h("ul", { class: "risk-list people" }, people)]) : null
    ]);
  }

  function steps(rows) {
    return h("ol", { class: "steps-list" }, objects(rows).map(function (s) {
      return h("li", {}, [owner(s.owner), h("b", { text: s.step || "" }), h("span", { class: "task", text: s.task || "" })]);
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
      [list(s.sources).length, "sources"], [list(s.experts).length, "AI experts"], [list(s.debate).length, "debate turns"],
      [list(s.top5).length, "top moves"], [s.maturity ? s.maturity + "/4" : "—", "AI maturity"]
    ].map(function (r) { return h("div", { class: "stat" }, [h("strong", { text: String(r[0]) }), h("span", { text: r[1] })]); });
    doneStatus = h("p", { class: "status-line", role: "status", text: "Building the full report and the deliverables." });
    loadView();
    return h("article", { class: "card gb done-card live" }, [
      h("header", { class: "card-head" }, [h("h3", {}, [ico("package"), " The harness kit is ready"]), h("span", { class: "pill cobalt", text: "done" })]),
      h("div", { class: "stats" }, stats),
      h("div", { class: "downloads" }, [
        h("button", { type: "button", class: "btn primary small", "data-download": "kit" }, [ico("package"), "Harness kit"]),
        h("button", { type: "button", class: "btn small", "data-download": "pptx" }, [ico("presentation"), "Client deck .pptx"]),
        h("button", { type: "button", class: "btn small", "data-download": "skill-pack" }, [ico("puzzle"), "Skill pack"]),
        h("button", { type: "button", class: "btn small ghost", "data-download": "report" }, [ico("file-text"), "Report .md"]),
        h("button", { type: "button", class: "btn small ghost", onclick: saveJson }, [ico("download"), "JSON"])
      ]),
      doneStatus
    ]);
  }

  /* ---------- the full report, rendered by the same code as /demos ---------- */
  function loadView() {
    if (viewing || reportNode || !state || state.phase !== "done") return;
    viewing = true;
    var jump = booted;
    var ticket = { epoch: generation, projectId: book.selected };
    fetch("/api/chat/view", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ state: state }) })
      .then(read).then(function (data) {
        viewing = false;
        if (!H.shouldApply(ticket, { epoch: generation, projectId: book.selected })) return;
        if (!data.ok || !data.report) throw new Error("no report");
        docs = {};
        (data.deliverables || []).concat(data.catalog || []).forEach(function (d) { docs[d.id] = d; });
        reportNode = h("div", { class: "live-report report-body" });
        reportNode.innerHTML = data.report;
        paintLog();
        paintRail();
        if (window.initReport) window.initReport(reportNode, null);
        loadCatalog(reportNode.querySelector("#catalog-picks"), reportNode.querySelector("#artifact-status"));
        if (jump) window.scrollTo({ top: Math.max(reportNode.getBoundingClientRect().top + window.scrollY - 90, 0), behavior: motion() });
      }).catch(function () {
        viewing = false;
        if (doneStatus) doneStatus.textContent = "The full report did not load. Reload the page to try again.";
      });
  }

  function motion() { return window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"; }

  function statusLine() {
    return (reportNode && reportNode.querySelector("#artifact-status")) || doneStatus;
  }

  function showDoc(id) {
    var doc = docs[id];
    if (!doc || !reportNode) return;
    var viewer = reportNode.querySelector("#viewer");
    var save = doc.pptx ? ".pptx" : ".html";
    viewer.hidden = false;
    reportNode.querySelector("#viewer-kicker").textContent = doc.pptx ? "Client deck · the same slides as the .pptx" : id.indexOf("catalog:") === 0 ? "Catalog artifact" : "Deliverable";
    reportNode.querySelector("#viewer-title").textContent = doc.title;
    var actions = reportNode.querySelector("#viewer-actions");
    actions.textContent = "";
    actions.appendChild(h("button", { type: "button", class: "btn small ghost", "data-open": id }, [ico("external-link"), "Open full page"]));
    actions.appendChild(h("button", { type: "button", class: "btn small primary", "data-save": id, "data-kind": save }, [ico("download"), "Download " + save]));
    if (doc.pptx) actions.appendChild(h("button", { type: "button", class: "btn small ghost", "data-save": id, "data-kind": ".html" }, [ico("download"), ".html"]));
    actions.appendChild(h("button", { type: "button", class: "linkish", "data-save": id, "data-kind": ".md" }, [".md"]));
    reportNode.querySelector("#viewer-frame").srcdoc = doc.html;
    reportNode.querySelectorAll("[data-card]").forEach(function (card) { card.classList.toggle("on", card.getAttribute("data-card") === id); });
    viewer.scrollIntoView({ behavior: motion(), block: "start" });
  }

  function openDoc(id) {
    var doc = docs[id];
    if (!doc) return;
    var url = URL.createObjectURL(new Blob([doc.html], { type: "text/html" }));
    window.open(url, "_blank", "noopener");
    setTimeout(function () { URL.revokeObjectURL(url); }, 60000);
  }

  function saveDoc(id, kind) {
    var doc = docs[id];
    if (!doc) return;
    var name = id.replace("catalog:", "");
    if (kind === ".pptx") download(DOWNLOADS.pptx[0], DOWNLOADS.pptx[1], statusLine());
    else if (kind === ".md") blobSave(doc.markdown || "", name + ".md", "text/markdown");
    else blobSave(doc.html, name + ".html", "text/html");
  }

  log.addEventListener("click", function (ev) {
    var el = ev.target.closest("[data-artifact],[data-open],[data-save],[data-download]");
    if (!el || !log.contains(el)) return;
    if (el.hasAttribute("data-artifact")) showDoc(el.getAttribute("data-artifact"));
    else if (el.hasAttribute("data-open")) openDoc(el.getAttribute("data-open"));
    else if (el.hasAttribute("data-save")) saveDoc(el.getAttribute("data-save"), el.getAttribute("data-kind"));
    else if (DOWNLOADS[el.getAttribute("data-download")]) {
      var d = DOWNLOADS[el.getAttribute("data-download")];
      download(d[0], d[1], statusLine());
    }
  });

  function recommend() {
    var text = ((state && state.problem) || "").toLowerCase();
    var ids = ["issue-tree", "board-one-pager", "business-case", "stakeholder-map", "risks", "raci"];
    if (text.indexOf("pric") >= 0) ids.unshift("pricing-analysis");
    if (text.indexOf("cost") >= 0) ids.unshift("cost-reduction");
    return ids.slice(0, 6);
  }

  function loadCatalog(picks, status) {
    if (!picks) return;
    fetch("/api/catalog").then(function (res) { return res.json(); }).then(function (data) {
      var byId = {};
      (data.groups || []).forEach(function (g) { (g.artifacts || []).forEach(function (a) { byId[a.id] = a; }); });
      var ids = Object.keys((state && state.artifacts) || {});
      recommend().forEach(function (id) { if (ids.indexOf(id) < 0) ids.push(id); });
      ids.forEach(function (id) {
        var item = byId[id];
        if (!item) return;
        var made = !!docs["catalog:" + id];
        picks.appendChild(h("button", { type: "button", class: "chip" + (made ? " on" : ""), onclick: function (ev) {
          if (docs["catalog:" + id]) showDoc("catalog:" + id); else generate(item, ev.currentTarget, status);
        } }, [ico(made ? "eye" : "sparkles"), item.title]));
      });
      picks.appendChild(h("a", { class: "chip", href: "/catalog" }, ["All artifacts", ico("arrow-right")]));
    }).catch(function () {});
  }

  function generate(item, button, status) {
    if (button.disabled || running) return;
    button.disabled = true;
    var ticket = { epoch: generation, projectId: book.selected };
    status.textContent = "Writing " + item.title + ". This takes about 20 seconds.";
    fetch("/api/chat/artifact", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state: state || {}, artifact_id: item.id })
    }).then(read).then(function (data) {
      button.disabled = false;
      if (!H.shouldApply(ticket, { epoch: generation, projectId: book.selected })) return;
      if (!data.ok) { status.textContent = (data.error && data.error.message) || "The artifact was not written. Try again."; return; }
      if (data.state) { state = data.state; save(); }
      status.textContent = "";
      docs["catalog:" + item.id] = { id: "catalog:" + item.id, title: item.title, html: data.html || "", markdown: data.markdown || "" };
      button.classList.add("on");
      button.replaceChild(ico("eye"), button.firstChild);
      showDoc("catalog:" + item.id);
    }).catch(function () { button.disabled = false; status.textContent = "The request failed. Try again."; });
  }

  function renderCard(card) {
    if (!card || !card.kind) return null;
    if (card.kind === "research") return researchCard(card);
    if (card.kind === "brief") return briefCard();
    if (card.kind === "experts") return expertsCard(card);
    if (card.kind === "debate") return debateCard(card);
    if (card.kind === "top5") return top5Card(card);
    if (card.kind === "frame") return frameCard();
    if (card.kind === "red_team") return redTeamCard();
    if (card.kind === "plan") return planCard();
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
    try {
      return renderKnownItem(item, index);
    } catch (e) {
      return h("li", { class: "msg" }, [avatarImg(), h("div", { class: "bubble", text: "This saved card could not be shown." })]);
    }
  }

  function renderKnownItem(item, index) {
    if (!item || typeof item !== "object") return null;
    if (item.role === "user") return h("li", { class: "msg me" }, [h("div", { class: "bubble", text: typeof item.text === "string" ? item.text : "" })]);
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
    return h("li", { class: "msg" }, [avatarImg(), h("div", {}, [h("div", { class: "bubble", text: typeof item.text === "string" ? item.text : "" }), extra])]);
  }

  function errorCard(item, index) {
    var last = index === items.length - 1;
    var canRetry = last && item.retry;
    return h("div", { class: "error-card" }, [
      h("p", {}, [ico("triangle-alert"), " ", typeof item.text === "string" ? item.text : ""]),
      canRetry || (last && item.fresh) ? h("div", { class: "downloads" }, [
        canRetry ? h("button", { type: "button", class: "btn small primary", onclick: retry }, [ico("refresh-cw"), item.resume ? "Continue" : "Retry"]) : null,
        last && item.fresh ? h("button", { type: "button", class: "btn small ghost", onclick: fresh }, [ico("rotate-ccw"), "New engagement"]) : null
      ]) : null
    ]);
  }

  function paintLog() {
    log.textContent = "";
    var showReport = reportNode && state && state.phase === "done";
    var runlog = null;
    var seen = {};
    items.forEach(function (item, i) {
      if (!readableItem(item)) {
        log.appendChild(h("li", { class: "msg" }, [avatarImg(), h("div", { class: "bubble", text: "One saved entry could not be shown." })]));
        return;
      }
      var kind = item.role === "card" && item.card ? item.card.kind : null;
      if (showReport && kind === "done") {
        log.appendChild(h("li", { class: "msg report-msg", id: "stage-7" }, [reportNode]));
        return;
      }
      var node = renderItem(item, i);
      if (!node) return;
      var stage = kind ? STAGE_OF[kind] : item.role === "user" ? 0 : null;
      if (stage != null && !seen[stage]) { node.id = "stage-" + stage; seen[stage] = true; }
      if (showReport && kind) {
        if (!runlog) {
          runlog = h("ol");
          log.appendChild(h("li", { class: "msg runlog-msg" }, [h("details", { class: "runlog" }, [
            h("summary", {}, [ico("chevron-down"), "Live run log: every card from research to the judge, as it happened"]), runlog
          ])]));
        }
        runlog.appendChild(node);
        return;
      }
      log.appendChild(node);
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
    if (typeof phase !== "string" || !phase || phase.indexOf("ask_") === 0 && phase !== "ask_size") return 0;
    if (phase === "research" || phase === "synthesize") return 1;
    if (phase === "panel") return 2;
    if (phase === "debate") return 3;
    if (phase === "judge") return 4;
    if (phase === "frame" || phase === "red_team" || phase === "plan") return 5;
    if (phase === "blueprint") return 6;
    if (phase === "ask_size" || phase === "skills") return 7;
    if (phase === "done") return 9;
    return 0;
  }

  function paintRail() {
    var s = state || {};
    var current = stageIndex(s.phase);
    var nav = !!(reportNode && s.phase === "done");
    stagesEl.textContent = "";
    stagesEl.classList.toggle("nav", nav);
    document.body.classList.toggle("reporting", nav);
    stagesEl.parentElement.setAttribute("aria-label", nav ? "Report sections" : "Progress");
    if (nav) {
      NAV.forEach(function (row) {
        if (row[3] && !row[3](s)) return;
        stagesEl.appendChild(h("li", { class: "done" }, [h("a", { href: "#" + row[0] }, [
          h("span", { class: "n" }, [ico("check")]), h("span", { class: "lbl", text: row[1] }), h("span", { class: "count", text: row[2](s) })
        ])]));
      });
      if (window.reportSpy) window.reportSpy(stagesEl, reportNode);
    }
    if (!nav) STAGES.forEach(function (stage, i) {
      var done = i < current;
      var active = i === current;
      var kids = [
        h("span", { class: "n" }, [done ? ico("check") : String(i + 1)]),
        h("span", { class: "lbl", text: stage.label }),
        h("span", { class: "count", text: stage.count(s) })
      ];
      stagesEl.appendChild(h("li", { class: done ? "done" : active ? "active" : "", "aria-current": active ? "step" : null },
        done || active ? [h("a", { href: "#stage-" + Math.min(i, 7) }, kids)] : kids));
    });
    var pct = Math.min(100, Math.round(current / STAGES.length * 100));
    if (s.phase === "panel" || s.phase === "debate") {
      var part = s.phase === "panel" ? (s.experts || []).length / 20 : (s.debate || []).length / 40;
      pct = Math.round((current + part) / STAGES.length * 100);
    }
    meter.style.setProperty("--v", pct + "%");
    var problemText = typeof s.problem === "string" ? s.problem : "";
    railTitle.textContent = problemText ? (problemText.length > 110 ? problemText.slice(0, 107) + "…" : problemText) : "New engagement";
  }

  function readableItem(item) {
    return !!(item && typeof item === "object" && typeof item.role === "string");
  }

  function paint() {
    var broken = items.filter(function (item) { return !readableItem(item); }).length;
    if (broken && !historyNote) {
      historyNote = broken + (broken === 1 ? " saved entry could not be shown. " : " saved entries could not be shown. ") + "The stored copy was not changed.";
    }
    paintProjects();
    paintArtifacts();
    var started = items.some(function (i) { return readableItem(i) && i.role === "user"; });
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

  function randomHex() {
    var bytes = new Uint8Array(16);
    if (window.crypto && window.crypto.getRandomValues) window.crypto.getRandomValues(bytes);
    else for (var i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256);
    var out = "";
    for (var i = 0; i < bytes.length; i++) out += (bytes[i] + 256).toString(16).slice(1);
    return out;
  }

  function visitorId() {
    var existing = "";
    try { existing = localStorage.getItem(VISITOR_KEY) || ""; } catch (e) { existing = ""; }
    if (existing) return existing;
    var id = (window.crypto && typeof window.crypto.randomUUID === "function") ? window.crypto.randomUUID() : randomHex();
    try { localStorage.setItem(VISITOR_KEY, id); } catch (e2) { /* private mode: still send it this turn */ }
    return id;
  }

  function hasHistory() {
    try { return localStorage.getItem(HISTORY_KEY) === "1"; } catch (e) { return false; }
  }

  function markHistory() {
    try { localStorage.setItem(HISTORY_KEY, "1"); } catch (e) { /* ignore */ }
  }

  function wroteMemory(s) {
    if (!s) return false;
    if (s.phase === "done" || s.chart || s.pack) return true;
    return Array.isArray(s.top5) && s.top5.length > 0;
  }

  function post(message, ticket) {
    return fetch(ENDPOINT, {
      method: "POST", signal: ticket.signal, headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: message,
        state: state || {},
        uploads: message ? takeUploads() : [],
        visitor_id: visitorId(),
        has_history: hasHistory()
      })
    }).then(read).then(function (data) {
      if (!H.shouldApply(ticket, { epoch: generation, projectId: book.selected })) return { ignored: true };
      return data;
    });
  }

  function handle(data) {
    if (!data || data.ignored) return null;
    if (data.state) state = data.state;
    if (wroteMemory(state)) markHistory();
    var err = data.error;
    if (!data.ok || err) {
      var code = err && err.code;
      var text = (err && err.message) || "The request failed. Your earlier answers are still here.";
      append({ role: "error", text: text, retry: ["budget", "tamper", "daily_limit", "not_configured"].indexOf(code) < 0, fresh: code === "budget" || code === "tamper" || code === "spend_limit" });
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
    if (controller) controller.abort();
    generation += 1;
    var ticket = { epoch: generation, projectId: book.selected, signal: (controller = new AbortController()).signal };
    lastMessage = message;
    setBusy(true, message ? null : state && state.phase);
    var guard = 0;
    function step(msg) {
      return post(msg, ticket).then(function (data) {
        if (!H.shouldApply(ticket, { epoch: generation, projectId: book.selected })) return;
        var next = handle(data);
        if (next && guard < 20) {
          guard += 1;
          lastMessage = "";
          typingText.textContent = STATUS[next] || "Working";
          return step("");
        }
      });
    }
    return step(message).catch(function (err) {
      if (err && err.name === "AbortError") return;
      if (!H.shouldApply(ticket, { epoch: generation, projectId: book.selected })) return;
      append({ role: "error", text: "The connection dropped. Your earlier answers are still here.", retry: true });
    }).then(function () {
      if (!H.shouldApply(ticket, { epoch: generation, projectId: book.selected })) return;
      setBusy(false);
      paint();
      if (window.matchMedia("(pointer: fine)").matches) box.focus();
    });
  }

  function retry() {
    if (running) return;
    var phase = state && state.phase;
    items = items.filter(function (i, idx) { return !(readableItem(i) && i.role === "error" && idx === items.length - 1); });
    paintLog();
    run(AUTO.indexOf(phase) >= 0 ? "" : lastMessage);
  }

  function submit(text) {
    text = String(text || "").trim();
    if (!text || running) return;
    if (!book.selected) book = H.startNew(book, Math.random, Date.now()).book;
    if (state && state.phase === "done" && text.length > 15) {
      var kept = save();
      if (!kept || kept.ok === false) return;
      var started = H.startNew(book, Math.random, Date.now());
      if (!started.ok) { setNote(started.notice); return; }
      book = started.book;
      state = null;
      reportNode = null;
      docs = {};
      viewing = false;
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
    status = status || { textContent: "" };
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
    var keep = { problem: s.problem, team: s.team, tools: s.tools, maturity: s.maturity, brief: s.brief, experts: s.experts, debate: s.debate, top5: s.top5, panel: s.panel, frame: s.frame, attacks: s.attacks, plan: s.plan, chart: s.chart };
    blobSave(JSON.stringify(keep, null, 2), "engagement.json", "application/json");
  }

  /* ---------- persistence ---------- */
  function setNote(text) {
    historyNote = text || "";
    var note = document.getElementById("history-note");
    if (note) note.textContent = historyNote;
  }

  function persist() {
    var result = H.write(localStorage, book, seen);
    if (result.ok) { seen.raw = result.raw; historyNote = ""; }
    if (!result.ok) setNote(result.notice);
    paintProjects();
    return result;
  }

  function save() {
    if (seen.blocked) { setNote(historyNote); paintProjects(); return { ok: false, persisted: false }; }
    if (!book.selected) return { ok: true, persisted: false };
    var touched = H.touch(book, book.selected, state, items, Date.now());
    if (!touched.ok) { setNote(touched.notice); paintProjects(); return touched; }
    var meaningful = touched.book.projects.some(function (project) {
      return (project.items || []).some(function (item) { return readableItem(item) && item.role === "user"; }) || (project.state && project.state.problem);
    });
    if (!meaningful) return { ok: true, persisted: false };
    book = touched.book;
    return persist();
  }

  function welcome() { return document.getElementById("welcome").textContent; }

  function blankView() {
    state = null;
    reportNode = null;
    docs = {};
    viewing = false;
    items = [{ role: "assistant", text: welcome() }];
    uploads = [];
    paintFiles();
  }

  function showProject(project) {
    reportNode = null;
    docs = {};
    viewing = false;
    state = project && project.state ? JSON.parse(JSON.stringify(project.state)) : null;
    items = project && project.items && project.items.length ? JSON.parse(JSON.stringify(project.items)) : [];
    if (!items.length) items = [{ role: "assistant", text: welcome() }];
    var last = items[items.length - 1];
    if (H.bootAction(state) === "pause" && !(last && last.resume)) {
      items.push({ role: "error", text: "The engagement paused while the agents were working. Continue from where it stopped.", retry: true, resume: true });
    }
    uploads = [];
    paintFiles();
    paint();
  }

  function stopFlight() {
    generation += 1;
    if (controller) controller.abort();
    if (running) setBusy(false);
  }

  function fresh() {
    if (seen.blocked) { setNote(historyNote); paintProjects(); return; }
    var saved = save();
    if (!saved || saved.ok === false) { paint(); return; }
    var started = H.startNew(book, Math.random, Date.now());
    if (!started.ok) { setNote(started.notice); paintProjects(); return; }
    stopFlight();
    book = started.book;
    blankView();
    paint();
    save();
    window.scrollTo(0, 0);
    box.focus();
  }

  function paintProjects() {
    var bar = document.getElementById("project-bar");
    var select = document.getElementById("projects");
    if (!bar || !select) return;
    var keep = book.projects.some(function (project) {
      return (project.items || []).some(function (item) { return item && item.role === "user"; }) || (project.state && project.state.problem);
    });
    bar.hidden = !keep && !historyNote;
    var recover = document.getElementById("recover-storage");
    if (recover) recover.hidden = !seen.blocked;
    select.textContent = "";
    book.projects.forEach(function (project) {
      var option = document.createElement("option");
      option.value = project.id;
      option.textContent = project.title || "New engagement";
      if (project.id === book.selected) option.selected = true;
      select.appendChild(option);
    });
    setNote(historyNote);
  }

  function paintArtifacts() {
    var box = document.getElementById("project-files");
    if (!box) return;
    var started = items.some(function (item) { return readableItem(item) && item.role === "user"; });
    var index = H.artifactIndex(state);
    var any = started && (index.saved.length || index.regenerable.length);
    box.hidden = !any;
    box.textContent = "";
    if (!any) return;
    box.appendChild(h("p", { class: "saved-note", text: index.note }));
    index.regenerable.forEach(function (row) {
      var button = h("button", { type: "button", class: "btn small" + (row.ready ? "" : " ghost") }, [row.label]);
      if (!row.ready) {
        button.disabled = false;
        button.addEventListener("click", function () {
          setNote(row.label + " is rebuilt from this project's saved answers. This project is not ready for that file yet.");
        });
      } else {
        button.addEventListener("click", function () {
          var spec = DOWNLOADS[row.id];
          download(spec[0], spec[1], { set textContent(value) { if (value) setNote(value); } });
        });
      }
      box.appendChild(button);
    });
    index.saved.forEach(function (row) {
      box.appendChild(h("button", { type: "button", class: "btn small ghost", onclick: function () { showSaved(row.id); } }, ["Saved text: " + row.label]));
    });
  }

  function showSaved(id) {
    var text = state && state.artifacts && state.artifacts[id];
    var box = document.getElementById("project-files");
    if (!box) return;
    var existing = document.getElementById("saved-text");
    if (existing) existing.remove();
    if (typeof text !== "string" || !text.trim()) {
      setNote("That artifact is not saved in this browser yet.");
      return;
    }
    box.appendChild(h("pre", { id: "saved-text", class: "saved-text", text: text }));
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
  document.getElementById("remove-project").addEventListener("click", function () {
    if (seen.blocked) { setNote(historyNote); paintProjects(); return; }
    if (!book.selected) return;
    var next = H.remove(book, book.selected);
    var title = (H.find(book, book.selected) || {}).title || "this project";
    var previous = book;
    book = next;
    var result = persist();
    if (!result.ok) { book = previous; setNote(result.notice); paintProjects(); return; }
    stopFlight();
    setNote("Removed \"" + title + "\" from this browser.");
    var project = H.find(book, book.selected);
    if (project) showProject(project);
    else blankView();
    paint();
  });
  document.getElementById("recover-storage").addEventListener("click", function () {
    var kept = H.holdAside(localStorage, seen);
    if (!kept.ok) { setNote(kept.notice); paintProjects(); return; }
    seen.blocked = false;
    historyNote = kept.notice;
    if (!book.projects.length) {
      var started = H.startNew(book, Math.random, Date.now());
      if (started.ok) book = started.book;
    }
    var written = persist();
    setNote(written.ok ? "A copy of the unreadable data is kept in this browser. This list is the new one." : written.notice);
    var project = H.find(book, book.selected);
    if (project) showProject(project);
    else blankView();
    paint();
  });
  document.getElementById("projects").addEventListener("change", function (ev) {
    var id = ev.target.value;
    if (id === book.selected) return;
    var saved = save();
    if (!saved || saved.ok === false) { paint(); return; }
    stopFlight();
    book = H.select(book, id);
    showProject(H.find(book, book.selected));
    save();
  });

  /* ---------- boot ---------- */
  try {
    seen.raw = localStorage.getItem(STORE);
  } catch (e) {
    seen.raw = null;
    seen.blocked = true;
    historyNote = "Saved projects could not be read. They were not replaced.";
  }
  if (!seen.blocked) {
    try {
      var loaded = H.read(seen.raw, Math.random, Date.now());
      book = loaded.book;
      seen.blocked = !!loaded.blocked;
      historyNote = loaded.notice || "";
      if (loaded.write && !loaded.blocked) {
        var migrated = persist();
        if (!migrated.ok) historyNote = migrated.notice;
      }
    } catch (e) {
      book = H.blank();
      seen.blocked = true;
      historyNote = "Saved projects could not be read. They were not replaced.";
    }
  }
  if (!book.projects.length && !seen.blocked) book = H.startNew(book, Math.random, Date.now()).book;
  showProject(H.find(book, book.selected));
  if (wroteMemory(state)) markHistory();
  visitorId();
  booted = true;
  if (!items.some(function (i) { return readableItem(i) && i.role === "user"; }) && window.matchMedia("(pointer: fine)").matches) box.focus();
  var tick = 0;
  var placeholders = Array.prototype.map.call(document.querySelectorAll("[data-example]"), function (c) { return c.getAttribute("data-example"); });
  setInterval(function () {
    if (document.body.classList.contains("chatting") || document.activeElement === box && box.value) return;
    tick = (tick + 1) % placeholders.length;
    box.placeholder = placeholders[tick];
  }, 4500);
})();
