// Store Minerva + Switch: «Importa store» riempie lo «Store online» di ogni console con gli archivi di minerva-archive.org
// (elencati da r-roms) e gli store preimpostati Switch, Switch 2, PS4 e PS5; poi una scheda per console con «Leggi».
const VIEW = "minerva";
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

export default function (gs, ctx) {
  const { t, lang } = ctx;

  gs.addSidebarItem({ id: VIEW, label: t("nav"), icon: "⌂", view: VIEW });
  gs.addTutorial({
    id: ctx.id, view: VIEW,
    steps: [
      { title: t("tut.1.t"), text: t("tut.1.x") },
      { title: t("tut.2.t"), text: t("tut.2.x"), sel: "#mv-go" },
      { title: t("tut.3.t"), text: t("tut.3.x"), sel: ".mv-grid, .ext-empty" },
    ],
  });

  gs.registerView(VIEW, {
    title: t("nav"),
    async render(el) {
      let consoles = [], job = { status: "idle", log: [] }, reading = null;
      const actions = `<button class="btn primary" type="button" id="mv-go">${gs.esc(t("import"))}</button>`
        + `<button class="btn" type="button" id="mv-all" hidden></button>`;
      const body = gs.ui.page(el, { title: t("nav"), subtitle: t("subtitle"), actions, tutorial: ctx.id });
      body.innerHTML = `<div class="mv-status" hidden></div><div class="mv-list"></div>
        <details class="mv-log"><summary>${gs.esc(t("log"))}</summary><pre></pre></details>`;
      const btn = el.querySelector("#mv-go"), all = el.querySelector("#mv-all");
      const status = body.querySelector(".mv-status"), list = body.querySelector(".mv-list"), pre = body.querySelector(".mv-log pre");

      const showJob = (j) => {
        job = j;
        pre.textContent = (j.log || []).slice(-40).join("\n");
        body.querySelector(".mv-log").hidden = !(j.log || []).length;
        btn.disabled = j.status === "running";
        btn.textContent = j.status === "running" ? t("importing") : t("import");
      };
      const showReading = () => {
        status.hidden = !reading;
        if (reading) status.innerHTML = `<span>${gs.esc(t("reading", { fatti: reading.done, totale: reading.total }))}</span>`
          + `<div class="mv-bar"><i style="--w:${reading.total ? Math.round((100 * reading.done) / reading.total) : 0}%"></i></div>`;
      };

      const drawList = async () => {
        try { consoles = (await gs.api(`/plugin-api/${VIEW}/console`)).consoles; } catch { return; }
        const unread = consoles.flatMap((c) => c.stores.filter((s) => !s.games).map((s) => s.id));
        all.hidden = !unread.length;
        all.textContent = t("readAll", { n: unread.length });
        list.innerHTML = "";
        if (!consoles.length) {
          list.append(gs.ui.empty({ icon: "⌂", title: t("empty.t"), text: t("empty.x"), action: { label: t("import"), run: () => btn.click() } }));
          return;
        }
        list.innerHTML = `<div class="mv-grid">${consoles.map((c) => `<article class="mv-card${c.games ? "" : " new"}">
            <img class="mv-ico" src="/icons/platform/${encodeURIComponent(c.platform)}" alt="" data-onerr="remove">
            <div class="mv-info"><b>${gs.esc(c.name)}</b>
              <span class="muted">${gs.esc(c.games ? t("games", { n: c.games.toLocaleString(lang) }) : t("notRead"))}</span>
              <small class="muted">${gs.esc(t("stores", { n: c.stores.length }))}${c.unread && c.games ? ` · ${gs.esc(t("unread", { n: c.unread }))}` : ""}</small></div>
            <button class="btn${c.games ? "" : " primary"}" type="button" data-read="${gs.esc(c.platform)}" ${reading ? "disabled" : ""}>${gs.esc(c.games ? t("refresh") : t("read"))}</button>
          </article>`).join("")}</div>`;
      };

      // lettura: la coda degli store dell'app (rispetta il limite «in parallelo» e ricostruisce la libreria una volta)
      const followRead = async () => {
        let s;
        do {
          await wait(1500);
          try { s = (await gs.api("/api/store-refresh")).job; } catch { reading = null; break; }
          reading = s.status === "running" ? s : null;
          if (el.isConnected) showReading();
        } while (s.status === "running");
        gs.toast(t("readDone"));
        gs.refresh();
        if (el.isConnected) { showReading(); drawList(); }
      };
      const read = async (ids) => {
        if (!ids.length) return;
        try { await gs.api("/api/store-refresh/run", { body: { ids } }); } catch (e) { return gs.toast(e.message, true); }
        reading = { done: 0, total: ids.length };
        showReading(); drawList();
        followRead();
      };
      list.onclick = (e) => {
        const b = e.target.closest("[data-read]");
        const c = b && consoles.find((x) => x.platform === b.dataset.read);
        if (c) read(c.stores.map((s) => s.id));
      };
      all.onclick = () => read(consoles.flatMap((c) => c.stores.filter((s) => !s.games).map((s) => s.id)));

      const follow = async () => {
        let j;
        do { await wait(1000); j = await gs.api(`/plugin-api/${VIEW}/stato`); if (el.isConnected) showJob(j); }
        while (j.status === "running");
        if (j.status !== "done") return gs.toast(t("importFail"), true);
        const count = (o) => Object.values(o || {}).reduce((a, v) => a + (v && v.length ? v.length : Number(v) || 0), 0);
        const added = count(j.added), unread = count(j.todo);  // added: {console: n}, todo: {console: [url]}
        // dirlo anche quando non cambia nulla: prima sembrava che il pulsante non facesse niente
        gs.toast(added ? t("added", { n: added }) : unread ? t("noneNewUnread", { n: unread }) : t("noneNew"));
        window.dispatchEvent(new CustomEvent("pz-catalogs-changed"));
        if (el.isConnected) drawList();
      };
      btn.onclick = async () => { showJob(await gs.api(`/plugin-api/${VIEW}/importa`, { body: {} })); follow(); };

      showJob(await gs.api(`/plugin-api/${VIEW}/stato`));
      if (job.status === "running") follow();
      const rj = (await gs.api("/api/store-refresh").catch(() => ({ job: {} }))).job;
      if (rj.status === "running") { reading = rj; followRead(); }
      showReading();
      drawList();
    },
  });
}
