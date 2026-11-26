// Overlay in gioco: schede (panoramica, prestazioni, emulatore, media e note). Navigabile con tastiera e controller.
const $ = (s) => document.querySelector(s);
const post = async (u, b) => {
  const r = await fetch(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b || {}) });
  const d = await r.json().catch(() => ({}));
  return { _ok: r.ok, ...d };
};
const fmt = (s) => { s = Math.max(0, Math.round(s)); const h = Math.floor(s / 3600), m = Math.floor(s / 60) % 60; return (h ? h + ":" + String(m).padStart(2, "0") : m) + ":" + String(s % 60).padStart(2, "0"); };

let st = null, timer = null, statsTimer = null, padTimer = null, msgTimer = null, stopTimer = null;
let tab = "overview", shown = false, stopArmed = false, baseElapsed = 0, syncAt = 0, prev = {};
const bar = (id, pct) => { $(id).style.transform = `scaleX(${Math.max(0, Math.min(100, pct || 0)) / 100})`; };

function showMsg(txt) {
  const el = $("#ov-msg");
  clearTimeout(msgTimer); msgTimer = null;
  if (!txt) { el.hidden = true; el.textContent = ""; return; }
  el.textContent = txt;
  el.hidden = false;
  msgTimer = setTimeout(() => { el.hidden = true; }, 3500);
}

function disarmStop() {
  clearTimeout(stopTimer); stopTimer = null;
  if (!stopArmed) return;
  stopArmed = false;
  const b = $("#ov-stop");
  b.classList.remove("armed");
  b.querySelector("span").textContent = t("o.overlay.stop");
}

function setFocus(el) {
  document.querySelectorAll(".ov-card button.focus").forEach((b) => b.classList.remove("focus"));
  if (el) { el.classList.add("focus"); el.focus(); }
}

// il server chiama ovHide() prima di nascondere la finestra: da chiusa non resta nessun timer ne' polling
window.ovHide = () => {
  shown = false;
  prev = {};
  disarmStop();
  showMsg("");
  clearInterval(timer); clearInterval(statsTimer); clearInterval(padTimer);
  timer = statsTimer = padTimer = null;
};

function tick() {
  if (!shown) return;
  if (!st || (!st.started && !(st.elapsed > 0))) {
    $("#ov-time").textContent = "0:00";
    return;
  }
  const cur = st.paused ? baseElapsed : baseElapsed + (Date.now() - syncAt) / 1000;
  $("#ov-time").textContent = fmt(cur);
}

// ---- schede e focus separati dalle azioni del pannello
const tabBtns = () => [...document.querySelectorAll("[role=tab]")].filter((b) => !b.hidden);
const actionBtns = () => [...document.querySelectorAll(".ov-panel:not([hidden]) button:not(:disabled)")].filter((b) => !b.hidden);
const allBtns = () => [...document.querySelectorAll(".ov-card button:not(:disabled)")].filter((b) => !b.hidden && !b.closest("[hidden]"));

function focusFirst() {
  const a = actionBtns();
  setFocus(a[0] || tabBtns().find((x) => x.dataset.tab === tab) || allBtns()[0]);
}

function showTab(name, focusPanel) {
  disarmStop();
  const list = tabBtns();
  const b = list.find((x) => x.dataset.tab === name) || list[0];
  tab = b.dataset.tab;
  list.forEach((x) => {
    const on = x === b;
    x.setAttribute("aria-selected", String(on));
    x.tabIndex = on ? 0 : -1;
  });
  document.querySelectorAll("[data-panel]").forEach((p) => { p.hidden = p.dataset.panel !== tab; });
  if (focusPanel) focusFirst();
  pollStats();
}

const stepTab = (d) => {
  const l = tabBtns(), i = l.findIndex((x) => x.dataset.tab === tab);
  showTab(l[(i + d + l.length) % l.length].dataset.tab, true);
};

// ---- prestazioni: si interroga il server solo con la scheda aperta e la finestra visibile, ogni 2 s
function setStat(id, text, pct) { $(id).textContent = text; bar(id + "-bar", pct); }
async function loadStats() {
  try {
    const r = await fetch("/api/overlay/stats");
    if (!r.ok) return;
    const s = await r.json();
    setStat("#ov-cpu", s.cpu + "%", s.cpu); setStat("#ov-ram", s.ram + "%", s.ram);
    if (s.battery) setStat("#ov-bat", s.battery.percent + "%" + (s.battery.plugged ? " · " + t("o.overlay.plugged") : ""), s.battery.percent);
    else setStat("#ov-bat", t("o.overlay.noBattery"), 0);
  } catch (e) { /* server non raggiungibile: restano gli ultimi valori */ }
}
function pollStats() {
  clearInterval(statsTimer); statsTimer = null;
  if (tab !== "perf" || document.hidden || !shown) return;
  loadStats(); statsTimer = setInterval(loadStats, 2000);
}
document.addEventListener("visibilitychange", pollStats);

const coverEl = $("#ov-cover");
if (coverEl) coverEl.onerror = () => { coverEl.hidden = true; coverEl.removeAttribute("src"); };

async function ovRefresh() {
  shown = true;
  prev = {};
  disarmStop();
  showMsg("");
  if (window.GSI18n?.ready) await window.GSI18n.ready;
  if (!padTimer) padTimer = setInterval(pollPad, 80);
  try {
    const r = await fetch("/api/overlay/state");
    if (!r.ok) throw new Error("http " + r.status);
    st = await r.json();
  } catch (e) {
    st = null;
    $("#ov-none").textContent = t("o.overlay.netError");
    $("#ov-none").hidden = false;
    focusFirst();
    return;
  }
  baseElapsed = st.elapsed;
  syncAt = Date.now();
  $("#ov-title").textContent = st.title || "";
  $("#ov-none").textContent = t("o.overlay.none");
  $("#ov-none").hidden = st.running;
  $("#ov-pause span").textContent = t(st.paused ? "o.overlay.resume" : "o.overlay.pause");
  coverEl.hidden = !st.gid;
  if (st.gid) coverEl.src = `/img/${st.gid}/cover?w=300`;
  else coverEl.removeAttribute("src");
  document.querySelector('[data-tab=emu]').hidden = !st.emu;  // la scheda emulatore c'e' solo con un emulatore supportato
  const ready = !!(st.emu && st.emu.ready);
  document.querySelectorAll("[data-emu]").forEach((b) => { b.disabled = !ready; });
  $("#ov-emu-msg").textContent = st.emu && !ready ? t("o.overlay.emuOff") : "";
  showTab(tab === "emu" && !st.emu ? "overview" : tab, true);
  clearInterval(timer); tick(); timer = setInterval(tick, 1000);
  $("#ov-ach").hidden = true;
  $("#ov-notes-list").replaceChildren();
  $("#ov-notes-empty").hidden = false;
  if (!st.gid) return;
  fetch(`/api/game/${st.gid}/achievements`).then((r) => r.json()).then((a) => {  // il server tiene 1 ora di cache
    const d = a.data; if (!d || !d.total) return;
    $("#ov-ach").hidden = false; $("#ov-ach-txt").textContent = `${d.unlocked} / ${d.total}`;
    bar("#ov-ach-bar", 100 * d.unlocked / d.total);
  }).catch(() => {});
  fetch(`/plugin-api/diario/gioco?id=${st.gid}`).then((r) => (r.ok ? r.json() : null)).then((d) => {  // estensione assente: 404, stato vuoto
    if (!d || !d.voci || !d.voci.length) return;
    $("#ov-notes-list").replaceChildren(...d.voci.slice(0, 3).map((v) => Object.assign(document.createElement("li"), { textContent: v.testo })));
    $("#ov-notes-empty").hidden = true;
  }).catch(() => {});
}
window.ovRefresh = ovRefresh;

function move(d, axis) {
  const cur = document.activeElement;
  if (cur && cur.getAttribute("role") === "tab") {
    if (axis === "x") { stepTab(d); return; }
    if (d > 0 && actionBtns().length) { setFocus(actionBtns()[0]); return; }
  }
  const b = actionBtns();
  if (!b.length) {
    const tb = tabBtns();
    if (!tb.length) return;
    const i = tb.indexOf(cur);
    setFocus(tb[(i + d + tb.length) % tb.length]);
    return;
  }
  const i = b.indexOf(cur);
  setFocus(b[(i + d + b.length) % b.length]);
}

const hide = () => post("/api/overlay/hide").catch(() => {});
// chiusa in pausa: riprende (la route nasconde da sola), altrimenti il gioco resterebbe congelato davanti
const close = () => (st && st.paused ? post("/api/overlay/resume").catch(() => {}) : hide());

// un'azione alla volta per pulsante; un errore di rete non lascia il pulsante bloccato ne' lancia eccezioni
async function act(btn, fn) {
  if (btn.disabled) return;
  btn.disabled = true;
  try { await fn(); } catch (e) { showMsg(t("o.overlay.netError")); } finally { btn.disabled = false; setFocus(btn); }
}

$("#ov-back").onclick = $("#ov-close").onclick = close;
$("#ov-shot").onclick = (e) => act(e.currentTarget, async () => {
  const r = await post("/api/overlay/screenshot");
  showMsg(r._ok && r.ok ? t("o.overlay.shotSaved") : (r.detail || t("o.overlay.actionFailed")));
});
$("#ov-pause").onclick = (e) => act(e.currentTarget, async () => {
  const wasPaused = Boolean(st && st.paused);
  const r = await post(wasPaused ? "/api/overlay/resume" : "/api/overlay/pause");
  if (!r._ok || r.ok === false) { showMsg(r.detail || t("o.overlay.actionFailed")); return; }
  if (!wasPaused) await ovRefresh(); // ripreso: la route ha gia' nascosto l'overlay
});
$("#ov-stop").onclick = async (e) => {
  const btn = e.currentTarget;
  if (!stopArmed) {
    stopArmed = true;
    btn.classList.add("armed");
    btn.querySelector("span").textContent = t("o.overlay.stopConfirm");
    stopTimer = setTimeout(disarmStop, 4000);
    return;
  }
  disarmStop();
  await act(btn, () => post("/api/running/stop"));
  hide();
};
$("#ov-stop").addEventListener("blur", disarmStop);

document.querySelectorAll("[data-media]").forEach((b) => b.onclick = () => act(b, async () => {
  const r = await post("/api/media/keys", { action: b.dataset.media });
  showMsg(r._ok && r.ok !== false ? t("o.overlay.mediaSent") : (r.detail || t("o.overlay.actionFailed")));
}));
document.querySelectorAll("[data-emu]").forEach((b) => b.onclick = () => act(b, async () => {
  const r = await post("/api/overlay/emu", { action: b.dataset.emu });
  $("#ov-emu-msg").textContent = r._ok ? t("o.overlay.emuSent") : (r.detail || t("o.overlay.actionFailed"));
}));
document.querySelectorAll("[role=tab]").forEach((b) => b.onclick = () => { showTab(b.dataset.tab, false); setFocus(b); });

document.querySelector(".ov-card").addEventListener("focusin", (e) => {
  const b = e.target.closest("button");
  document.querySelectorAll(".ov-card button.focus").forEach((x) => { if (x !== b) x.classList.remove("focus"); });
  if (b) b.classList.add("focus");
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") close();
  else if (e.key === "PageDown") { e.preventDefault(); stepTab(1); }
  else if (e.key === "PageUp") { e.preventDefault(); stepTab(-1); }
  else if (e.key === "Tab") {
    const list = allBtns();
    if (!list.length) return;
    e.preventDefault();
    const i = list.indexOf(document.activeElement);
    const next = e.shiftKey ? (i <= 0 ? list.length - 1 : i - 1) : (i < 0 || i >= list.length - 1 ? 0 : i + 1);
    setFocus(list[next]);
  }
  else if (e.key === "ArrowRight") { e.preventDefault(); move(1, "x"); }
  else if (e.key === "ArrowDown") { e.preventDefault(); move(1, "y"); }
  else if (e.key === "ArrowLeft") { e.preventDefault(); move(-1, "x"); }
  else if (e.key === "ArrowUp") { e.preventDefault(); move(-1, "y"); }
});

// controller: croce/levetta per spostarsi, A conferma, B chiude, LB/RB cambiano scheda (Select+R3 chiude anche da XInput lato server)
function pollPad() {
  if (document.hidden || !shown) return;  // overlay nascosto: niente polling del pad
  const p = (navigator.getGamepads ? [...navigator.getGamepads()] : []).find(Boolean); if (!p) return;
  const down = { l: p.buttons[14]?.pressed || p.axes[0] < -.6, r: p.buttons[15]?.pressed || p.axes[0] > .6,
    u: p.buttons[12]?.pressed || p.axes[1] < -.6, d: p.buttons[13]?.pressed || p.axes[1] > .6, a: p.buttons[0]?.pressed, b: p.buttons[1]?.pressed,
    lb: p.buttons[4]?.pressed, rb: p.buttons[5]?.pressed };
  if ((down.r || down.d) && !prev.r && !prev.d) move(1, down.r ? "x" : "y");
  if ((down.l || down.u) && !prev.l && !prev.u) move(-1, down.l ? "x" : "y");
  if (down.rb && !prev.rb) stepTab(1);
  if (down.lb && !prev.lb) stepTab(-1);
  if (down.a && !prev.a) document.activeElement?.click();
  if (down.b && !prev.b) close();
  prev = down;
}
