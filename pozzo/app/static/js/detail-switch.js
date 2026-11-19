"use strict";
/* Switch: aggiornamento, DLC e mod con cui parte il gioco. Le scelte stanno nel profilo del gioco;
   all'avvio Pozzo le scrive nei file di Ryujinx/Eden (niente installazione nella NAND, niente copie). */

const SW_ERR = { xci: "f.sw.err.xci", ambiguo: "f.sw.err.ambiguous", "prod.keys": "f.sw.err.keys" };

async function loadSwitchPanel(d) {
  const body = document.querySelector("#detail-body");
  if (!body || !d?.id) return;
  body.querySelector("#d-switch")?.remove();
  const url = `/api/game/${d.id}/switch/contents`;
  let data;
  try { data = await api(url); } catch { return; }  // file non raggiungibili: niente sezione, l'etichetta resta
  if (typeof S !== "undefined" && S.detail !== d) return;
  const sec = document.createElement("section");
  sec.id = "d-switch";
  body.append(sec);

  const run = async (fn) => {
    try { data = await fn(); draw(); } catch (e) { toast(e.message, true); }
  };
  const save = (patch) => run(() => api(url, { body: { ...data.choice, ...patch } }));
  const offOf = (attr) => [...sec.querySelectorAll(`[${attr}]`)].filter((c) => !c.checked).map((c) => c.getAttribute(attr));

  function draw() {
    const ch = data.choice;
    const ups = data.updates.map((u) => `<option value="${esc(u.path)}"${ch.update === u.path ? " selected" : ""}>${esc(t("f.sw.version", { v: u.version }))} · ${esc(u.name)}</option>`).join("");
    const dlcs = data.dlcs.map((x) => `<label class="chk d-sw-row"><input type="checkbox" data-sw-dlc="${esc(x.path)}"${x.enabled ? " checked" : ""}${x.error ? " disabled" : ""}>
      <span>${esc(x.name)}${x.error ? ` <span class="muted small">${esc(t(SW_ERR[x.error] || "f.sw.err.other", { msg: x.error }))}</span>` : ""}</span></label>`).join("");
    const mods = data.mods.map((m) => `<div class="d-sw-row"><label class="chk grow"><input type="checkbox" data-sw-mod="${esc(m.name)}"${m.enabled ? " checked" : ""}> <span>${esc(m.name)}</span></label>
      <button class="btn" type="button" data-sw-rm="${esc(m.name)}">${t("f.btn.remove")}</button></div>`).join("");
    sec.innerHTML = `<div class="d-h">${t("f.sw.heading")}</div>
      <label class="small d-sw-up">${t("f.sw.update")}
        <select class="field" data-sw-up><option value="latest"${ch.update === "latest" ? " selected" : ""}>${t("f.sw.latest")}</option>
        <option value="none"${ch.update === "none" ? " selected" : ""}>${t("f.sw.none")}</option>${ups}</select></label>
      <div class="d-h">${t("f.sw.dlc")}</div>
      ${dlcs || `<p class="muted small">${t("f.sw.noDlc")}</p>`}
      <div class="row"><button class="btn" type="button" data-sw-add>${t("f.sw.addFile")}</button></div>
      <div class="d-h">${t("f.mods.heading")}</div>
      ${mods || `<p class="muted small">${t("f.sw.noMods")}</p>`}
      <div class="row"><button class="btn" type="button" data-sw-mod-file>${t("f.sw.modFile")}</button>
        <button class="btn" type="button" data-sw-mod-dir>${t("f.sw.modDir")}</button></div>
      <p class="muted small">${t("f.sw.note")}</p>`;
  }

  sec.addEventListener("change", (e) => {
    if (e.target.matches("[data-sw-up]")) return save({ update: e.target.value });
    if (e.target.matches("[data-sw-dlc]")) return save({ dlc_off: offOf("data-sw-dlc").concat(data.dlcs.filter((x) => x.error).map((x) => x.path)) });
    if (e.target.matches("[data-sw-mod]")) return save({ mods_off: offOf("data-sw-mod") });
  });
  sec.addEventListener("click", async (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.hasAttribute("data-sw-add")) {
      const p = await pickPath("file");
      if (p) save({ extra: [...data.choice.extra, p] });
    } else if (b.hasAttribute("data-sw-mod-file") || b.hasAttribute("data-sw-mod-dir")) {
      const p = await pickPath(b.hasAttribute("data-sw-mod-dir") ? "folder" : "file");
      if (p) run(() => api(`/api/game/${d.id}/switch/mods`, { body: { path: p } }));
    } else if (b.dataset.swRm && confirm(t("f.sw.rmConfirm", { name: b.dataset.swRm }))) {
      run(() => api(`/api/game/${d.id}/switch/mods/${encodeURIComponent(b.dataset.swRm)}`, { method: "DELETE" }));
    }
  });
  draw();
}
