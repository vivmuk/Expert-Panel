/* Same-browser project book. No network. Loaded before chat.js and by node tests.

A project state and its transcript are stored whole. This file does not shorten
strings, lists, or nested fields. The whole record must fit in MAX_BYTES.
A larger record, a value JSON cannot store, or a dangerous key is refused.
The previous value of KEY stays as it was. Unreadable or newer-schema text
also stays until the user keeps a copy and starts fresh.
*/
(function (root) {
  "use strict";
  var SCHEMA = 3;
  var KEY = "ai-partner-chat-v2";
  var HELD_KEY = "ai-partner-chat-v2-held";
  var MAX_PROJECTS = 12;
  var MAX_BYTES = 2000000;
  var ID_RE = /^[A-Za-z0-9_-]{8,40}$/;
  var AUTO = { research: 1, synthesize: 1, panel: 1, debate: 1, judge: 1, frame: 1, red_team: 1, plan: 1, blueprint: 1, skills: 1 };
  var DANGEROUS = Object.create(null);
  DANGEROUS.__proto__ = 1;
  DANGEROUS.constructor = 1;
  DANGEROUS.prototype = 1;
  var NOT_SAVED = "Not saved. This browser refused the write. The last saved copy was not replaced. This project is still open in this tab.";
  var TOO_BIG = "Not saved. This browser record is over " + MAX_BYTES + " characters. The last saved copy was not replaced. This project is still open in this tab.";
  var UNSAFE = "Not saved. This project has a value this browser cannot store safely. The last saved copy was not replaced. This project is still open in this tab.";
  var CONFLICT = "Another tab saved a newer copy. Reload this tab to see it. This tab did not replace that copy.";
  var HELD = "Saved projects in this browser could not be opened. They were not replaced. Choose Keep a copy and start fresh to store a new list. Until then, what you do in this tab is not written over them.";

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

  function unsupported(value, seen) {
    if (value === null) return false;
    var kind = typeof value;
    if (kind === "string" || kind === "boolean") return false;
    if (kind === "number") return !isFinite(value);
    if (kind !== "object") return true;
    if (seen.indexOf(value) >= 0) return true;
    seen.push(value);
    var names = Object.getOwnPropertyNames(value);
    if (Array.isArray(value)) {
      for (var i = 0; i < value.length; i++) if (unsupported(value[i], seen)) return true;
      return false;
    }
    for (var n = 0; n < names.length; n++) {
      if (DANGEROUS[names[n]]) return true;
      if (unsupported(value[names[n]], seen)) return true;
    }
    return false;
  }

  function cloneJson(value) {
    if (unsupported(value, [])) return null;
    try {
      var text = JSON.stringify(value);
      if (typeof text !== "string") return null;
      return JSON.parse(text);
    } catch (e) {
      return null;
    }
  }

  function projectUsable(raw) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) return false;
    if (typeof raw.id !== "string" || !ID_RE.test(raw.id)) return false;
    if (raw.state != null && (typeof raw.state !== "object" || Array.isArray(raw.state))) return false;
    if (raw.items != null && !Array.isArray(raw.items)) return false;
    return !unsupported(raw, []);
  }

  function blockedResult(raw, notice) {
    return { book: blank(), notice: notice || HELD, write: false, blocked: true, raw: raw };
  }

  function read(raw, rng, stamp) {
    if (raw == null || raw === "") return { book: blank(), notice: "", write: false, blocked: false, raw: raw == null ? null : raw };
    var parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (e) {
      return blockedResult(raw, "Saved projects could not be read. They were not replaced. Choose Keep a copy and start fresh to store a new list.");
    }
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return blockedResult(raw);
    if (parsed.schema == null && Array.isArray(parsed.items)) {
      if (unsupported(parsed, [])) return blockedResult(raw);
      var legacyId = parsed.state && typeof parsed.state.chat_id === "string" && ID_RE.test(parsed.state.chat_id) ? parsed.state.chat_id : newId(rng);
      var legacy = {
        id: legacyId,
        title: titleOf(parsed.state, parsed.items),
        updated: stamp || 0,
        state: parsed.state && typeof parsed.state === "object" && !Array.isArray(parsed.state) ? parsed.state : null,
        items: parsed.items
      };
      return {
        book: { schema: SCHEMA, selected: legacy.id, projects: [legacy] },
        notice: "",
        write: true,
        blocked: false,
        raw: raw
      };
    }
    if (parsed.schema !== SCHEMA || !Array.isArray(parsed.projects)) return blockedResult(raw, "Saved projects use a format this page does not open. They were not replaced. Choose Keep a copy and start fresh to store a new list.");
    var projects = [];
    var seen = {};
    for (var i = 0; i < parsed.projects.length; i++) {
      var project = parsed.projects[i];
      if (!projectUsable(project) || seen[project.id]) return blockedResult(raw);
      seen[project.id] = true;
      project.title = titleOf(project.state, project.items);
      projects.push(project);
    }
    projects.sort(function (a, b) { return (b.updated || 0) - (a.updated || 0); });
    var selected = typeof parsed.selected === "string" && seen[parsed.selected] ? parsed.selected : (projects[0] ? projects[0].id : null);
    return {
      book: { schema: SCHEMA, selected: selected, projects: projects },
      notice: "",
      write: false,
      blocked: false,
      raw: raw
    };
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
    var nextState = state == null ? null : cloneJson(state);
    var nextItems = items == null ? [] : cloneJson(items);
    if (state != null && nextState == null) return { ok: false, book: book, notice: UNSAFE };
    if (items != null && nextItems == null) return { ok: false, book: book, notice: UNSAFE };
    if (nextState && unsupported(nextState, [])) return { ok: false, book: book, notice: UNSAFE };
    if (unsupported(nextItems, [])) return { ok: false, book: book, notice: UNSAFE };
    var projects = book.projects.map(function (project) {
      if (project.id !== id) return project;
      var next = {};
      Object.keys(project).forEach(function (key) { next[key] = project[key]; });
      next.state = nextState;
      next.items = nextItems;
      next.updated = stamp || 0;
      next.title = titleOf(nextState, nextItems);
      return next;
    });
    return { ok: true, book: { schema: SCHEMA, selected: book.selected, projects: projects }, notice: "" };
  }

  function payload(book) {
    return JSON.stringify({ schema: SCHEMA, selected: book.selected, projects: book.projects });
  }

  function readCurrent(storage) {
    try {
      return { ok: true, value: storage.getItem(KEY) };
    } catch (e) {
      return { ok: false };
    }
  }

  function write(storage, book, seen) {
    if (!seen || !Object.prototype.hasOwnProperty.call(seen, "raw")) {
      return { ok: false, persisted: false, notice: "Not saved. This tab has no record of what was stored. Reload. Nothing was replaced." };
    }
    if (seen.blocked) return { ok: false, persisted: false, notice: HELD };
    var current = readCurrent(storage);
    if (!current.ok) return { ok: false, persisted: false, notice: NOT_SAVED };
    if (current.value !== seen.raw) return { ok: false, persisted: false, conflict: true, notice: CONFLICT };
    if (unsupported(book, [])) return { ok: false, persisted: false, notice: UNSAFE };
    var body;
    try {
      body = payload(book);
    } catch (e) {
      return { ok: false, persisted: false, notice: UNSAFE };
    }
    if (body.length > MAX_BYTES) return { ok: false, persisted: false, notice: TOO_BIG };
    try {
      storage.setItem(KEY, body);
    } catch (e) {
      return { ok: false, persisted: false, notice: NOT_SAVED };
    }
    return { ok: true, persisted: true, raw: body, notice: "" };
  }

  function holdAside(storage, seen) {
    if (!seen || !seen.blocked) return { ok: false, persisted: false, notice: "There is no unreadable copy to keep." };
    var current = readCurrent(storage);
    if (!current.ok) return { ok: false, persisted: false, notice: NOT_SAVED };
    if (current.value !== seen.raw) return { ok: false, persisted: false, conflict: true, notice: CONFLICT };
    var held;
    try {
      held = storage.getItem(HELD_KEY);
    } catch (e) {
      return { ok: false, persisted: false, notice: NOT_SAVED };
    }
    if (held && held !== seen.raw) {
      return { ok: false, persisted: false, notice: "An older unreadable copy is already kept. This tab did not replace either copy." };
    }
    try {
      if (seen.raw != null) storage.setItem(HELD_KEY, seen.raw);
    } catch (e) {
      return { ok: false, persisted: false, notice: "Not saved. This browser could not keep a copy of the unreadable data. The original was not replaced." };
    }
    return { ok: true, persisted: false, notice: "A copy of the unreadable data is kept in this browser." };
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
    HELD_KEY: HELD_KEY,
    MAX_PROJECTS: MAX_PROJECTS,
    MAX_BYTES: MAX_BYTES,
    read: read,
    write: write,
    holdAside: holdAside,
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
