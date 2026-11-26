// Anniversari retro: badge sui festeggiati di oggi, scaffale in home e pagina con oggi e i prossimi 30 giorni.

export default function (gs, ctx) {
  const { t, lang } = ctx;
  let oggi = { giochi: [] };
  const anni = new Map();   // id gioco -> anni compiuti oggi

  async function load() {
    try {
      oggi = await gs.api("/plugin-api/anniversari/oggi");
      const prima = anni.size;
      anni.clear();
      for (const g of oggi.giochi) anni.set(g.id, g.anni);
      if (prima || anni.size) gs.redraw?.();   // i badge arrivano dopo la prima schermata: si ridisegnano le copertine
    } catch { /* senza backend niente badge */ }
  }

  // giochi della libreria in memoria (copertina, console) a partire dalle voci del backend
  const games = (list) => {
    const byId = new Map((gs.library()?.games || []).map((g) => [g.id, g]));
    return list.map((x) => ({ x, g: byId.get(x.id) || { id: x.id, title: x.titolo, platform: x.piattaforma } }));
  };
  const card = ({ x, g }) => `<div class="ann-item${x.tondo ? " round" : ""}">${gs.ui.gameCard(g)}`
    + `<span class="ann-years"${x.tondo ? ` title="${gs.esc(t("round"))}"` : ""}>${gs.esc(t("years", { n: x.anni }))}</span></div>`;

  gs.addTileBadge({ id: "anniversario", render: (g) => (anni.has(g.id) ? t("badge", { n: anni.get(g.id) }) : null) });
  gs.addSidebarItem({ id: "anniversari", label: t("nav"), icon: "◷", view: "anniversari" });
  gs.addShelf({
    id: "anniversari", title: t("shelf"), why: t("shelfWhy"),
    async games(lib) {
      const r = await gs.api("/plugin-api/anniversari/prossimi?giorni=7");
      const byId = new Map((lib?.games || []).map((g) => [g.id, g]));
      return r.giorni.flatMap((d) => d.giochi).map((x) => byId.get(x.id)).filter(Boolean);
    },
  });
  gs.addTutorial({
    id: ctx.id, view: "anniversari",
    steps: [
      { title: t("tut.1.t"), text: t("tut.1.x") },
      { title: t("tut.2.t"), text: t("tut.2.x"), sel: ".ann-today" },
      { title: t("tut.3.t"), text: t("tut.3.x"), sel: ".ann-next" },
      { title: t("tut.4.t"), text: t("tut.4.x") },
    ],
  });
  gs.on("libraryLoaded", load);   // anche a mezzanotte passata, alla prima ricarica
  load();

  gs.registerView("anniversari", {
    title: t("title"),
    async render(el) {
      const data = new Date().toLocaleDateString(lang, { weekday: "long", day: "numeric", month: "long" });
      const body = gs.ui.page(el, { title: t("title"), subtitle: t("subtitle", { data }), tutorial: ctx.id });
      body.innerHTML = `<p class="muted">…</p>`;
      const [, r] = await Promise.all([load(), gs.api("/plugin-api/anniversari/prossimi?giorni=31")]);
      const dopo = r.giorni.filter((d) => d.tra > 0);
      body.innerHTML = "";
      if (!oggi.giochi.length && !dopo.length) {
        body.append(gs.ui.empty({ icon: "◷", title: t("empty.t"), text: t("empty.x") }));
        return;
      }
      const today = document.createElement("section");
      today.className = "shelf-section ann-today";
      today.innerHTML = oggi.giochi.length
        ? `<h2>${gs.esc(t("today"))}</h2><div class="shelf-lane ann-lane">${games(oggi.giochi.map((x) => ({ ...x, tondo: x.anni % 5 === 0 }))).map(card).join("")}</div>`
        : `<h2>${gs.esc(t("today"))}</h2><p class="muted">${gs.esc(t("todayNone"))}</p>`;
      const next = document.createElement("section");
      next.className = "ann-next";
      next.innerHTML = `<h2>${gs.esc(t("next"))}</h2>` + dopo.map((d) => {
        const quando = new Date(d.data + "T12:00:00").toLocaleDateString(lang, { weekday: "long", day: "numeric", month: "long" });
        const resto = d.totale - d.giochi.length;
        return `<div class="ann-day"><div class="ann-date"><b>${gs.esc(quando)}</b>`
          + `<span class="muted">${gs.esc(d.tra === 1 ? t("tomorrow") : t("inDays", { n: d.tra }))}</span></div>`
          + `<div class="shelf-lane ann-lane">${games(d.giochi).map(card).join("")}`
          + `${resto > 0 ? `<span class="ann-more muted">${gs.esc(t("more", { n: resto }))}</span>` : ""}</div></div>`;
      }).join("");
      body.append(today, ...(dopo.length ? [next] : []));
    },
  });
}
