"use strict";
// Test di regressione per i bug Big Picture, media, pad, temi e FPS monitor: `node tests/test_bp_fixes.js`.
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const assert = require("assert");

const ROOT = path.join(__dirname, "..");
const read = (rel) => fs.readFileSync(path.join(ROOT, rel), "utf8");

// 1. bigpicture.css: palette, rem scaling su html, token tema, safe-area, scroll, shots-bar, blur leggero, niente flicker .mo-in
{
  const css = read("pozzo/app/static/bigpicture.css");
  assert.ok(!/html\[data-palette="[^"]+"\]\s+\.card\.focus\s+\.cv,\s*$/m.test(css), "nessuna virgola sospesa nelle palette");
  assert.match(css, /html\[data-bptext="large"\]\s*\{/, "bptext large su html");
  assert.match(css, /html\[data-bptext="xlarge"\]\s*\{/, "bptext xlarge su html");
  assert.ok(!/html\[data-bptext="(?:large|xlarge)"\]\s+body\s*\{/.test(css), "bptext non deve stare su body");
  assert.match(css, /--bp-safe-x:/, "token --bp-safe-x");
  assert.match(css, /--bp-safe-y:/, "token --bp-safe-y");
  assert.match(css, /\.bp-desc\s*\{[^}]*overflow-y:\s*auto/, ".bp-desc scorrevole");
  assert.match(css, /\.search-res\s*\{[^}]*overflow-y:\s*auto/, ".search-res scorrevole");
  assert.ok(!/\.bp-shots-bar\s*\{[^}]*bottom:\s*-2\.6rem/.test(css), ".bp-shots-bar non deve invadere #bp-hints");
  assert.ok(!/blur\(14px\)/.test(css), "niente blur(14px) pesante su #bp-bg");
  assert.match(css, /html\[data-motion="reduced"\][^}]*#bp-bg\s+\.bg-img/, "sfondo ridotto con data-motion");
  assert.match(css, /#grid-inner\s+\.mo-in\s*\{\s*animation:\s*none/, "niente flicker .mo-in in #grid-inner");
  for (const hex of ["#d5dae6", "#dfe4ee", "#cfd5e2", "#d3d8e3", "#1a1e2c", "#23283a"]) {
    assert.ok(!css.includes(hex), `colore hardcoded scuro/chiaro rimosso: ${hex}`);
  }
}

// 2. retro/theme.css: niente Google Fonts @import, niente html,body{font-size:17px}
{
  const retro = read("pozzo/app/themes/retro/theme.css");
  assert.ok(!/fonts\.googleapis\.com/.test(retro), "niente @import Google Fonts");
  assert.ok(!/html\s*,\s*body\s*\{\s*font-size:\s*17px/.test(retro), "niente font-size:17px globale");
}

// 3. bigpicture.html: rimossi script/css desktop, reco.js?v={{v}}, nessun <img> senza src
{
  const html = read("pozzo/app/static/bigpicture.html");
  for (const f of ["palette.js", "onboarding.js", "hints.js", "skeleton.css"]) {
    assert.ok(!html.includes(f), `rimosso ${f} da bigpicture.html`);
  }
  assert.ok(html.includes('/static/reco.js?v={{v}}'), "reco.js ha ?v={{v}}");
  for (const m of html.matchAll(/<img\b[^>]*>/gi)) {
    assert.ok(/\bsrc\s*=/.test(m[0]), `<img> senza src: ${m[0]}`);
  }
}

// 4. motion.css: aspect-ratio focus ring per .tile-text (16:9) e .resume-card
{
  const motion = read("pozzo/app/static/motion.css");
  assert.match(motion, /\.card\.tile-text\.focus::after\s*\{[^}]*aspect-ratio:\s*16\s*\/\s*9/, "ring 16:9 per tile-text");
  assert.match(motion, /\.card\.resume-card\.focus::after\s*\{[^}]*aspect-ratio:\s*auto/, "ring adattato per resume-card");
}

// 5. pad.js: tasti TV/Tizen
{
  const src = read("pozzo/app/static/pad.js");
  const ctx = {
    store: { get: (_, d) => d },
    window: {},
    document: {},
    $: () => null,
    esc: String,
    console,
  };
  vm.createContext(ctx);
  vm.runInContext(src + "\nthis.Pad = Pad;", ctx);
  assert.strictEqual(ctx.Pad.keyAction({ keyCode: 10009, key: "" }), "b");
  assert.strictEqual(ctx.Pad.keyAction({ key: "XF86Back" }), "b");
  assert.strictEqual(ctx.Pad.keyAction({ key: "GoBack" }), "b");
  assert.strictEqual(ctx.Pad.keyAction({ key: "BrowserBack" }), "b");
  assert.strictEqual(ctx.Pad.keyAction({ key: "MediaStop" }), "", "tasti media: non guidano il pad");
  assert.strictEqual(ctx.Pad.keyAction({ key: "MediaPlayPause" }), "");
}

// 6. media.js & media.css: R3 non rubato da chiuso, volume in controls(), niente mojibake, token CSS
{
  const mcss = read("pozzo/app/static/media.css");
  assert.ok(!mcss.includes("#ff9a9a"), "usa var(--bad) in media.css");
  assert.ok(!mcss.includes("rgba(18,21,30,.97)"), "usa var(--panel) in media.css");

  const mjs = read("pozzo/app/static/media.js");
  assert.ok(!mjs.includes('"?? "') && !mjs.includes('.join(" ? ")') && !mjs.includes('` ? $'), "niente mojibake in media.js");

  let widgetHidden = true;
  const volEl = { id: "bp-media-volume", value: "50", disabled: false, events: [], focus() { doc.activeElement = this; }, dispatchEvent(e) { this.events.push(e.type); }, addEventListener() {} };
  const btnEl = { className: "media-action", disabled: false, focus() { doc.activeElement = this; }, click() {} };
  const widgetEl = { id: "bp-media-widget", get hidden() { return widgetHidden; }, set hidden(v) { widgetHidden = v; }, style: { setProperty() {} }, querySelector: () => btnEl, addEventListener() {} };
  const doc = {
    activeElement: btnEl,
    body: { addEventListener() {} },
    querySelector(s) {
      if (s === "#bp-media-widget") return widgetEl;
      if (s === "#bp-media-volume") return volEl;
      return null;
    },
    querySelectorAll(s) {
      if (s.includes("#bp-media-volume")) return [btnEl, volEl];
      return [btnEl];
    },
    addEventListener() {},
  };
  const ctx = {
    document: doc,
    window: { dispatchEvent() {}, addEventListener() {} },
    CustomEvent: function (n) { this.type = n; },
    Event: function (n) { this.type = n; },
    MutationObserver: function () { return { observe() {} }; },
    t: (k) => k,
    fetch: async () => ({ ok: true, json: async () => ({}) }),
    clearTimeout, setTimeout,
    console,
  };
  ctx.window.document = doc;
  vm.createContext(ctx);
  vm.runInContext(mjs, ctx);

  // R3 quando chiuso NON deve essere catturato da PozzoMedia
  assert.strictEqual(ctx.window.PozzoMedia.handlePad("r3"), false, "R3 non catturato a widget chiuso");
  assert.strictEqual(widgetHidden, true);

  // Aperto: arrow down porta il focus anche su #bp-media-volume; left/right regola il volume
  widgetHidden = false;
  doc.activeElement = btnEl;
  assert.strictEqual(ctx.window.PozzoMedia.handlePad("down"), true);
  assert.strictEqual(doc.activeElement, volEl, "down sposta il focus sul cursore volume");
  assert.strictEqual(ctx.window.PozzoMedia.handlePad("right"), true);
  assert.strictEqual(Number(volEl.value), 55, "right alza volume");
  assert.strictEqual(ctx.window.PozzoMedia.handlePad("left"), true);
  assert.strictEqual(Number(volEl.value), 50, "left abbassa volume");
  // R3 quando aperto lo chiude
  assert.strictEqual(ctx.window.PozzoMedia.handlePad("r3"), true);
  assert.strictEqual(widgetHidden, true);
}

// 7. bigpicture.js: initFpsMonitor su documentElement + pausa su document.hidden,
//    lookScreen sostituisce stack senza duplicare e mantiene indice, race setBackground, clear cache, GSI18n.ready, #bp-running
{
  const bpjs = read("pozzo/app/static/bigpicture.js");
  assert.ok(!bpjs.includes("Per chiudere il gioco: ${t("), "niente prefisso duplicato c.run.hold");
  assert.ok(!/label:\s*"Media"/.test(bpjs), "tab Media usa t(...)");
  assert.match(bpjs, /await\s+(?:window\.)?GSI18n\??\.ready/, "attende GSI18n.ready prima di clock/t");
  assert.match(bpjs, /setBackground[\s\S]{0,600}glowId\s*!==\s*\(?id/, "guardia race setBackground");
  assert.match(bpjs, /reloadLibrary[\s\S]{0,250}accents\.clear\(\)[\s\S]{0,80}shotCache\.clear\(\)/, "reloadLibrary svuota le cache");

  // Test reale di initFpsMonitor in vm: target documentElement e pausa quando document.hidden
  const aStart = bpjs.indexOf("function initFpsMonitor(");
  const aEnd = bpjs.indexOf("BP.initFpsMonitor = initFpsMonitor;", aStart);
  assert.ok(aStart > 0 && aEnd > aStart);
  let rafCb = null, rafCount = 0, cancelled = 0;
  const visListeners = [];
  const docEl = { dataset: {} };
  const doc = {
    hidden: false,
    documentElement: docEl,
    body: { dataset: {} },
    addEventListener(ev, fn) { if (ev === "visibilitychange") visListeners.push(fn); },
    removeEventListener() {},
  };
  const ctx = {
    document: doc,
    store: { get: (_, d) => d },
    requestAnimationFrame: (cb) => { rafCb = cb; return ++rafCount; },
    cancelAnimationFrame: () => { cancelled++; rafCb = null; },
    toast() {},
    t: (k) => k,
    console,
  };
  vm.createContext(ctx);
  vm.runInContext(bpjs.slice(aStart, aEnd) + "\nthis.initFpsMonitor = initFpsMonitor;", ctx);
  const mon = ctx.initFpsMonitor();
  assert.ok(rafCount === 1);
  // Simula FPS bassi (<30fps = 60ms/frame per 2500ms)
  for (let ts = 0; ts <= 2500; ts += 60) {
    if (rafCb) rafCb(ts);
  }
  assert.strictEqual(docEl.dataset.motion, "reduced", "initFpsMonitor imposta documentElement.dataset.motion");
  assert.strictEqual(doc.body.dataset.motion, undefined, "initFpsMonitor non scrive su body.dataset.motion");

  // Pausa quando document.hidden diventa true
  const before = rafCount;
  doc.hidden = true;
  visListeners.forEach((fn) => fn());
  assert.ok(cancelled > 0, "cancelAnimationFrame chiamato quando document.hidden");
  assert.strictEqual(rafCb, null, "nessun rAF pendente mentre nascosto");
  doc.hidden = false;
  visListeners.forEach((fn) => fn());
  assert.ok(rafCount > before, "riprende quando torna visibile");
  mon.stop();

  // Test lookScreen: sostituisce top di BP.stack e mantiene i
  const lStart = bpjs.indexOf("function lookScreen(");
  const lEnd = bpjs.indexOf("/* ---- \"Per te\"", lStart);
  assert.ok(lStart > 0 && lEnd > lStart);
  let shows = 0;
  const lctx = {
    BP: { palette: "default", text: "normal", stack: [{ dummy: 1 }] },
    PALETTES: [{ id: "default", label: "Predefinita" }, { id: "contrast", label: "Contrasto" }],
    TEXTS: [{ id: "normal", label: "Normali" }, { id: "large", label: "Grandi" }],
    Pad: { sound: true, talk: false },
    store: { set() {} },
    applyLook() {}, beep() {}, toast() {}, announce() {},
    t: (k) => k, window: { t: (k) => k },
    gridScreen: (title, items) => ({ title, items, i: 0 }),
    push(s) { lctx.BP.stack.push(s); },
    cur() { return lctx.BP.stack[lctx.BP.stack.length - 1]; },
    show() { shows++; },
    console,
  };
  vm.createContext(lctx);
  vm.runInContext(bpjs.slice(lStart, lEnd) + "\nthis.lookScreen = lookScreen;", lctx);
  const ls = lctx.lookScreen();
  lctx.BP.stack.push(ls);
  ls.i = 2;
  ls.items[2].ok();
  assert.strictEqual(lctx.BP.stack.length, 2, "lookScreen non accumula duplicati sullo stack");
  assert.strictEqual(lctx.cur().i, 2, "lookScreen preserva l'indice focalizzato");
  assert.ok(shows >= 1);

  // Test showRunning + pollRunning: nessuna distruzione di #bp-pause, niente overlap di pollRunning
  const rStart = bpjs.indexOf("function showRunning(");
  const rEnd = bpjs.indexOf("async function reloadLibrary(", rStart);
  assert.ok(rStart > 0 && rEnd > rStart);
  let pauseCreated = 0, apiRunningCalls = 0, timers = [];
  const pauseBtn = { id: "bp-pause", textContent: "", classList: { toggle() {} }, click() {} };
  const msgEl = { textContent: "" };
  const titleEl = { textContent: "" };
  const pauseWrap = { hidden: true };
  const runEl = {
    hidden: true,
    _html: "",
    set innerHTML(v) { this._html = v; if (v.includes("bp-pause")) pauseCreated++; },
    get innerHTML() { return this._html; },
    querySelector(s) {
      if (s === "#bp-pause") return pauseCreated ? pauseBtn : null;
      if (s === "#bp-run-msg") return pauseCreated ? msgEl : null;
      if (s === "#bp-run-title") return pauseCreated ? titleEl : null;
      if (s === "#bp-pause-wrap") return pauseCreated ? pauseWrap : null;
      return null;
    },
  };
  let resolveApi;
  const rctx = {
    BP: { running: { id: "g1", title: "Gioco" }, paused: false, canPause: true },
    idle: { close() {} },
    $: (s) => (s === "#bp-running" ? runEl : runEl.querySelector(s)),
    esc: String,
    t: (k) => k,
    glyph: (k) => k,
    toast() {},
    fmtTime: String,
    cur: () => ({}),
    reloadLibrary: async () => {},
    window: {},
    setTimeout: (fn) => { timers.push(fn); return timers.length; },
    clearTimeout() {},
    api: async (u) => {
      if (u === "/api/running") {
        apiRunningCalls++;
        return new Promise((res) => { resolveApi = res; });
      }
      return {};
    },
    console,
  };
  vm.createContext(rctx);
  vm.runInContext("let pollTimer = 0, pollBusy = false;\n" + bpjs.slice(rStart, rEnd) + "\nthis.showRunning = showRunning; this.pollRunning = pollRunning;", rctx);
  rctx.showRunning("A");
  rctx.showRunning("B");
  assert.strictEqual(pauseCreated, 1, "showRunning aggiorna in-place senza ricreare #bp-pause");
  rctx.pollRunning();
  rctx.pollRunning();
  assert.strictEqual(apiRunningCalls, 1, "pollRunning non fa chiamate sovrapposte");
  resolveApi({ status: "running", emulator: "ra", can_pause: true, paused: false });
}

console.log("test_bp_fixes: ok");
