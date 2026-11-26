// Link → Store: procedura in 3 passi. 1) l'indirizzo di una pagina che raccoglie altri siti; 2) i link da tenere,
// raggruppati per intestazione (h2/h3); 3) la console di ogni gruppo (indovinata dal titolo) e «Aggiungi».
// Aggiungere non scarica nulla: scrive settings.json; «Leggi subito» avvia la lettura come Impostazioni › Store.
const VIEW = "linkstores";
const MAX_ROWS = 400; // link mostrati prima di «Mostra tutti»: pagine con migliaia di link restano usabili

export default function (gs, ctx) {
  const { t, lang } = ctx;
  const esc = gs.esc;
  let state = { platforms: [], catalogs: {}, pc_stores: [] };
  let step = 1, url = "", externalOnly = true, scan = null, query = "", showAll = false;
  const picked = new Set();      // indirizzi scelti al passo 2
  const dest = new Map();        // nome del gruppo -> {platform, kind} al passo 3

  gs.addSidebarItem({ id: VIEW, label: t("nav"), icon: "⇄", view: VIEW });
  gs.addTutorial({
    id: ctx.id, view: VIEW,
    steps: [
      { title: t("tut.1.t"), text: t("tut.1.x"), sel: ".ls-steps" },
      { title: t("tut.2.t"), text: t("tut.2.x"), sel: "#ls-url" },
      { title: t("tut.3.t"), text: t("tut.3.x") },
    ],
  });

  const platName = (pid) => state.platforms.find((p) => p.id === pid)?.name || pid;
  /** Dove e' gia' configurato un indirizzo (null se non lo e'). */
  const already = (target) => {
    if ((state.pc_stores || []).some((x) => x.url === target)) return t("pcStore");
    const hit = Object.entries(state.catalogs || {}).find(([, urls]) => (urls || []).includes(target));
    return hit ? platName(hit[0]) : null;
  };
  /** Console suggerita dal titolo del gruppo («Nintendo Switch», «PS2 ISO»...); PC se non si riconosce. */
  const guess = (name) => {
    const n = gs.fold(name);
    const hit = state.platforms.filter((p) => !p.pc).sort((a, b) => b.name.length - a.name.length)
      .find((p) => n.includes(gs.fold(p.name)) || new RegExp(`\\b${gs.fold(p.id)}\\b`).test(n));
    return hit ? hit.id : "windows";
  };
  const groupsPicked = () => (scan?.groups || []).map((g) => ({ ...g, links: g.links.filter((l) => picked.has(l.url)) })).filter((g) => g.links.length);

  async function loadState() {
    try { state = await gs.api(`/plugin-api/${VIEW}/state`); } catch (e) { gs.toast(t("err.state", { msg: e.message }), true); }
  }

  function stepper() {
    return `<ol class="ls-steps">${[1, 2, 3].map((n) => `<li class="${n === step ? "on" : n < step ? "done" : ""}">
      <span>${n < step ? "✓" : n}</span>${esc(t(`step.${n}`))}</li>`).join("")}</ol>`;
  }

  function step1(body) {
    body.insertAdjacentHTML("beforeend", `<section class="ls-card">
      <h2>${esc(t("s1.t"))}</h2><p class="muted">${esc(t("s1.x"))}</p>
      <form class="ls-form"><input class="field" id="ls-url" type="url" required placeholder="https://…" value="${esc(url)}" aria-label="${esc(t("s1.t"))}">
        <button class="btn primary" type="submit">${esc(t("s1.go"))}</button></form>
      <label class="chk"><input type="checkbox" id="ls-ext"${externalOnly ? " checked" : ""}> ${esc(t("s1.ext"))}</label></section>`);
    body.querySelector(".ls-form").onsubmit = async (e) => {
      e.preventDefault();
      url = body.querySelector("#ls-url").value.trim();
      externalOnly = body.querySelector("#ls-ext").checked;
      const b = e.target.querySelector("button");
      b.disabled = true; b.textContent = t("s1.reading");
      try {
        scan = await gs.api(`/plugin-api/${VIEW}/scan`, { body: { url, external_only: externalOnly } });
        await loadState();
        picked.clear(); dest.clear(); query = ""; showAll = false;
        if (!scan.groups.length) { gs.toast(t("s1.none"), true); b.disabled = false; b.textContent = t("s1.go"); return; }
        step = 2; draw();
      } catch (err) { gs.toast(err.message, true); b.disabled = false; b.textContent = t("s1.go"); }
    };
  }

  function step2(body) {
    const q = gs.fold(query);
    const match = (l) => !q || gs.fold(l.text).includes(q) || gs.fold(l.url).includes(q);
    let shown = 0;
    const groups = scan.groups.map((g) => ({ ...g, links: g.links.filter(match) })).filter((g) => g.links.length);
    const total = groups.reduce((a, g) => a + g.links.length, 0);
    const html = groups.map((g, gi) => {
      const links = showAll ? g.links : g.links.slice(0, Math.max(0, MAX_ROWS - shown));
      shown += links.length;
      if (!links.length) return "";
      const free = g.links.filter((l) => !already(l.url));
      const all = free.length && free.every((l) => picked.has(l.url));
      return `<div class="ls-group"><div class="ls-gh"><label class="chk"><input type="checkbox" data-group="${gi}" ${all ? "checked" : ""} ${free.length ? "" : "disabled"}>
          <b>${esc(g.name)}</b></label><span class="muted">${esc(t("links", { n: g.links.length }))}</span></div>
        ${links.map((l) => { const there = already(l.url); return `<label class="ls-row${there ? " there" : ""}">
          <input type="checkbox" data-url="${esc(l.url)}" ${there || picked.has(l.url) ? "checked" : ""} ${there ? "disabled" : ""}>
          <span class="ls-text"><b>${esc(l.text)}</b><span class="muted">${esc(l.host)}</span></span>
          ${there ? `<span class="badge">✓ ${esc(there)}</span>` : ""}</label>`; }).join("")}</div>`;
    }).join("");
    body.insertAdjacentHTML("beforeend", `<section class="ls-card">
      <div class="ls-head"><div><h2>${esc(t("s2.t"))}</h2><p class="muted">${esc(scan.title ? t("s2.from", { titolo: scan.title }) : url)}</p></div>
        <input class="field" id="ls-q" placeholder="${esc(t("filter"))}" value="${esc(query)}" aria-label="${esc(t("filter"))}"></div>
      <div class="ls-list">${html || `<p class="muted">${esc(t("noMatch"))}</p>`}</div>
      ${!showAll && total > shown ? `<p class="muted">${esc(t("shown", { n: shown, tot: total }))} <button class="btn" type="button" id="ls-more">${esc(t("showAll"))}</button></p>` : ""}
      <div class="ls-nav"><button class="btn" type="button" data-step="1">${esc(t("back"))}</button>
        <span class="muted">${esc(t("picked", { n: picked.size }))}</span>
        <button class="btn primary" type="button" data-step="3" ${picked.size ? "" : "disabled"}>${esc(t("next"))}</button></div></section>`);
    body.querySelector("#ls-q").oninput = (e) => { query = e.target.value; const pos = e.target.selectionStart; draw(); const i = el().querySelector("#ls-q"); i.focus(); i.setSelectionRange(pos, pos); };
    body.querySelector("#ls-more")?.addEventListener("click", () => { showAll = true; draw(); });
    body.onchange = (e) => {
      const g = e.target.dataset.group;
      if (g !== undefined) groups[+g].links.filter((l) => !already(l.url)).forEach((l) => (e.target.checked ? picked.add(l.url) : picked.delete(l.url)));
      else if (e.target.dataset.url) (e.target.checked ? picked.add(e.target.dataset.url) : picked.delete(e.target.dataset.url));
      draw();
    };
  }

  function step3(body) {
    const groups = groupsPicked();
    for (const g of groups) if (!dest.has(g.name)) dest.set(g.name, { platform: guess(g.name), kind: "direct" });
    const opts = (sel) => state.platforms.map((p) => `<option value="${esc(p.id)}" ${p.id === sel ? "selected" : ""}>${esc(p.pc ? t("pc") : p.name)}</option>`).join("");
    body.insertAdjacentHTML("beforeend", `<section class="ls-card"><h2>${esc(t("s3.t"))}</h2><p class="muted">${esc(t("s3.x"))}</p>
      <div class="ls-dest">${groups.map((g, i) => { const d = dest.get(g.name); return `<div class="ls-dest-row">
        <div><b>${esc(g.name)}</b><span class="muted">${esc(t("links", { n: g.links.length }))}</span></div>
        <select class="field" data-plat="${i}" aria-label="${esc(t("s3.console"))}">${opts(d.platform)}</select>
        <select class="field" data-kind="${i}" ${d.platform === "windows" ? "" : "hidden"} aria-label="${esc(t("s3.kind"))}">
          <option value="direct" ${d.kind === "direct" ? "selected" : ""}>${esc(t("kind.direct"))}</option>
          <option value="repack" ${d.kind === "repack" ? "selected" : ""}>${esc(t("kind.repack"))}</option></select></div>`; }).join("")}</div>
      <label class="chk"><input type="checkbox" id="ls-read" checked> ${esc(t("s3.read"))}</label>
      <div class="ls-nav"><button class="btn" type="button" data-step="2">${esc(t("back"))}</button><span></span>
        <button class="btn primary" type="button" id="ls-add">${esc(t("s3.add", { n: picked.size }))}</button></div></section>`);
    body.onchange = (e) => {
      const i = e.target.dataset.plat ?? e.target.dataset.kind;
      if (i === undefined) return;
      const d = dest.get(groups[+i].name);
      if (e.target.dataset.plat !== undefined) { d.platform = e.target.value; draw(); } else d.kind = e.target.value;
    };
    body.querySelector("#ls-add").onclick = async (e) => {
      e.target.disabled = true;
      const readNow = body.querySelector("#ls-read").checked;
      let ok = 0, fail = 0;
      const touched = new Set();
      for (const g of groups) {
        const d = dest.get(g.name);
        for (const l of g.links) {
          try {
            const r = await gs.api(`/plugin-api/${VIEW}/add`, { body: { url: l.url, platform: d.platform, kind: d.kind } });
            state = r.state || state;
            if (r.added) { ok++; touched.add(d.platform); }
          } catch { fail++; }
        }
      }
      if (ok) window.dispatchEvent(new CustomEvent("pz-catalogs-changed"));
      if (readNow) {
        for (const pid of touched) {
          try {
            if (pid === "windows") await gs.api("/api/pc-stores", { body: { stores: state.pc_stores, refresh: true } });
            else await gs.api(`/api/catalogs/${pid}`, { body: { urls: state.catalogs?.[pid] || [], refresh: true } });
          } catch (err) { gs.toast(`${platName(pid)}: ${err.message}`, true); }
        }
      }
      gs.toast(t(fail ? "done.partial" : "done", { n: ok, fail }), !!fail);
      picked.clear(); dest.clear(); step = 2; draw();
    };
  }

  let host = null;
  const el = () => host;
  function draw() {
    const body = gs.ui.page(host, { title: t("nav"), subtitle: t("subtitle"), tutorial: ctx.id });
    body.innerHTML = stepper();
    body.onclick = (e) => { const s = e.target.closest("[data-step]"); if (s && !s.disabled) { step = +s.dataset.step; draw(); } };
    if (step === 1 || !scan) step1(body); else if (step === 2) step2(body); else step3(body);
  }

  gs.registerView(VIEW, {
    title: t("nav"),
    async render(root) {
      host = root;
      await loadState();
      draw();
    },
  });
}
