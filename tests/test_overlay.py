"""Overlay in gioco: impostazioni, coda degli avvisi, rotte (la finestra nativa non si prova)."""

import types
from pathlib import Path

import pytest

from pozzo import overlay as OV


def test_settings_defaults_and_validation():
    cfg = types.SimpleNamespace(app={})
    cur = OV.settings(cfg)
    assert cur["hotkey"] == "ctrl+shift+o" and cur["achievements"] and cur["sound"] == "soft"
    assert cur["hud"] is False and cur["hud_corner"] == "tl"  # HUD spento di default
    assert OV.clean({"hotkey": " Ctrl+Alt+F9 ", "sound": "none", "achievements": 0}, cur) == {
        "hotkey": "ctrl+alt+f9", "sound": "none", "achievements": False, "hud": False, "hud_corner": "tl"}
    assert OV.clean({"hud": 1, "hud_corner": "br"}, cur)["hud"] is True
    assert OV.clean({"hotkey": ""}, cur)["hotkey"] == ""  # vuota = spenta
    for bad in ({"hotkey": "ctrl+ciao"}, {"hotkey": "foo+o"}, {"sound": "loud"}, {"hud_corner": "centro"}):
        with pytest.raises(ValueError):
            OV.clean(bad, cur)


def test_retroarch_network_commands(tmp_path):
    import socket
    from pozzo.emuadapters import retroarch as RA
    exe = tmp_path / "retroarch.exe"
    cfg = tmp_path / "retroarch.cfg"
    cfg.write_text('network_cmd_enable = "false"\n')
    assert not RA.net_ready(exe) and RA.command(exe, "save") is False  # spento: non si invia nulla
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.bind(("127.0.0.1", 0)); rx.settimeout(2)
    cfg.write_text(f'network_cmd_enable = "true"\nnetwork_cmd_port = "{rx.getsockname()[1]}"\n')
    assert RA.command(exe, "save") and rx.recvfrom(64)[0] == b"SAVE_STATE"
    assert RA.command(exe, "reset") and rx.recvfrom(64)[0] == b"RESET"
    assert RA.command(exe, "format") is False  # comando sconosciuto
    rx.close()


def test_toast_queue_order_dedupe_and_limit():
    q = OV.ToastQueue(limit=3)
    for i in (1, 2, 2, 3, 4, 5):
        q.push({"id": i})
    assert [q.pop()["id"] for _ in range(3)] == [3, 4, 5]  # 2 una volta sola, i piu' vecchi scartati
    assert q.pop() is None


def test_routes(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from pozzo import config as C
    from pozzo.app.routes import overlay as R
    saved = []
    monkeypatch.setattr(C, "save_settings", lambda cfg, **kw: saved.append(kw))
    cfg = types.SimpleNamespace(app={})
    launcher = types.SimpleNamespace(running=lambda: {"status": "running", "key": "k", "title": "T", "started": 5.0})
    ov = OV.Overlay(cfg, launcher)  # senza attach(): niente finestra, toggle risponde False
    ctx = types.SimpleNamespace(cfg=cfg, launcher=launcher, lib=types.SimpleNamespace(by_key={"k": {"id": 7, "title": "Titolo"}}), overlay=ov)
    app = FastAPI()
    app.include_router(R.build_router(ctx))
    c = TestClient(app)
    st = c.get("/api/overlay/state").json()
    assert st["running"] and st["gid"] == 7 and st["title"] == "Titolo" and st["settings"]["hotkey"] == "ctrl+shift+o"
    assert c.post("/api/overlay/toggle").json() == {"ok": False}
    assert c.post("/api/overlay/settings", json={"sound": "classic"}).json()["settings"]["sound"] == "classic"
    assert saved and cfg.app["overlay"]["sound"] == "classic"
    assert c.post("/api/overlay/settings", json={"hotkey": "zz+zz"}).status_code == 400
    # il codice del toast e' in un file a se' (CSP: niente script inline)
    assert '<script src="/static/overlay-toast.js?v=' in c.get("/overlay/toast").text
    assert "window.showToast" in (Path(R.__file__).parents[1] / "static" / "overlay-toast.js").read_text(encoding="utf-8")
    assert "ov-card" in c.get("/overlay").text
    assert "h-time" in c.get("/overlay/hud").text
    assert st["emu"] is None  # nessun emulatore in esecuzione: la scheda non compare
    stats = c.get("/api/overlay/stats").json()
    assert 0 <= stats["cpu"] <= 100 and 0 <= stats["ram"] <= 100 and "battery" in stats
    assert c.post("/api/overlay/emu", json={"action": "save"}).status_code == 409


def test_emu_route_retroarch(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from pozzo.app.routes import overlay as R
    exe = tmp_path / "retroarch.exe"
    (tmp_path / "retroarch.cfg").write_text('network_cmd_enable = "false"\n')
    cfg = types.SimpleNamespace(app={})
    launcher = types.SimpleNamespace(running=lambda: {"status": "running", "key": "k", "emulator_id": "retroarch", "exe": str(exe)})
    ctx = types.SimpleNamespace(cfg=cfg, launcher=launcher, lib=types.SimpleNamespace(by_key={}), overlay=OV.Overlay(cfg, launcher))
    app = FastAPI()
    app.include_router(R.build_router(ctx))
    c = TestClient(app)
    assert c.get("/api/overlay/state").json()["emu"] == {"id": "retroarch", "ready": False}
    assert c.post("/api/overlay/emu", json={"action": "save"}).status_code == 409  # comandi di rete spenti: nessun invio di nascosto


def test_macos_native_window(monkeypatch):
    calls = []

    class NS:  # finta NSWindow: registra i selettori chiamati
        def __getattr__(self, name):
            return lambda *a: calls.append((name, a))

    w = types.SimpleNamespace(native=NS(), show=lambda: calls.append(("show", ())))
    monkeypatch.setattr(OV, "_mac_call", lambda fn: fn())  # niente run loop di Cocoa nel test
    ov = OV.Overlay(types.SimpleNamespace(app={}), None)
    monkeypatch.setattr(OV.sys, "platform", "darwin")
    ov._click_through(w)
    ov._show_passive(w)
    ov._front(w)
    assert calls == [("setLevel_", (25,)), ("setCollectionBehavior_", (273,)), ("setIgnoresMouseEvents_", (True,)),
                     ("orderFrontRegardless", ()), ("orderFrontRegardless", ())]  # HUD mostrato senza w.show(): niente furto di fuoco
    calls.clear()
    monkeypatch.setattr(OV.sys, "platform", "win32")  # ramo Windows: nessun selettore Cocoa, show() normale
    ov._click_through(w)  # (niente _front: su Windows manderebbe un vero Alt via keybd_event)
    ov._show_passive(w)
    assert calls == [("show", ())]


def test_mac_call_never_raises(monkeypatch):
    import sys as _s
    monkeypatch.setitem(_s.modules, "PyObjCTools", None)  # pyobjc assente: esegue subito, l'errore si registra e basta
    OV._mac_call(lambda: 1 / 0)


def test_overlay_screenshot_hides_overlay_first(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from pozzo.app.routes import overlay as R

    calls = []
    cfg = types.SimpleNamespace(app={})
    launcher = types.SimpleNamespace(
        running=lambda: {"status": "running", "key": "k", "started": 10.0},
        screenshot=lambda: calls.append(("shot", ov.visible)) or True,
    )
    ov = OV.Overlay(cfg, launcher)
    ov.visible = True
    monkeypatch.setattr(ov, "hide", lambda refocus=True: calls.append(("hide", refocus)) or setattr(ov, "visible", False) or True)
    monkeypatch.setattr(ov, "show", lambda: calls.append(("show",)) or setattr(ov, "visible", True) or True)
    monkeypatch.setattr(R.time, "sleep", lambda _s: None)
    ctx = types.SimpleNamespace(cfg=cfg, launcher=launcher, lib=types.SimpleNamespace(by_key={}), overlay=ov)
    app = FastAPI()
    app.include_router(R.build_router(ctx))
    c = TestClient(app)

    assert c.post("/api/overlay/screenshot").json() == {"ok": True}
    assert calls == [("hide", True), ("shot", False), ("show",)]


def test_overlay_pause_focus_and_timing(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from pozzo.app.routes import overlay as R

    calls = []
    cfg = types.SimpleNamespace(app={})
    state = {"status": "running", "key": "k", "started": 100.0, "paused": False, "paused_total": 15.0}
    launcher = types.SimpleNamespace(
        running=lambda: dict(state),
        pause=lambda focus_launcher=True: calls.append(("pause", focus_launcher)) or True,
        resume=lambda: calls.append(("resume",)) or True,
    )
    ov = OV.Overlay(cfg, launcher)
    ov.visible = True
    monkeypatch.setattr(ov, "hide", lambda refocus=True: calls.append(("hide", refocus)) or setattr(ov, "visible", False) or True)
    monkeypatch.setattr(R.time, "time", lambda: 165.0)
    ctx = types.SimpleNamespace(cfg=cfg, launcher=launcher, lib=types.SimpleNamespace(by_key={}), overlay=ov)
    app = FastAPI()
    app.include_router(R.build_router(ctx))
    c = TestClient(app)

    assert c.post("/api/overlay/pause").json() == {"ok": True}
    assert calls == [("pause", False)]

    st = c.get("/api/overlay/state").json()
    assert st["paused"] is False and st["paused_total"] == 15.0 and st["elapsed"] == pytest.approx(50.0)
    stats = c.get("/api/overlay/stats").json()
    assert stats["paused"] is False and stats["paused_total"] == 15.0 and stats["elapsed"] == pytest.approx(50.0)

    calls.clear()
    assert c.post("/api/overlay/resume").json() == {"ok": True}
    assert calls == [("resume",), ("hide", True)]


def test_hide_hud_calls_js_and_hud_dimensions():
    assert (OV.HUD_W, OV.HUD_H) == (220, 72)
    calls = []
    w = types.SimpleNamespace(
        evaluate_js=lambda js: calls.append(("js", js)),
        hide=lambda: calls.append(("hide",)),
    )
    ov = OV.Overlay(types.SimpleNamespace(app={}), None)
    ov.wins["hud"] = w
    ov.hud_on = True
    ov.hide_hud()
    assert ov.hud_on is False
    assert ("js", "window.hudHide && hudHide()") in calls
    assert ("hide",) in calls


def test_toast_loop_click_through_and_macos_hide(monkeypatch):
    calls = []

    class NS:
        def __getattr__(self, name):
            return lambda *a: calls.append((name, a))

    w = types.SimpleNamespace(
        events=types.SimpleNamespace(loaded=types.SimpleNamespace(wait=lambda _t=5: True)),
        evaluate_js=lambda js: calls.append(("js", js)),
        hide=lambda: calls.append(("hide",)),
        native=NS(),
    )
    ov = OV.Overlay(types.SimpleNamespace(app={}), None)
    ov.wins["toast"] = w
    monkeypatch.setattr(ov, "_win", lambda which: w)
    monkeypatch.setattr(ov, "_click_through", lambda win: calls.append(("click_through", win is w)))
    monkeypatch.setattr(ov, "_show_passive", lambda win: calls.append(("show_passive", win is w)))
    monkeypatch.setattr(OV.time, "sleep", lambda _s: None)

    def stop_wait():
        raise StopIteration

    # Windows: applica _click_through e chiama w.hide() direttamente
    monkeypatch.setattr(OV.sys, "platform", "win32")
    ov.queue.push({"id": 1, "title": "T"})
    ov._wake.set()
    monkeypatch.setattr(ov._wake, "wait", lambda: stop_wait() if not ov.queue.items else True)
    with pytest.raises(StopIteration):
        ov._toast_loop()
    assert ("click_through", True) in calls
    assert ("hide",) in calls

    # macOS: w.hide passa da _mac_call
    calls.clear()
    mac_fns = []
    monkeypatch.setattr(OV.sys, "platform", "darwin")
    monkeypatch.setattr(OV, "_mac_call", lambda fn: mac_fns.append(fn) or fn())
    ov.queue.push({"id": 2, "title": "M"})
    ov._wake.set()
    with pytest.raises(StopIteration):
        ov._toast_loop()
    assert ("click_through", True) in calls
    assert w.hide in mac_fns and ("hide",) in calls


def test_hotkey_reload_and_watch_pad_decoupled(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from pozzo import config as C
    from pozzo.app.routes import overlay as R
    from pozzo.library import launcher as L, screens

    hk_events = []

    class FakeHotkey:
        def __init__(self, combo, cb):
            self.combo = combo
            hk_events.append(("init", combo))

        def start(self):
            hk_events.append(("start", self.combo))

        def stop(self):
            hk_events.append(("stop", self.combo))

    monkeypatch.setattr(screens, "Hotkey", FakeHotkey)
    monkeypatch.setattr(C, "save_settings", lambda cfg, **kw: None)

    cfg = types.SimpleNamespace(app={"screenshots": {"pad": False}})
    launcher = types.SimpleNamespace(running=lambda: {"status": "running"})
    ov = OV.Overlay(cfg, launcher)

    # game_started ferma eventuale hotkey precedente
    old_hk = FakeHotkey("ctrl+alt+1", ov.toggle)
    ov._hotkey = old_hk
    with monkeypatch.context() as m:
        m.setattr(ov, "_watch_pad", lambda: None)
        m.setattr(ov, "show_hud", lambda: None)
        ov.game_started()
    assert ("stop", "ctrl+alt+1") in hk_events
    assert ("start", "ctrl+shift+o") in hk_events

    # Cambio hotkey in sessione attiva ricarica la scorciatoia
    ctx = types.SimpleNamespace(cfg=cfg, launcher=launcher, lib=types.SimpleNamespace(by_key={}), overlay=ov)
    app = FastAPI()
    app.include_router(R.build_router(ctx))
    c = TestClient(app)
    assert c.post("/api/overlay/settings", json={"hotkey": "ctrl+alt+f8"}).status_code == 200
    assert ("stop", "ctrl+shift+o") in hk_events
    assert ("start", "ctrl+alt+f8") in hk_events

    # _watch_pad funziona anche con screenshots.pad = False
    pad_reads = 0

    def fake_read():
        nonlocal pad_reads
        pad_reads += 1
        ov.active = False
        return 0

    monkeypatch.setattr(L, "_xinput", lambda: fake_read)
    ov.active = True
    ov._watch_pad()
    assert pad_reads == 1


def test_overlay_settings_error_keys():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from pozzo import i18n as I
    from pozzo.app.routes import overlay as R

    cfg = types.SimpleNamespace(app={})
    launcher = types.SimpleNamespace(running=lambda: {"status": "idle"})
    ctx = types.SimpleNamespace(cfg=cfg, launcher=launcher, lib=types.SimpleNamespace(by_key={}), overlay=OV.Overlay(cfg, launcher))
    app = FastAPI()
    app.include_router(R.build_router(ctx))
    c = TestClient(app)

    r_sound = c.post("/api/overlay/settings", json={"sound": "loud"})
    assert r_sound.status_code == 400 and r_sound.json()["detail"] != I.tr("s.shots.hotkeyInvalid")
    r_corner = c.post("/api/overlay/settings", json={"hud_corner": "center"})
    assert r_corner.status_code == 400 and r_corner.json()["detail"] != I.tr("s.shots.hotkeyInvalid")
    r_hk = c.post("/api/overlay/settings", json={"hotkey": "bad+key"})
    assert r_hk.status_code == 400 and r_hk.json()["detail"] == I.tr("s.shots.hotkeyInvalid")


def test_overlay_stats_cpu_cache(monkeypatch):
    import psutil
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from pozzo.app.routes import overlay as R

    samples = []
    monkeypatch.setattr(psutil, "cpu_percent", lambda interval=None: samples.append(interval) or 37.4)
    now = [10.0]
    monkeypatch.setattr(R.time, "monotonic", lambda: now[0])

    cfg = types.SimpleNamespace(app={})
    launcher = types.SimpleNamespace(running=lambda: {"status": "running", "started": 5.0})
    ctx = types.SimpleNamespace(cfg=cfg, launcher=launcher, lib=types.SimpleNamespace(by_key={}), overlay=OV.Overlay(cfg, launcher))
    app = FastAPI()
    app.include_router(R.build_router(ctx))
    c = TestClient(app)

    assert c.get("/api/overlay/stats").json()["cpu"] == 37
    now[0] = 10.4
    assert c.get("/api/overlay/stats").json()["cpu"] == 37
    assert len(samples) == 1
    now[0] = 11.2
    assert c.get("/api/overlay/stats").json()["cpu"] == 37
    assert len(samples) == 2


def test_overlay_static_assets_and_js_behavior():
    import subprocess
    static_dir = Path("pozzo/app/static")
    for name in ("overlay.html", "overlay-hud.html", "overlay-toast.html"):
        html = (static_dir / name).read_text(encoding="utf-8")
        assert "--fg" not in html
        assert "/static/app.css?v={{v}}" in html
        assert "/static/overlay-boot.js?v={{v}}" in html
        assert 'src="/static/i18n.js?v={{v}}"' in html
    assert "--fg" not in (static_dir / "overlay.css").read_text(encoding="utf-8")

    ov_html = (static_dir / "overlay.html").read_text(encoding="utf-8")
    assert 'aria-controls="ov-panel-overview"' in ov_html
    assert 'aria-labelledby="ov-tab-overview"' in ov_html
    assert 'data-media="volume_up"' in ov_html and 'data-media="volume_down"' in ov_html and 'data-media="mute"' in ov_html
    assert "ov-notes-empty" in ov_html and "ov-hints" in ov_html

    script = r"""
const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

function makeStorage(init = {}) {
  const m = new Map(Object.entries(init));
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k) };
}

// 1) overlay-boot.js: data-motion + theme
{
  const head = { children: [], appendChild(el) { this.children.push(el); } };
  const docEl = { dataset: {} };
  const ctx = {
    document: { documentElement: docEl, head, getElementById: () => null, createElement: (tag) => ({ tagName: tag }) },
    localStorage: makeStorage({ "gs.motion": JSON.stringify("reduced") }),
    matchMedia: () => ({ matches: false }),
    fetch: async () => ({ ok: true, json: async () => ({ active_theme: "chiaro", themes: [{ id: "chiaro", desktop: "/themes/chiaro/desktop.css" }] }) }),
  };
  vm.runInNewContext(fs.readFileSync("pozzo/app/static/overlay-boot.js", "utf8"), ctx);
  assert.strictEqual(docEl.dataset.motion, "reduced");
}

// 2) overlay-toast.js: AudioContext riutilizzato, x.icon validato, GSI18n.ready atteso
(async () => {
  let audioCount = 0;
  class FakeAudioContext {
    constructor() { audioCount++; this.currentTime = 0; this.destination = {}; this.state = "running"; }
    createGain() { return { gain: { value: 0 }, connect() {} }; }
    createOscillator() { return { type: "", frequency: { value: 0 }, connect() {}, start() {}, stop() {} }; }
    resume() { return Promise.resolve(); }
  }
  const els = {
    k: { textContent: "" }, n: { textContent: "" }, d: { textContent: "" },
    i: { hidden: true, src: "", removeAttribute(a) { if (a === "src") this.src = ""; } },
    t: { classList: { remove() {}, add() {} }, offsetWidth: 1 },
  };
  let readyDone = false;
  const ctx = {
    URL,
    AudioContext: FakeAudioContext,
    document: { getElementById: (id) => els[id] },
    GSI18n: { ready: new Promise((r) => setTimeout(() => { readyDone = true; r(); }, 10)) },
    t: (k) => (readyDone ? "TRAD:" + k : k),
  };
  ctx.window = ctx;
  vm.runInNewContext(fs.readFileSync("pozzo/app/static/overlay-toast.js", "utf8"), ctx);
  await ctx.window.showToast({ key: "o.test", text: "Ach", icon: "javascript:alert(1)", sound: "soft" });
  assert.strictEqual(els.k.textContent, "TRAD:o.test");
  assert.strictEqual(els.i.hidden, true);
  await ctx.window.showToast({ title: "OK", text: "Ach2", icon: "/img/1/cover", sound: "soft" });
  assert.strictEqual(els.i.hidden, false);
  assert.strictEqual(els.i.src, "/img/1/cover");
  assert.strictEqual(audioCount, 1);

  // 3) overlay-hud.js: hudHide ferma timer e polling, timer si congela in pausa
  const intervals = new Set();
  let nextId = 1;
  const hTime = { textContent: "" }, hSt = { textContent: "" };
  let hudReady = false;
  const hudCtx = {
    document: {
      hidden: false,
      querySelector: (s) => (s === "#h-time" ? hTime : hSt),
      addEventListener() {},
    },
    GSI18n: { ready: new Promise((r) => setTimeout(() => { hudReady = true; r(); }, 5)) },
    t: (k) => (hudReady ? "T:" + k : k),
    setInterval: (_fn, _ms) => { const id = nextId++; intervals.add(id); return id; },
    clearInterval: (id) => intervals.delete(id),
    addEventListener: () => {},
    fetch: async () => ({ ok: true, json: async () => ({ started: 100, paused: true, elapsed: 42, cpu: 15, ram: 40 }) }),
  };
  hudCtx.window = hudCtx;
  vm.runInNewContext(fs.readFileSync("pozzo/app/static/overlay-hud.js", "utf8"), hudCtx);
  hudCtx.window.hudShow();
  await new Promise((r) => setTimeout(r, 20));
  assert.strictEqual(hTime.textContent, "0:42");
  assert.strictEqual(hSt.textContent, "T:o.overlay.cpu 15% · T:o.overlay.ram 40%");
  assert.strictEqual(intervals.size, 2);
  hudCtx.window.hudHide();
  assert.strictEqual(intervals.size, 0);

  // 4) overlay.js: conferma inline su Chiudi gioco, focusFirst con !st.gid, ovHide ferma padTimer, errore rete
  function makeEl(id, extra = {}) {
    const classes = new Set();
    const listeners = {};
    const el = {
      id,
      hidden: false,
      disabled: false,
      textContent: "",
      src: "",
      dataset: {},
      style: {},
      tabIndex: 0,
      children: [],
      focused: false,
      classList: {
        add: (c) => classes.add(c),
        remove: (c) => classes.delete(c),
        contains: (c) => classes.has(c),
      },
      focus() { ovCtx.document.activeElement = this; this.focused = true; },
      click() { if (this.onclick) return this.onclick({ currentTarget: this }); },
      getAttribute(a) { return this.attrs?.[a] ?? null; },
      setAttribute(a, v) { this.attrs = this.attrs || {}; this.attrs[a] = String(v); },
      removeAttribute(a) { if (a === "src") this.src = ""; },
      addEventListener(ev, fn) { (listeners[ev] = listeners[ev] || []).push(fn); },
      dispatch(ev, arg = {}) { (listeners[ev] || []).forEach((fn) => fn(arg)); },
      querySelector(s) { return s === "span" ? (this._span || { textContent: "" }) : null; },
      closest() { return null; },
      replaceChildren(...nodes) { this.children = nodes; },
      ...extra,
    };
    return el;
  }
  const ovIntervals = new Set();
  let ovNextId = 1;
  const posts = [];
  let stateMode = "ok";
  const stopSpan = { textContent: "Chiudi gioco" };
  const pauseSpan = { textContent: "Pausa" };
  const tabOverview = makeEl("ov-tab-overview", { dataset: { tab: "overview" }, attrs: { role: "tab" } });
  const tabEmu = makeEl("ov-tab-emu", { dataset: { tab: "emu" }, attrs: { role: "tab" }, hidden: true });
  const panelOverview = makeEl("ov-panel-overview", { dataset: { panel: "overview" } });
  const panelPerf = makeEl("ov-panel-perf", { dataset: { panel: "perf" }, hidden: true });
  const shotBtn = makeEl("ov-shot");
  const pauseBtn = makeEl("ov-pause", { _span: pauseSpan });
  const stopBtn = makeEl("ov-stop", { _span: stopSpan });
  const closeBtn = makeEl("ov-close");
  const cardEl = makeEl("ov-card");
  const bySel = {
    "#ov-back": makeEl("ov-back"),
    "#ov-close": closeBtn,
    "#ov-shot": shotBtn,
    "#ov-pause": pauseBtn,
    "#ov-pause span": pauseSpan,
    "#ov-stop": stopBtn,
    "#ov-title": makeEl("ov-title"),
    "#ov-none": makeEl("ov-none"),
    "#ov-time": makeEl("ov-time"),
    "#ov-cover": makeEl("ov-cover"),
    "#ov-msg": makeEl("ov-msg"),
    "#ov-emu-msg": makeEl("ov-emu-msg"),
    "#ov-ach": makeEl("ov-ach"),
    "#ov-notes-list": makeEl("ov-notes-list"),
    "#ov-notes-empty": makeEl("ov-notes-empty"),
    '[data-tab=emu]': tabEmu,
    ".ov-card": cardEl,
  };
  const allButtons = [tabOverview, tabEmu, shotBtn, pauseBtn, stopBtn, closeBtn];
  const ovCtx = {
    navigator: { getGamepads: () => [] },
    document: {
      hidden: false,
      activeElement: null,
      querySelector: (s) => bySel[s] || null,
      querySelectorAll: (s) => {
        if (s === "[role=tab]") return [tabOverview, tabEmu];
        if (s === "[data-panel]") return [panelOverview, panelPerf];
        if (s === ".ov-panel:not([hidden]) button:not(:disabled)") return [shotBtn, pauseBtn, stopBtn, closeBtn];
        if (s === ".ov-card button:not(:disabled)") return allButtons;
        if (s === ".ov-card button.focus") return allButtons.filter((b) => b.classList.contains("focus"));
        return [];
      },
      createElement: () => ({}),
      addEventListener() {},
    },
    GSI18n: { ready: Promise.resolve() },
    t: (k) => k,
    setInterval: () => { const id = ovNextId++; ovIntervals.add(id); return id; },
    clearInterval: (id) => ovIntervals.delete(id),
    setTimeout,
    clearTimeout,
    addEventListener: () => {},
    fetch: async (url) => {
      if (url === "/api/overlay/state") {
        if (stateMode === "neterr") throw new Error("down");
        return { ok: true, json: async () => ({ running: true, paused: true, paused_total: 10, elapsed: 65, started: 10, gid: null, title: "Manual Game", emu: null }) };
      }
      posts.push(url);
      return { ok: true, json: async () => ({ ok: true }) };
    },
  };
  ovCtx.window = ovCtx;
  vm.runInNewContext(fs.readFileSync("pozzo/app/static/overlay.js", "utf8"), ovCtx);
  await ovCtx.window.ovRefresh();
  // anche senza gid, il primo pulsante dell'azione riceve focus e il timer mostra 1:05
  assert.strictEqual(ovCtx.document.activeElement, shotBtn);
  assert.strictEqual(bySel["#ov-time"].textContent, "1:05");
  assert.ok(ovIntervals.size >= 2);
  // primo click su #ov-stop arma conferma senza chiudere il gioco
  await stopBtn.click();
  assert.strictEqual(stopBtn.classList.contains("armed"), true);
  assert.strictEqual(stopSpan.textContent, "o.overlay.stopConfirm");
  assert.strictEqual(posts.includes("/api/running/stop"), false);
  // secondo click ferma il gioco e chiude overlay
  await stopBtn.click();
  assert.strictEqual(posts.includes("/api/running/stop"), true);
  assert.strictEqual(posts.includes("/api/overlay/hide"), true);
  // chiudere in pausa riprende il gioco (la route nasconde da se), non lo lascia congelato davanti
  posts.length = 0;
  await closeBtn.click();
  assert.deepStrictEqual(posts, ["/api/overlay/resume"]);
  // ovHide ferma tutti i timer (sessione, stats, pad)
  ovCtx.window.ovHide();
  assert.strictEqual(ovIntervals.size, 0);
  // errore di rete mostra messaggio dedicato, non o.overlay.none
  stateMode = "neterr";
  await ovCtx.window.ovRefresh();
  assert.strictEqual(bySel["#ov-none"].hidden, false);
  assert.strictEqual(bySel["#ov-none"].textContent, "o.overlay.netError");
  ovCtx.window.ovHide();
})().catch((e) => { console.error(e); process.exit(1); });
"""
    res = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=False)
    assert res.returncode == 0, res.stderr or res.stdout



def test_overlay_media_uses_shared_route_and_localized_msg():
    js = Path("pozzo/app/static/overlay.js").read_text(encoding="utf-8")
    assert "/api/media/keys" in js and "/api/overlay/media" not in js
    assert "r.message" not in js
    assert not hasattr(__import__("pozzo.app.routes.overlay", fromlist=["x"]), "_MEDIA_ACTIONS")
