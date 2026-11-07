"use strict";
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const source = fs.readFileSync(path.join(__dirname, "..", "server", "static", "history.js"), "utf8");
const context = {};
vm.runInNewContext(source, context);
const H = context.AIPartnerHistory;
function makeRng(seed) {
  let x = seed;
  return function () {
    x = (x * 1664525 + 1013904223) % 4294967296;
    return x / 4294967296;
  };
}
const rng = makeRng(7);

function memory() {
  const map = {};
  return {
    fail: false,
    getItem(key) { return Object.prototype.hasOwnProperty.call(map, key) ? map[key] : null; },
    setItem(key, value) { if (this.fail) throw new Error("quota"); map[key] = String(value); },
    removeItem(key) { delete map[key]; }
  };
}

const legacy = JSON.stringify({
  state: { chat_id: "legacychatid1", problem: "Host a public web agent", phase: "ask_context", team: "4 engineers" },
  items: [{ role: "user", text: "Host a public web agent" }, { role: "assistant", text: "Who is on the team?" }]
});
const first = H.read(legacy, rng, 100);
assert.strictEqual(first.write, true);
assert.strictEqual(first.book.projects.length, 1);
assert.strictEqual(first.book.selected, "legacychatid1");
assert.strictEqual(first.book.projects[0].state.team, "4 engineers");
const again = H.read(JSON.stringify(first.book), rng, 100);
assert.strictEqual(again.write, false);
assert.strictEqual(again.book.projects.length, 1);
assert.strictEqual(again.book.projects[0].state.problem, "Host a public web agent");

const broken = H.read("{", rng, 1);
assert.match(broken.notice, /left in place/);
assert.strictEqual(broken.write, false);
const future = H.read(JSON.stringify({ schema: 99, projects: [{ id: "abcdefgh", items: [{ role: "user", text: "keep" }] }] }), rng, 1);
assert.match(future.notice, /left in place/);
assert.strictEqual(future.write, false);

const started = H.startNew(first.book, rng, 200);
assert.strictEqual(started.ok, true);
assert.notStrictEqual(started.book.selected, first.book.selected);
assert.strictEqual(started.book.projects.length, 2);
const reopened = H.find(started.book, "legacychatid1");
assert.strictEqual(reopened.state.team, "4 engineers");
assert.strictEqual(reopened.items[0].text, "Host a public web agent");

let full = first.book;
for (let i = 0; i < H.MAX_PROJECTS - 1; i++) {
  full = H.startNew(full, rng, 300 + i).book;
  full = H.touch(full, full.selected, { problem: "Problem " + i }, [{ role: "user", text: "Problem " + i }], 300 + i);
}
const refused = H.startNew(full, rng, 999);
assert.strictEqual(refused.ok, false);
assert.match(refused.notice, /Nothing was deleted/);
assert.strictEqual(refused.book.projects.length, H.MAX_PROJECTS);

const a = memory();
const b = memory();
H.write(a, first.book);
assert.strictEqual(b.getItem(H.KEY), null);
assert.strictEqual(H.read(a.getItem(H.KEY), rng, 1).book.projects[0].id, "legacychatid1");
a.fail = true;
const quota = H.write(a, first.book);
assert.strictEqual(quota.ok, false);
assert.match(quota.notice, /still open in this tab/);
assert.strictEqual(H.read(a.getItem(H.KEY), rng, 1).book.projects.length, 1);

const paused = H.bootAction({ phase: "research" });
assert.strictEqual(paused, "pause");
assert.strictEqual(H.bootAction({ phase: "ask_context" }), "idle");
assert.strictEqual(H.shouldApply({ epoch: 1, projectId: "a" }, { epoch: 1, projectId: "a" }), true);
assert.strictEqual(H.shouldApply({ epoch: 1, projectId: "a" }, { epoch: 2, projectId: "b" }), false);

const dirty = H.read(JSON.stringify({
  schema: 3,
  selected: "okproject1",
  projects: [{
    id: "okproject1",
    updated: 5,
    state: { problem: "Keep", artifacts: { "issue-tree": "<script>alert(1)</script> text" } },
    items: [{ role: "card", card: { kind: "research", html: "<img onerror=alert(1)>", queries: ["q"] } }, { role: "nope", text: "x" }]
  }]
}), rng, 1);
assert.strictEqual(dirty.book.projects[0].items[0].card.html, undefined);
assert.strictEqual(dirty.book.projects[0].items[0].card.queries[0], "q");
const index = H.artifactIndex(dirty.book.projects[0].state);
assert.strictEqual(index.saved[0].id, "issue-tree");
assert.strictEqual(index.saved[0].kind, "browser");
assert.ok(index.regenerable.every((row) => row.kind === "regenerable"));
assert.match(index.note, /24 hours/);
assert.strictEqual(index.regenerable.find((row) => row.id === "kit").ready, false);

console.log("history ok");
