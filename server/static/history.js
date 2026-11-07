/* Same-browser project book. No network. Loaded before chat.js and by node tests. */
(function (root) {
  "use strict";
  var SCHEMA = 3;
  var KEY = "ai-partner-chat-v2";
  var MAX_PROJECTS = 12;
  var MAX_ITEMS = 200;
  var MAX_TEXT = 8000;
  var ID_RE = /^[A-Za-z0-9_-]{8,40}$/;
  var ROLES = { user: 1, assistant: 1, error: 1, card: 1 };
  var ASKS = { maturity: 1, size: 1 };
  var AUTO = { research: 1, synthesize: 1, panel: 1, debate: 1, judge: 1, red_team: 1, blueprint: 1, skills: 1 };

  function newId(rng) {
    var roll = rng || Math.random;
    var hex = "";
    for (var i = 0; i < 16; i++) hex += "0123456789abcdef".charAt(Math.floor(roll() * 16));
    return hex;
  }

  function blank() {
    return { schema: SCHEMA, selected: null, projects: [] };
  }

  function titleOf(state, items) {
    var problem = state && typeof state.problem === "string" ? state.problem : "";
    if (!problem && items) {
      for (var i = 0; i < items.length; i++) {
        if (items[i] && items[i].role === "user" && items[i].text) {
          problem = items[i].text;
          break;
        }
      }
    }
    problem = String(problem || "").replace(/\s+/g, " ").trim();
    if (!problem) return "New engagement";
    return problem.length > 80 ? problem.slice(0, 77) + "..." : problem;
  }

  function plain(value, depth) {
    if (depth > 5) return null;
    if (value == null || typeof value === "boolean") return value;
    if (typeof value === "number") return isFinite(value) ? value : null;
    if (typeof value === "string") return value.slice(0, 4000);
    if (Array.isArray(value)) {
      var list = [];
      for (var i = 0; i < value.length && list.length < 40; i++) list.push(plain(value[i], depth + 1));
      return list;
    }
    if (typeof value === "object") {
      var out = {};
      var keys = Object.keys(value);
      for (var k = 0; k < keys.length && k < 40; k++) {
        if (keys[k] === "html" || keys[k] === "srcdoc") continue;
        out[keys[k]] = plain(value[keys[k]], depth + 1);
      }
      return out;
    }
    return null;
  }

  function sanitizeItem(item) {
    if (!item || typeof item !== "object" || !ROLES[item.role]) return null;
    var out = { role: item.role };
    if (typeof item.text === "string" && item.text) out.text = item.text.slice(0, MAX_TEXT);
    if (ASKS[item.ask]) out.ask = item.ask;
    if (item.role === "error") {
      if (item.retry) out.retry = true;
      if (item.resume) out.resume = true;
      if (item.fresh) out.fresh = true;
    }
    if (item.role === "card") {
      var card = plain(item.card, 0);
      if (!card || typeof card.kind !== "string" || !card.kind) return null;
      out.card = card;
    }
    if (item.role !== "card" && !out.text) return null;
    return out;
  }

  function sanitizeItems(items) {
    if (!Array.isArray(items)) return [];
    var out = [];
    for (var i = 0; i < items.length && out.length < MAX_ITEMS; i++) {
      var clean = sanitizeItem(items[i]);
      if (clean) out.push(clean);
    }
    return out;
  }

  function sanitizeState(state) {
    if (!state || typeof state !== "object" || Array.isArray(state)) return null;
    var copy = plain(state, 0);
    if (!copy) return null;
    try {
      if (JSON.stringify(copy).length > 400000) return null;
    } catch (e) {
      return null;
    }
    return copy;
  }

  function oneProject(raw, rng, stamp) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
    var items = sanitizeItems(raw.items);
    var state = sanitizeState(raw.state);
    if (!state && !items.length) return null;
    var id = typeof raw.id === "string" && ID_RE.test(raw.id) ? raw.id : newId(rng);
    var updated = typeof raw.updated === "number" && isFinite(raw.updated) ? raw.updated : stamp || 0;
    return { id: id, title: titleOf(state, items), updated: updated, state: state, items: items };
  }

  function unread(notice) {
    return { book: blank(), notice: notice, write: false };
  }

  function read(raw, rng, stamp) {
    if (raw == null || raw === "") return { book: blank(), notice: "", write: false };
    var parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (e) {
      return unread("Saved projects could not be read. They were left in place.");
    }
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return unread("Saved projects could not be read. They were left in place.");
    if (parsed.schema == null && Array.isArray(parsed.items)) {
      var migrated = oneProject({ id: parsed.state && parsed.state.chat_id, state: parsed.state, items: parsed.items, updated: stamp || 0 }, rng, stamp);
      var book = blank();
      if (migrated) {
        book.projects = [migrated];
        book.selected = migrated.id;
      }
      return { book: book, notice: "", write: true };
    }
    if (parsed.schema !== SCHEMA) return unread("Saved projects use a format this page does not open. They were left in place.");
    if (!Array.isArray(parsed.projects)) return unread("Saved projects could not be read. They were left in place.");
    var projects = [];
    var seen = {};
    var skipped = 0;
    for (var i = 0; i < parsed.projects.length; i++) {
      var project = oneProject(parsed.projects[i], rng, stamp);
      if (!project || seen[project.id]) {
        skipped += 1;
        continue;
      }
      seen[project.id] = true;
      projects.push(project);
    }
    projects.sort(function (a, b) { return b.updated - a.updated; });
    var selected = typeof parsed.selected === "string" && seen[parsed.selected] ? parsed.selected : (projects[0] ? projects[0].id : null);
    var notice = skipped ? "Some saved entries were skipped because they had no usable content. The rest were kept." : "";
    return { book: { schema: SCHEMA, selected: selected, projects: projects }, notice: notice, write: false };
  }

  function find(book, id) {
    for (var i = 0; i < book.projects.length; i++) if (book.projects[i].id === id) return book.projects[i];
    return null;
  }

  function hasUser(items) {
    return (items || []).some(function (item) { return item && item.role === "user"; });
  }

  function startNew(book, rng, stamp) {
    var current = find(book, book.selected);
    if (current && !hasUser(current.items) && !(current.state && current.state.problem)) {
      return { ok: true, book: book, notice: "" };
    }
    if (book.projects.length >= MAX_PROJECTS) {
      return { ok: false, book: book, notice: "This browser already has " + MAX_PROJECTS + " saved projects. Remove one before starting another. Nothing was deleted." };
    }
    var created = { id: newId(rng), title: "New engagement", updated: stamp || 0, state: null, items: [] };
    return { ok: true, book: { schema: SCHEMA, selected: created.id, projects: book.projects.concat([created]) }, notice: "" };
  }

  function select(book, id) {
    if (!find(book, id)) return book;
    return { schema: SCHEMA, selected: id, projects: book.projects };
  }

  function remove(book, id) {
    var projects = book.projects.filter(function (project) { return project.id !== id; });
    var selected = book.selected === id ? (projects[0] ? projects[0].id : null) : book.selected;
    return { schema: SCHEMA, selected: selected, projects: projects };
  }

  function touch(book, id, state, items, stamp) {
    var projects = book.projects.map(function (project) {
      if (project.id !== id) return project;
      var nextItems = sanitizeItems(items);
      var nextState = sanitizeState(state);
      return { id: project.id, title: titleOf(nextState, nextItems), updated: stamp || 0, state: nextState, items: nextItems };
    });
    return { schema: SCHEMA, selected: book.selected, projects: projects };
  }

  function write(storage, book) {
    try {
      storage.setItem(KEY, JSON.stringify({ schema: SCHEMA, selected: book.selected, projects: book.projects }));
      return { ok: true, notice: "" };
    } catch (e) {
      return { ok: false, notice: "This browser could not store the project. It is still open in this tab." };
    }
  }

  function shouldApply(request, current) {
    return !!(request && current && request.epoch === current.epoch && request.projectId === current.projectId);
  }

  function bootAction(state) {
    if (state && AUTO[state.phase]) return "pause";
    return "idle";
  }

  function artifactIndex(state) {
    var saved = [];
    var artifacts = state && state.artifacts;
    if (artifacts && typeof artifacts === "object" && !Array.isArray(artifacts)) {
      Object.keys(artifacts).forEach(function (id) {
        if (typeof artifacts[id] === "string" && artifacts[id].trim()) saved.push({ id: id, kind: "browser", label: id });
      });
    }
    return {
      saved: saved,
      regenerable: [
        { id: "kit", kind: "regenerable", label: "Harness kit", ready: !!(state && state.chart) },
        { id: "pptx", kind: "regenerable", label: "Client deck", ready: !!(state && state.phase === "done") },
        { id: "skill-pack", kind: "regenerable", label: "Skill pack", ready: !!(state && state.pack) },
        { id: "report", kind: "regenerable", label: "Report", ready: !!(state && state.phase === "done") }
      ],
      note: "Downloads are rebuilt from this project's saved answers when you click them. This page does not keep a server file. Agent download links that look like /api/downloads expire after 24 hours and are not listed here."
    };
  }

  root.AIPartnerHistory = {
    SCHEMA: SCHEMA,
    KEY: KEY,
    MAX_PROJECTS: MAX_PROJECTS,
    read: read,
    write: write,
    startNew: startNew,
    select: select,
    remove: remove,
    touch: touch,
    titleOf: titleOf,
    artifactIndex: artifactIndex,
    shouldApply: shouldApply,
    bootAction: bootAction,
    newId: newId,
    blank: blank,
    find: find
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
