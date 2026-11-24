"use strict";
/* Pozzo Launcher - frontend: emulatori. Script classico: ambito globale condiviso con gli altri file di js/ (ordine in index.html). */

/* ---- emulatori */
async function loadEmu() {
  try { SET.emu = await api("/api/emulators"); } catch (e) { return toast(e.message, true); }
  renderEmu(SET.emu);
  renderEmuInstall();
  api("/api/app/launch").then((l) => {
    $("#ln-before").value = l.before || ""; $("#ln-after").value = l.after || ""; $("#ln-close").checked = !!l.close_launcher; $("#ln-splash").checked = l.splash !== false;
  }).catch(() => {});
}

function collectEmu() {
  const emulators = {};
  document.querySelectorAll(".emu-path").forEach((i) => { emulators[i.dataset.emu] = i.value.trim(); });
  const platforms = {};
  document.querySelectorAll("#emu-table tr[data-p]").forEach((tr) => {
    platforms[tr.dataset.p] = { emulator: $(".emu-sel", tr).value.replace("__new", ""), core: $(".emu-core", tr).value, args: $(".emu-args", tr).value };
  });
  return { emulators, platforms, retroarch_cores: $("#ra-cores") ? $("#ra-cores").value : undefined };
}

function renderEmu(d, draft) {
  // draft = modifiche non ancora salvate da conservare quando si ridisegna
  const paths = { ...d.emulators, ...(draft ? draft.emulators : {}) };
  $("#emu-saved-to").textContent = t("i.emu.savedTo", { p: d.settings });
  const used = new Set(SET.extraEmus);
  d.platforms.forEach((p) => { p.candidates.forEach((c) => used.add(c.split(" ")[0])); if (p.emulator) used.add(p.emulator); });
  Object.keys(paths).forEach((k) => used.add(k));
  const names = [...used].sort();
  $("#emu-paths").innerHTML = `<table class="emu"><tr><th style="width:130px">${t("i.emu.col.emulator")}</th><th>${t("i.emu.col.exePath")}</th><th style="width:96px"></th></tr>`
    + names.map((n) => `<tr><td>${esc(n)}</td><td><input class="field emu-path" data-emu="${esc(n)}" value="${esc(paths[n] || "")}" placeholder="${t("i.emu.notConfigured")}"></td>`
      + `<td><button class="btn emu-pick" data-emu="${esc(n)}">${t("i.emu.browse")}</button></td></tr>`).join("")
    + `<tr><td class="muted">${t("i.emu.core")}</td><td><input class="field" id="ra-cores" value="${esc(draft && draft.retroarch_cores !== undefined ? draft.retroarch_cores : d.retroarch_cores || "")}" `
    + `placeholder="${t("i.emu.cores.placeholder")}"></td><td></td></tr></table>`;
  const known = [...new Set([...d.known, ...names])].sort();
  // console da sistemare in cima (sort stabile): sono quelle per cui l'utente apre la pagina
  const plats = [...d.platforms].sort((x, y) => !!x.effective - !!y.effective);
  const bad = plats.filter((p) => !p.effective).length;
  $("#emu-table").innerHTML = `<p class="small emu-sum" role="status">${t("i.emu.summary", { ok: plats.length - bad, bad })}</p>`
    + `<table class="emu"><tr><th>${t("i.emu.col.console")}</th><th style="width:200px">${t("i.emu.col.emulator")}</th><th style="width:200px">${t("i.emu.col.status")}</th></tr>`
    + plats.map((p) => {
      const dp = draft && draft.platforms[p.platform] ? draft.platforms[p.platform] : { emulator: p.emulator, core: p.core, args: p.args };
      const rec = new Set(p.candidates.map((c) => c.split(" ")[0]));
      const opts = [`<option value="">${t("i.emu.auto")}</option>`,
        ...known.map((k) => `<option value="${esc(k)}" ${k === dp.emulator ? "selected" : ""}>${esc(k)}${rec.has(k) ? " ★" : ""}</option>`),
        `<option value="__new">${t("i.emu.other")}</option>`].join("");
      const status = p.effective ? `<span class="status-ok">✓ ${esc(p.effective)}</span>` : `<span class="status-bad">${esc(p.problem || t("i.emu.notConfigured"))}</span>`;
      // core e argomenti restano nella riga (li legge collectEmu) ma si vedono solo a riga aperta
      return `<tr data-p="${esc(p.platform)}" data-name="${esc(p.name)}"${p.effective ? "" : " data-open"}><td><button class="emu-more" type="button" aria-expanded="${p.effective ? "false" : "true"}">${esc(p.name)}</button><div class="muted small">${t("i.emu.recommended", { list: esc(p.candidates.join(", ") || "—") })}</div>`
        + `<div class="emu-adv"><label class="small"><span class="muted">${t("i.emu.col.core")}</span><input class="field emu-core" value="${esc(dp.core)}" placeholder="${esc(p.default_core)}"></label>`
        + `<label class="small"><span class="muted">${t("i.emu.col.args")}</span><input class="field emu-args" value="${esc(dp.args)}" placeholder="${esc(p.default_args)}"></label></div></td>`
        + `<td><select class="field emu-sel" aria-label="${esc(p.name)}">${opts}</select></td><td>${status}</td></tr>`;
    }).join("") + `</table>`;
}

async function renderEmuInstall() {
  let d;
  try { d = await api("/api/emulators/catalog"); } catch (e) { return toast(e.message, true); }
  const cores = d.cores.length ? `<div class="row"><span class="muted small grow">${t("i.emu.coresMissing", { list: esc(d.cores.join(", ")) })}</span>`
    + `<button class="btn" data-emu-cores ${d.retroarch ? "" : "disabled title=\"" + t("i.emu.installRetroarchFirst") + "\""}>⬇ ${t("i.emu.downloadCores")}</button></div>` : "";
  // vetrina come uno store: installati, disponibili, e in fondo (chiusi) quelli senza build per questo processore
  const shelves = [
    [t("i.emu.store.installed"), d.items.filter((x) => x.installed)],
    [t("i.emu.store.available"), d.items.filter((x) => !x.installed && x.arch_ok !== false)],
  ];
  const blocked = d.items.filter((x) => !x.installed && x.arch_ok === false);
  const shelf = ([title, list]) => (list.length ? `<section class="emu-shelf"><h4 class="emu-shelf-h">${esc(title)} <span class="muted">${list.length}</span></h4>
    <div class="emu-cards">${list.map((x) => emuCard(x, d)).join("")}</div></section>` : "");
  $("#emu-inst").innerHTML = shelves.map(shelf).join("")
    + (blocked.length ? `<details class="emu-shelf emu-fold"><summary>${t("i.emu.store.unavailable", { arch: esc(d.arch) })} <span class="muted">${blocked.length}</span></summary>
      <div class="emu-cards">${blocked.map((x) => emuCard(x, d)).join("")}</div></details>` : "")
    + `${cores}<p class="muted small">${t("i.emu.defaultDir", { dir: esc(d.dir) })}</p>`;
  markEmuUpdates();
}

// nomi come li scrivono i progetti (l'id del catalogo e' in minuscolo)
const EMU_NAMES = { azahar: "Azahar", cemu: "Cemu", dolphin: "Dolphin", "dosbox-staging": "DOSBox Staging", duckstation: "DuckStation",
  eden: "Eden", eglantine: "Eglantine", flycast: "Flycast", melonds: "melonDS", mesen: "Mesen", mgba: "mGBA", openemu: "OpenEmu",
  pcsx2: "PCSX2", ppsspp: "PPSSPP", retroarch: "RetroArch", rmg: "Rosalie's Mupen GUI", rpcs3: "RPCS3", ryujinx: "Ryujinx",
  shadps4: "shadPS4", vita3k: "Vita3K", xemu: "xemu", xenia: "Xenia Canary" };

function emuCard(x, d) {
  const name = EMU_NAMES[x.id] || x.id;
  const aboutKey = `i.emu.about.${x.id}`;
  const about = t(aboutKey) === aboutKey ? "" : t(aboutKey);
  const hue = [...x.id].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 7);  // colore stabile per l'iniziale
  const ver = x.installed ? `<span class="emu-ver">${esc(x.version || t("i.common.installed"))}</span>` : "";
  const note = x.arch_ok === false ? `<p class="emu-note" id="emu-arch-${esc(x.id)}">${t("i.emu.wrongArch", { arch: esc(d.arch) })}</p>`
    : !x.installed && x.configured ? `<p class="emu-note">${t("i.emu.alreadySet")}</p>` : "";
  // installato: «Aggiorna» resta secondario finche' non c'e' davvero una versione nuova (markEmuUpdates)
  const main = x.arch_ok === false
    ? `<button class="btn" type="button" disabled aria-describedby="emu-arch-${esc(x.id)}">${ic("download")} ${t("i.common.install")}</button>`
    : x.installed
      ? `<button class="btn" type="button" data-emu-inst="${esc(x.id)}">${ic("refresh")} ${t("i.common.update")}</button>`
      : `<button class="btn primary" type="button" data-emu-inst="${esc(x.id)}">${ic("download")} ${t("i.common.install")}</button>`;
  // solo quelli installati da Pozzo: quelli indicati a mano non si toccano
  const remove = x.installed ? `<button class="btn emu-remove" type="button" data-emu-uninst="${esc(x.id)}" title="${esc(t("i.emu.uninstall_tip"))}"
    aria-label="${esc(t("i.emu.uninstall"))} ${esc(name)}">${ic("trash")}<span>${t("i.emu.uninstall")}</span></button>` : "";
  return `<article class="emu-card${x.installed ? " is-installed" : ""}" data-emu-card="${esc(x.id)}">
    <div class="emu-ic" style="--emu-hue:${hue}"><span aria-hidden="true">${esc(name.charAt(0))}</span>
      <img src="/api/emulators/icon/${encodeURIComponent(x.id)}" alt="" loading="lazy" data-onerr="remove"></div>
    <div class="emu-meta">
      <div class="emu-title"><b>${esc(name)}</b>${ver}</div>
      ${about ? `<p class="emu-about">${esc(about)}</p>` : ""}
      ${x.consoles.every((c) => about.includes(c)) ? "" : `<p class="emu-cons" title="${esc(x.consoles.join(", "))}">${esc(x.consoles.join(" · "))}</p>`}
      ${note}
    </div>
    <div class="emu-actions">${main}${remove}
      <a href="#" class="emu-site" data-open="${esc(x.home)}">${t("i.emu.site")} ${ic("external")}</a></div>
  </article>`;
}

// versioni nuove (controllo in cache 12 ore): «Aggiorna» diventa il pulsante principale con la versione
async function markEmuUpdates() {
  let r;
  try { r = await api("/api/emulators/updates"); } catch { return; }
  for (const u of r.updates || []) {
    const card = document.querySelector(`.emu-card[data-emu-card="${CSS.escape(u.id)}"]`);
    if (!card) continue;
    const b = card.querySelector("[data-emu-inst]");
    const v = card.querySelector(".emu-ver");
    if (u.update && b) {
      b.classList.add("primary");
      b.innerHTML = `${ic("download")} ${esc(t("i.emu.updateTo", { v: u.latest }))}`;
      v?.insertAdjacentHTML("afterend", `<span class="emu-new">${esc(t("i.emu.newVersion"))}</span>`);
    } else if (b && u.latest) {
      b.title = t("i.emu.upToDate");
    }
  }
}

async function followEmuJob() {
  let j;
  do {
    try { j = await api("/api/emulators/job"); } catch { return; }
    const pct = j.total ? Math.round((j.done / j.total) * 100) : 0;
    $("#emu-inst-job").innerHTML = `<p class="small">${j.status === "running" ? `⏳ ${j.total ? `${pct}% · ${t("i.common.ofSize", { a: fmtSize(j.done), b: fmtSize(j.total) })}` : j.done ? fmtSize(j.done) : ""}` : ""}</p>
      <pre class="log">${esc(j.log.slice(-6).join("\n"))}</pre>`;
    if (j.status === "running") await new Promise((r) => setTimeout(r, 1000));
  } while (j.status === "running");
  if (j.status === "error") toast(j.log[j.log.length - 1] || t("i.common.installFailed"), true);
  else toast(j.log[j.log.length - 1] || t("i.common.done"));
  loadEmu();
}

async function saveEmu(body) {
  try {
    SET.emu = await api("/api/emulators", { body: body || collectEmu() });
    SET.extraEmus = [];
    renderEmu(SET.emu);
    toast(t("i.emu.saved"));
    if (S.detail) openDetail(S.detail.id);
  } catch (e) { toast(e.message, true); }
}

function showStatus(st) {
  const n = S.games.length;
  $("#lib-info").textContent = t("i.emu.libInfo", { v: n.toLocaleString(GSI18n.lang), g: S.groups.length.toLocaleString(GSI18n.lang), c: S.colls.length });
  $("#build-log").textContent = (st.build_log || []).join("\n");
  $("#rebuild-btn").disabled = st.building;
  $("#rebuild-btn").textContent = st.building ? t("i.emu.rebuilding") : "↻ " + t("i.emu.refreshLibrary");
  $("#thumbs-info").textContent = st.thumbs_total ? t("i.emu.thumbs", { done: st.thumbs_done.toLocaleString(GSI18n.lang), total: st.thumbs_total.toLocaleString(GSI18n.lang) }) : "";
}

async function rebuild() {
  await api("/api/rebuild", { body: {} });
  const tick = async () => {
    const st = await api("/api/status");
    showStatus(st);
    if (st.building) setTimeout(tick, 1000);
    else { await reload(true); toast(t("i.emu.libUpdated")); }
  };
  tick();
}

async function waitFirstBuild() {
  $("#splash").hidden = false;
  for (;;) {
    const st = await api("/api/status");
    $("#splash-log").textContent = (st.build_log || []).join("\n");
    if (st.has_library && !st.building) break;
    await new Promise((r) => setTimeout(r, 1000));
  }
  $("#splash").hidden = true;
}

async function reload(keepScroll) {
  await loadLibrary();
  if (S.view.type === "collection" && !S.collBySlug.has(S.view.id)) S.view = { type: "all" };
  renderSidebar();
  refreshGrid(keepScroll);
}

/* dettagli per console (consiglio, BIOS, preset) e salti della barra delle sezioni */
document.addEventListener("click", (e) => {
  const m = e.target.closest(".emu-more");
  if (m) { const tr = m.closest("tr"); tr.toggleAttribute("data-open"); m.setAttribute("aria-expanded", tr.hasAttribute("data-open")); return; }
  const g = e.target.closest("[data-goto]");
  if (g) document.getElementById(g.dataset.goto)?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
});
