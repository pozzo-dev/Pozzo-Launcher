require("./_i18n_stub");
"use strict";
// Fix frontend 0.21.0 (W5): activity.js, play.js e controlli statici sugli altri file. STATIC=<dir> per provare altre copie.
const assert = require("assert"), fs = require("fs"), path = require("path"), vm = require("vm");
const STATIC = process.env.STATIC || path.join(__dirname, "..", "pozzo", "app", "static");
const src = (f) => fs.readFileSync(path.join(STATIC, f), "utf8");
const tick = () => new Promise((r) => setImmediate(r));
const res = (ok, body, status = ok ? 200 : 403) => ({ ok, status, json: async () => body });

(async () => {
  // ---- activity.js
  const els = {}, hs = {};
  const el = (id) => (els[id] ||= { textContent: "", innerHTML: "", hidden: false });
  const doc = { body: {}, head: { insertAdjacentHTML() {} }, documentElement: { dataset: {} },
    getElementById: el, querySelector: () => ({}) };
  let reply = res(true, { jobs: [{ id: "a", name: "Scan", status: "running", stoppable: true, progress: 0.5 }], now: 1 });
  const ctx = vm.createContext({ document: doc, self: 1, top: 1, t: (k) => k, Date, Math, String, Array, JSON, Promise,
    setInterval() {}, addEventListener: (ev, fn) => { hs[ev] = fn; }, fetch: async (u) => (u === "/api/extensions" ? res(true, { themes: [] }) : reply) });
  vm.runInContext(src("activity.js"), ctx);
  await tick();
  assert.ok(/class="act running"/.test(el("list").innerHTML), "prima lista disegnata");

  el("list").innerHTML = "X";
  hs.pointerdown();
  vm.runInContext("render()", ctx);
  assert.strictEqual(el("list").innerHTML, "X", "con il puntatore premuto la lista non si ricostruisce");
  hs.pointerup();
  vm.runInContext("render()", ctx);
  assert.ok(el("list").innerHTML.includes("act running"), "rilasciato: si ridisegna");

  reply = res(false, { detail: "boom" });
  const btn = { disabled: false, dataset: { id: "a" }, closest: (s) => (s === ".stop" ? btn : null) };
  await doc.body.onclick({ target: { closest: (s) => (s === ".stop" ? btn : null) } });
  assert.ok(el("list").innerHTML.includes("act running"), "errore: i job restano, niente crash su data.jobs");
  assert.strictEqual(el("sum").textContent, "boom", "il motivo dell'errore si vede");
  assert.ok(src("activity.js").includes("&#39;"), "esc come core.js");

  // ---- play.js: 403 {detail} non deve girare in eterno
  const msg = { textContent: "" };
  const P = { gid: 1, name: "x", t: { error: "E {msg}", preparing: "p", downloading: "d {pct}" } };
  const pctx = vm.createContext({ document: { getElementById: (id) => (id === "play-data" ? { textContent: JSON.stringify(P) } : id === "msg" ? msg : {}) },
    window: {}, history: { length: 0 }, setTimeout, Math, JSON, Promise, String, Error, console,
    fetch: async () => res(false, { detail: "negato" }) });
  vm.runInContext(src("play.js"), pctx);
  await tick(); await tick();
  assert.strictEqual(msg.textContent, "E negato", "play: errore mostrato");

  // ---- controlli statici
  assert.ok(!/wishlist_news/.test(src("js/events.js")), "listener wishlist_news rimossi");
  for (const f of ["js/pages.js", "js/detail-mods.js"]) assert.ok(/if \(my !== seq\)|my === seq/.test(src(f)), f + ": controllo di sequenza");
  assert.ok(/my === gameSeq \? toast/.test(src("m/m.js")), "m.js: toast d'errore protetto");
  assert.ok(!/seed_ratio|seed_minutes|seed_action|dls-ratio|dls-seed/.test(src("js/downloads.js") + src("settings/download.html")), "niente controlli di seeding");
  assert.ok(!/>Annulla</.test(src("js/actions.js")) && !/Gioco non trovato/.test(src("js/detail.js")) && !/senza dimensione<\/span>/.test(src("js/downloads.js")), "stringhe in t()");
  console.log("ok test_frontend_021b");
})().catch((e) => { console.error(e); process.exit(1); });
