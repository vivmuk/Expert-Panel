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

function seenFrom(storage) {
  return { raw: storage.getItem(H.KEY), blocked: false };
}

function persist(storage, book, seen) {
  const result = H.write(storage, book, seen);
  if (result.ok) seen.raw = result.raw;
  return result;
}

const legacyState = {
  chat_id: "legacychatid1",
  problem: "Host a public web agent",
  phase: "ask_context",
  team: "4 engineers",
  artifacts: { "research-brief": "R".repeat(12000) }
};
const legacy = JSON.stringify({
  state: legacyState,
  items: [{ role: "user", text: "Host a public web agent" }, { role: "assistant", text: "Who is on the team?" }]
});
const first = H.read(legacy, rng, 100);
assert.strictEqual(first.write, true);
assert.strictEqual(first.blocked, false);
assert.strictEqual(first.book.projects.length, 1);
assert.strictEqual(first.book.selected, "legacychatid1");
assert.strictEqual(first.book.projects[0].state.team, "4 engineers");
assert.strictEqual(first.book.projects[0].state.artifacts["research-brief"], legacyState.artifacts["research-brief"]);
const store = memory();
const seen = seenFrom(store);
store.setItem(H.KEY, legacy);
seen.raw = legacy;
const migrated = persist(store, first.book, seen);
assert.strictEqual(migrated.persisted, true);
const again = H.read(store.getItem(H.KEY), rng, 100);
assert.strictEqual(again.write, false);
assert.strictEqual(again.blocked, false);
assert.strictEqual(JSON.stringify(again.book.projects[0].state), JSON.stringify(legacyState));
assert.strictEqual(again.book.projects[0].items[0].text, "Host a public web agent");

const brokenOriginal = "{";
const broken = H.read(brokenOriginal, rng, 1);
assert.match(broken.notice, /not replaced/);
assert.strictEqual(broken.write, false);
assert.strictEqual(broken.blocked, true);
const futureOriginal = JSON.stringify({ schema: 99, projects: [{ id: "abcdefgh", secret: "keep-me" }] });
const future = H.read(futureOriginal, rng, 1);
assert.match(future.notice, /not replaced/);
assert.strictEqual(future.blocked, true);
assert.strictEqual(future.write, false);

const holdStore = memory();
holdStore.setItem(H.KEY, futureOriginal);
const holdSeen = { raw: futureOriginal, blocked: true };
const intruder = H.touch(
  H.startNew(H.blank(), rng, 5).book,
  H.startNew(H.blank(), rng, 5).book.selected,
  { problem: "should not replace" },
  [{ role: "user", text: "should not replace" }],
  5
);
assert.strictEqual(H.write(holdStore, intruder.book, holdSeen).ok, false);
assert.strictEqual(holdStore.getItem(H.KEY), futureOriginal);
const kept = H.holdAside(holdStore, holdSeen);
assert.strictEqual(kept.ok, true);
assert.strictEqual(holdStore.getItem(H.KEY), futureOriginal);
assert.strictEqual(holdStore.getItem(H.HELD_KEY), futureOriginal);
holdSeen.blocked = false;
const replaced = persist(holdStore, intruder.book, holdSeen);
assert.strictEqual(replaced.persisted, true);
assert.strictEqual(holdStore.getItem(H.HELD_KEY), futureOriginal);
assert.notStrictEqual(holdStore.getItem(H.KEY), futureOriginal);

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
  full = H.touch(full, full.selected, { problem: "Problem " + i }, [{ role: "user", text: "Problem " + i }], 300 + i).book;
}
const refused = H.startNew(full, rng, 999);
assert.strictEqual(refused.ok, false);
assert.match(refused.notice, /Nothing was deleted/);
assert.strictEqual(refused.book.projects.length, H.MAX_PROJECTS);

const isolatedA = memory();
const isolatedB = memory();
const seenA = seenFrom(isolatedA);
assert.strictEqual(persist(isolatedA, first.book, seenA).persisted, true);
assert.strictEqual(isolatedB.getItem(H.KEY), null);

isolatedA.fail = true;
const quota = H.write(isolatedA, first.book, seenA);
assert.strictEqual(quota.ok, false);
assert.strictEqual(quota.persisted, false);
assert.match(quota.notice, /Not saved/);
assert.match(quota.notice, /not replaced/);
assert.doesNotMatch(quota.notice, /still saved/);
assert.strictEqual(isolatedA.getItem(H.KEY), seenA.raw);

const tabA = memory();
const cursorA = seenFrom(tabA);
const cursorB = { raw: null, blocked: false };
let bookA = H.startNew(H.blank(), rng, 1).book;
bookA = H.touch(bookA, bookA.selected, { problem: "Tab A problem", phase: "ask_context" }, [{ role: "user", text: "Tab A problem" }], 1).book;
assert.strictEqual(persist(tabA, bookA, cursorA).persisted, true);
cursorB.raw = cursorA.raw;
bookA = H.touch(bookA, bookA.selected, { problem: "Tab A problem", phase: "ask_maturity" }, [{ role: "user", text: "Tab A saved this later" }], 2).book;
assert.strictEqual(persist(tabA, bookA, cursorA).persisted, true);
const stale = H.touch(
  H.read(cursorB.raw, rng, 1).book,
  H.read(cursorB.raw, rng, 1).book.selected,
  { problem: "Tab B overwrite" },
  [{ role: "user", text: "Tab B overwrite" }],
  3
).book;
const conflict = H.write(tabA, stale, cursorB);
assert.strictEqual(conflict.ok, false);
assert.strictEqual(conflict.persisted, false);
assert.match(conflict.notice, /Another tab/);
assert.strictEqual(tabA.getItem(H.KEY), cursorA.raw);
assert.match(tabA.getItem(H.KEY), /Tab A saved this later/);

const longArtifact = "Paid brief.\n" + "x".repeat(12000);
const deep = { a: { b: { c: { d: { e: { kept: "deep-value" } } } } } };
const experts = Array.from({ length: 20 }, (_, n) => ({
  name: "Expert " + n,
  role: "Lens",
  lens: "L".repeat(160),
  insight: "I".repeat(600),
  recommendation: "R".repeat(400)
}));
const debate = Array.from({ length: 40 }, (_, n) => ({
  name: "Expert " + (n % 20),
  responding_to: "Expert 0",
  round: n < 20 ? 1 : 2,
  stance: "build",
  statement: "S".repeat(500)
}));
const engine = {
  chat_id: "enginechat00001",
  phase: "done",
  problem: "P".repeat(5000),
  team: "4 analysts",
  tools: "Excel",
  maturity: 2,
  calls: 4,
  experts,
  debate,
  top5: [{
    title: "Enter with a partner",
    detail: "D".repeat(3000),
    backers: ["Ada"],
    dissenters: [{ name: "Bao", why: "Wait" }],
    confidence: "high",
    impact: "medium",
    effort: "low",
    citation_url: "https://example.com/source"
  }],
  chart: {
    summary: "Agents draft and a partner decides.",
    current: [{ step: "Desk", task: "Pull sources", owner: "Human" }, { step: "Draft", task: "Write", owner: "Human" }],
    future: [{ step: "Sweep", task: "Pull sources", owner: "AI Agent" }, { step: "Draft", task: "Write", owner: "Hybrid" }]
  },
  pack: { tier: "small" },
  artifacts: { "research-brief": longArtifact },
  sources: Array.from({ length: 24 }, (_, n) => ({ title: "S" + n, url: "https://example.com/" + n, content: "C".repeat(500) }))
};
const longItems = [{ role: "user", text: "U".repeat(9000) }];
for (let i = 0; i < 200; i++) longItems.push({ role: "assistant", text: "line " + i });
longItems.push({
  role: "card",
  card: {
    kind: "research",
    html: "<img onerror=alert(1)>",
    queries: ["German reimbursement"],
    sources: [{ url: "https://example.com/a", title: "A", nested: deep }]
  }
});
let round = H.startNew(H.blank(), rng, 9).book;
const touched = H.touch(round, round.selected, engine, longItems, 9);
assert.strictEqual(touched.ok, true);
assert.strictEqual(touched.book.projects[0].state.artifacts["research-brief"].length, longArtifact.length);
assert.strictEqual(touched.book.projects[0].items[0].text.length, 9000);
assert.strictEqual(touched.book.projects[0].items.length, 202);
assert.strictEqual(touched.book.projects[0].items[201].card.html, "<img onerror=alert(1)>");
assert.strictEqual(touched.book.projects[0].items[201].card.sources[0].nested.a.b.c.d.e.kept, "deep-value");
const roundStore = memory();
const roundSeen = seenFrom(roundStore);
assert.strictEqual(persist(roundStore, touched.book, roundSeen).persisted, true);
const reloaded = H.read(roundStore.getItem(H.KEY), rng, 9);
assert.strictEqual(JSON.stringify(reloaded.book.projects[0].state), JSON.stringify(engine));
assert.strictEqual(JSON.stringify(reloaded.book.projects[0].items), JSON.stringify(longItems));

const tooBig = "z".repeat(H.MAX_BYTES);
const oversized = H.touch(touched.book, touched.book.selected, { problem: "small", artifacts: { "research-brief": tooBig } }, [{ role: "user", text: "small" }], 10);
assert.strictEqual(oversized.ok, true);
const refusedWrite = H.write(roundStore, oversized.book, roundSeen);
assert.strictEqual(refusedWrite.ok, false);
assert.strictEqual(refusedWrite.persisted, false);
assert.match(refusedWrite.notice, /Not saved/);
assert.match(refusedWrite.notice, /not replaced/);
assert.strictEqual(roundStore.getItem(H.KEY), roundSeen.raw);
assert.strictEqual(JSON.stringify(H.read(roundStore.getItem(H.KEY), rng, 9).book.projects[0].state), JSON.stringify(engine));

const unsafeState = JSON.parse('{"problem":"x","__proto__":{"admin":true}}');
const unsafe = H.touch(touched.book, touched.book.selected, unsafeState, [{ role: "user", text: "x" }], 11);
assert.strictEqual(unsafe.ok, false);
assert.match(unsafe.notice, /Not saved/);
assert.strictEqual(roundStore.getItem(H.KEY), roundSeen.raw);

assert.strictEqual(H.bootAction({ phase: "research" }), "pause");
assert.strictEqual(H.bootAction({ phase: "ask_context" }), "idle");
assert.strictEqual(H.shouldApply({ epoch: 1, projectId: "a" }, { epoch: 1, projectId: "a" }), true);
assert.strictEqual(H.shouldApply({ epoch: 1, projectId: "a" }, { epoch: 2, projectId: "b" }), false);

const index = H.artifactIndex(engine);
assert.strictEqual(index.saved[0].id, "research-brief");
assert.strictEqual(index.saved[0].kind, "browser");
assert.strictEqual(index.regenerable.find((row) => row.id === "kit").ready, true);
assert.strictEqual(index.regenerable.find((row) => row.id === "report").ready, true);
assert.match(index.note, /24 hours/);

console.log("history ok");
