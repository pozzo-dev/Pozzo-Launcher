"use strict";
const { inject } = require("./_i18n_stub");
// Regressioni Big Picture 0.21.0 (W2): Installa per i giochi store non installati, pad.js, pausa col gioco in primo piano.
const fs = require("fs"), path = require("path"), vm = require("vm"), assert = require("assert");
const read = (rel) => fs.readFileSync(path.join(__dirname, "..", rel), "utf8");

(async () => {
  // 1. gioco PC di uno store non installato: Installa, non Gioca; la card e' .notinst
  const ctx = {
    BPLayouts: {}, hueOf: () => 10, esc: String, STORE_SHORT: {}, SHORT: {}, platName: String, STATUS: {},
    $: () => ({ style: {} }), document: { querySelectorAll: () => [] }, main: {},
    window: {}, renderNav() {}, setBackground() {}, beep() {}, toast() {}, TABS: [], console, GSI18n: { lang: "it" },
    fmtTime: String, fmtSize: String, fmtHours: String, BP: { lib: { byId: new Map() }, details: new Map() },
    installGame() {}, playGame() {}, push() {}, pop() {},
  };
  ctx.detail = async () => ({ id: "s1", title: "G", store: "steam", store_name: "Steam", installed: false, emulator: "", media: {}, user: {}, versions: [], genres: [] });
  inject(ctx); vm.createContext(ctx);
  vm.runInContext(read("pozzo/app/static/bigpicture/layouts/classic/layout.js"), ctx);
  const html = ctx.BPLayouts.classic.card({ id: "s1", title: "G", store: "steam", installed: false, platform: "windows" }, 0);
  assert.ok(html.includes("notinst"), "card store non installato ha .notinst");
  const scr = ctx.BPLayouts.classic.game("s1");
  await scr.render({ innerHTML: "" });
  const labels = scr.buttons.map((b) => b.label);
  assert.ok(labels.some((l) => l.includes("Installa")), "Installa presente: " + labels);
  assert.ok(!labels.some((l) => l.includes("Gioca")), "Gioca assente");

  // 2. bigpicture.js: installGame chiama l'API; A in-game solo se la finestra ha il focus
  const bp = read("pozzo/app/static/bigpicture.js");
  assert.match(bp, /async function installGame[\s\S]{0,200}\/install/, "installGame presente");
  assert.match(bp, /action === "a" && BP\.canPause && document\.hasFocus\(\)/, "pausa solo con il focus");

  console.log("test_bp_021b: ok");
})().catch((e) => { console.error(e); process.exit(1); });
