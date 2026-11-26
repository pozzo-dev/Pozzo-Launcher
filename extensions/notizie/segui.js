// Seguiti: segui un gioco, badge di novità sulle tessere, sezione «Novità sul gioco», vista «Seguiti» e scaffale in home.

const API = "/plugin-api/notizie";

// Solo link http/https: qualunque altro schema (javascript:, data:) viene scartato.
export function safeHref(u) {
  try { const x = new URL(String(u || "")); return /^https?:$/.test(x.protocol) ? x.href : ""; } catch { return ""; }
}

// Totale delle notizie non lette su tutti i giochi seguiti.
export function contaNonLetti(games) {
  let n = 0;
  for (const g of games || []) n += Math.max(0, +g.unread || 0);
  return n;
}

// id gioco -> notizie non lette (solo i giochi che ne hanno).
export function nonLettiPerGioco(games) {
  const m = new Map();
  for (const g of games || []) if (+g.unread > 0) m.set(String(g.id), +g.unread); // il backend salva gli id come stringhe
  return m;
}

export default function (gs, ctx) {
  const { t, lang } = ctx;
  let games = [];                       // ultima risposta di follows/news
  let unread = new Map();               // id -> non letti, per le tessere
  const followed = (id) => games.some((g) => String(g.id) === String(id));
  const el = (tag, cls, ...kids) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    n.append(...kids.filter((k) => k != null));
    return n;
  };
  const fade = (node) => {
    if (!matchMedia("(prefers-reduced-motion: reduce)").matches)
      node.animate?.([{ opacity: 0, transform: "translateY(4px)" }, { opacity: 1, transform: "none" }], { duration: 180, easing: "ease-out" });
    return node;
  };
  const data = (s) => { const d = new Date(s); return isNaN(d) ? "" : d.toLocaleDateString(lang, { day: "numeric", month: "short", year: "numeric" }); };

  // Ricarica i seguiti e aggiorna badge e voce della barra laterale (anche se la richiesta fallisce).
  // Ritorna i giochi, o null se la richiesta fallisce.
  async function refresh() {
    let ok = true;
    try { games = (await gs.api(`${API}/follows/news`)).games || []; } catch { ok = false; }
    unread = nonLettiPerGioco(games);
    const n = contaNonLetti(games);
    gs.addSidebarItem({ id: "seguiti", label: t("follow.nav") + (n ? ` · ${n}` : ""), icon: "◉", view: "seguiti" });
    return ok ? games : null;
  }

  // Elenco di notizie: etichetta Patch/DLC, titolo con link esterno, data.
  const lista = (items) => el("ul", "nz-mini", ...items.map((it) => {
    const href = safeHref(it.link);
    const titolo = href ? Object.assign(el("a", "", it.title || t("untitled")), { href, target: "_blank", rel: "noopener noreferrer" }) : it.title || t("untitled");
    return el("li", "", ["patch", "dlc"].includes(it.kind) ? el("span", "chip nz-tag", t(`kind.${it.kind}`)) : null,
      el("span", "", titolo), it.unread ? el("b", "nz-new", t("follow.new")) : null, el("span", "muted small", data(it.published)));
  }));

  async function toggle(g, on) {
    try {
      // il dettaglio gioco non ha steam_appid: si ricava da key/pagina Steam, cosi' arrivano le news Steam
      const appid = g.steam_appid || (/(?:steam:|steampowered\.com\/app\/)(\d+)/.exec(`${g.key || ""} ${g.page || ""}`) || [])[1];
      if (on) await gs.api(`${API}/follow`, { body: { id: g.id, title: g.title, steam_appid: appid } });
      else await gs.api(`${API}/unfollow`, { body: { id: g.id } });
    } catch (e) { return gs.toast(e.message, true); }
    await refresh();
    gs.toast(t(on ? "follow.on" : "follow.off", { titolo: g.title }));
    if (String(gs.currentGame()?.id) === String(g.id)) gs.openGame(Number(g.id)); // ridisegna il dettaglio con il pulsante giusto
  }

  // Due voci con «when» complementari: il pulsante cambia in base allo stato già noto.
  gs.addGameAction({ id: "segui", label: t("follow.btn"), icon: "◉", when: (g) => !followed(g.id), run: (g) => toggle(g, true) });
  gs.addGameAction({ id: "smetti-di-seguire", label: t("follow.stop"), icon: "○", when: (g) => followed(g.id), run: (g) => toggle(g, false) });

  gs.addTileBadge({ id: "segui-novita", render: (g) => (unread.get(String(g.id)) ? t("follow.badge", { n: unread.get(String(g.id)) }) : null) });

  // scaffale in home: i giochi seguiti con novita' non lette
  gs.addShelf({
    id: "notizie-seguiti", title: t("follow.shelf"), why: t("follow.shelfWhy"),
    async games(lib) {
      await refresh();
      const byId = new Map((lib?.games || []).map((g) => [String(g.id), g]));
      return games.filter((g) => +g.unread > 0).map((g) => byId.get(String(g.id))).filter(Boolean);
    },
  });

  gs.addDetailSection({
    id: "novita-gioco",
    title: t("follow.section"),
    async render(g) {
      const all = await refresh();
      if (all === null) return el("p", "muted small", t("follow.unavailable"));
      const f = all.find((x) => String(x.id) === String(g.id));
      if (!f) return el("p", "muted small", t("follow.hint"));
      if (!f.items.length) return el("p", "muted small", t("follow.none"));
      if (f.unread > 0) gs.api(`${API}/follows/seen`, { body: { id: g.id } }).then(refresh).catch(() => {}); // aperta = letta
      return fade(lista(f.items));
    },
  });

  gs.registerView("seguiti", {
    title: t("follow.nav"),
    async render(root) {
      const body = gs.ui.page(root, { title: t("follow.nav"), subtitle: t("follow.subtitle") });
      body.append(el("p", "muted", t("follow.loading")));
      const all = await refresh();
      if (all === null) return body.replaceChildren(gs.ui.empty({ icon: "◉", title: t("follow.unavailable") }));
      if (!all.length) return body.replaceChildren(gs.ui.empty({ icon: "◉", title: t("follow.empty.t"), text: t("follow.empty.x") }));
      const byId = new Map((gs.library()?.games || []).map((g) => [String(g.id), g]));
      body.replaceChildren(...all.map((g) => {
        const open = el("button", "btn", t("follow.open")); open.type = "button"; open.onclick = () => gs.openGame(Number(g.id));
        const lib = byId.get(String(g.id));
        const cover = lib ? Object.assign(el("img", "nz-cover"), { src: gs.ui.cover(lib.id, 160), alt: "", loading: "lazy" }) : null;
        if (cover) cover.dataset.onerr = "remove";
        return fade(el("section", "nz-follow", cover, el("div", "nz-follow-body",
          el("div", "nz-follow-head", el("h3", "", g.title), g.unread ? el("span", "badge ext", t("follow.unread", { n: g.unread })) : null, open),
          g.items.length ? lista(g.items.slice(0, 5)) : el("p", "muted small", t("follow.none")))));
      }));
    },
  });

  refresh();
  gs.on("gameOpened", () => refresh());
}
