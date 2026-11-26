// HUD leggero: nessuna richiesta se la finestra e' nascosta; una sola richiesta (tempo + metriche) ogni 2 s
const $ = (s) => document.querySelector(s);
let hudActive = false, hasSession = false, paused = false, baseElapsed = 0, syncAt = 0;
let tickTimer = null, pollTimer = null;
const fmt = (s) => { s = Math.max(0, Math.round(s)); const h = Math.floor(s / 3600), m = Math.floor(s / 60) % 60; return (h ? h + ":" + String(m).padStart(2, "0") : m) + ":" + String(s % 60).padStart(2, "0"); };

function tickHud() {
  if (!hudActive || document.hidden) return;
  if (!hasSession) { $("#h-time").textContent = "0:00"; return; }
  const cur = paused ? baseElapsed : baseElapsed + (Date.now() - syncAt) / 1000;
  $("#h-time").textContent = fmt(cur);
}

async function poll() {
  if (!hudActive || document.hidden) return;
  try {
    if (window.GSI18n?.ready) await window.GSI18n.ready;
    const r = await fetch("/api/overlay/stats");
    if (!r.ok) return;
    const s = await r.json();
    const wasPaused = paused;
    paused = Boolean(s.paused);
    hasSession = Boolean(s.started || s.elapsed > 0);
    if (!paused || !wasPaused) {
      baseElapsed = s.elapsed;
      syncAt = Date.now();
    }
    tickHud();
    $("#h-st").textContent = `${t("o.overlay.cpu")} ${s.cpu}% · ${t("o.overlay.ram")} ${s.ram}%`;
  } catch (e) { /* server non raggiungibile: restano gli ultimi valori */ }
}

function hudShow() {
  hudActive = true;
  if (!tickTimer) tickTimer = setInterval(tickHud, 1000);
  if (!pollTimer) { poll(); pollTimer = setInterval(poll, 2000); }
}

function hudHide() {
  hudActive = false;
  clearInterval(tickTimer); clearInterval(pollTimer);
  tickTimer = pollTimer = null;
}

window.hudShow = hudShow;
window.hudHide = hudHide;
document.addEventListener("visibilitychange", () => { if (!document.hidden && hudActive) { poll(); tickHud(); } });
window.addEventListener("load", hudShow);
