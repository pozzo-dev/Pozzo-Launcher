"use strict";
/* «Riduci spazio su disco»: compressione WOF di un gioco PC, di una ROM o di una console (solo Windows). */
function wofAvailable(g) {
  return /Win/.test(navigator.platform) && (g.store ? !["online", "manual"].includes(g.store) && g.installed : true);
}

/** La voce del menu parte bloccata e si attiva solo se il server dice che c'e' spazio da guadagnare. */
async function wofGate(el, kind, ref) {
  el.setAttribute("aria-disabled", "true");
  try {
    const r = await api(`/api/wof/${kind}/${encodeURIComponent(ref)}/check`);
    if (r.ok) el.removeAttribute("aria-disabled"); else el.title = r.reason;
  } catch (e) { el.title = e.message; }
}

/** kind: "game" (ref = id) oppure "platform" (ref = console) */
async function openWof(kind, ref) {
  const url = `/api/wof/${kind}/${encodeURIComponent(ref)}`;
  let info;
  try { info = await api(url); } catch (e) { return toast(e.message, true); }
  const dlg = document.createElement("dialog");
  dlg.className = "small-dlg";
  const est = info.estimate;
  const bytes = (n) => fmtSize(n) || "0";
  const sav = (a) => est?.savings?.[a] != null ? ` (−${fmtSize(est.savings[a])})` : "";
  dlg.innerHTML = `<form method="dialog" class="dlg-head"><h2>${esc(t("w.wof.title"))}</h2><button class="icon-btn" aria-label="${esc(t("a.common.close"))}">✕</button></form>
    <div class="dlg-body">
      <p class="muted small">${esc(info.folder)} · ${esc(t("w.wof.sizes", {n: info.count, size: bytes(info.size), disk: bytes(info.disk)}))}</p>
      <p class="small">${est ? esc(t("w.wof.estimate", {name: est.name, best: est.best, saved: fmtSize(est.savings[est.best])})) : esc(t("w.wof.sampled", {saved: bytes(info.sampled)}))}</p>
      ${info.dstorage ? `<p class="small" style="color:var(--warn,#e5a50a)">${esc(t("w.wof.dstorage"))}</p>
        <label class="small"><input type="checkbox" id="wof-ds"> ${esc(t("w.wof.dstorageConfirm"))}</label>` : ""}
      <label class="small">${esc(t("w.wof.algo"))}
        <select id="wof-algo">${info.algos.map((a) => `<option value="${a}"${a === info.default ? " selected" : ""}>${a}${sav(a)}</option>`).join("")}</select></label>
      <progress id="wof-bar" max="1" value="0" hidden style="width:100%"></progress>
      <p class="muted small" id="wof-msg">${esc(info.blocked)}</p>
      <div class="row wrap"><button class="btn primary" id="wof-go"${info.blocked ? " disabled" : ""}>${esc(t("w.wof.compress"))}</button>
        <button class="btn" id="wof-undo"${info.undo ? "" : " disabled"}>${esc(t("w.wof.uncompress"))}</button>
        <button class="btn" id="wof-stop" hidden>${esc(t("w.wof.cancel"))}</button></div>
    </div>`;
  document.body.appendChild(dlg);
  const $d = (s) => dlg.querySelector(s);
  let timer = null;
  const stop = () => { clearInterval(timer); timer = null; };
  const show = (j) => {
    const run = j.status === "running";
    $d("#wof-bar").hidden = !run && j.status !== "done";
    $d("#wof-bar").value = j.total ? Math.min(1, j.done / j.total) : 0;
    if (j.status === "done") { $d("#wof-go").disabled = j.action === "compress"; $d("#wof-undo").disabled = j.action !== "compress"; }
    $d("#wof-go").hidden = $d("#wof-undo").hidden = run;
    $d("#wof-stop").hidden = !run;
    $d("#wof-msg").textContent = run ? t("w.wof.progress", {done: j.done, total: j.total})
      : j.status === "idle" ? "" : t("w.wof.st." + j.status) + (j.error ? ` ${j.error}` : "")
        + (j.action === "compress" ? " " + t("w.wof.saved", {saved: bytes(Math.max(0, j.saved))}) : "");
    if (!run) stop();
  };
  const poll = () => { stop(); timer = setInterval(async () => { try { show(await api(url + "/job")); } catch { stop(); } }, 1000); };
  const start = async (action) => {
    try {
      show(await api(url, { body: { action, algo: $d("#wof-algo").value, confirm_dstorage: !!$d("#wof-ds")?.checked } }));
      poll();
    } catch (e) { toast(e.message, true); }
  };
  $d("#wof-go").onclick = () => start("compress");
  $d("#wof-undo").onclick = () => start("uncompress");
  $d("#wof-stop").onclick = () => api(url, { method: "DELETE" }).catch((e) => toast(e.message, true));
  dlg.addEventListener("close", () => { stop(); dlg.remove(); }); // il lavoro continua in background anche a dialogo chiuso
  if (info.job) { show(info.job); if (info.job.status === "running") poll(); }
  dlg.showModal();
}
