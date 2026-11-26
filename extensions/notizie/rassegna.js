// Rassegna: cosa è successo nel mondo console nella settimana. Prima i tuoi giochi, poi una sezione per casa.

// Solo link http/https: qualunque altro schema viene scartato.
export function safeHref(u) {
  try { const x = new URL(String(u || "")); return /^https?:$/.test(x.protocol) ? x.href : ""; } catch { return ""; }
}

// Conteggi per il riepilogo: notizie per casa, notizie per i tuoi giochi, case con almeno una notizia.
export function riepilogo(digest) {
  const casa = Object.values(digest?.per_casa || {});
  return {
    notizie: casa.reduce((n, items) => n + (items?.length || 0), 0),
    mine: digest?.mine?.length || 0,
    case: casa.filter((items) => items?.length).length,
  };
}

// Sezioni per casa con al massimo `max` notizie, senza le case vuote.
export function sezioniCase(perCasa, max = 3) {
  return Object.entries(perCasa || {})
    .filter(([, items]) => items?.length)
    .map(([casa, items]) => [casa, items.slice(0, max)]);
}

export default function (gs, ctx) {
  const { t, lang } = ctx;
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
  const giorno = (s, opt = { day: "numeric", month: "short" }) => { const d = new Date(s); return isNaN(d) ? "" : d.toLocaleDateString(lang, opt); };
  const intervallo = (a, b) => (a && b ? `${giorno(a)} – ${giorno(b, { day: "numeric", month: "short", year: "numeric" })}` : "");

  const lista = (items) => el("ul", "nz-mini", ...items.map((it) => {
    const href = safeHref(it.link);
    const titolo = href ? Object.assign(el("a", "", it.title || t("untitled")), { href, target: "_blank", rel: "noopener noreferrer" }) : it.title || t("untitled");
    return el("li", "", ["patch", "dlc"].includes(it.kind) ? el("span", "chip nz-tag", t(`kind.${it.kind}`)) : null,
      el("span", "", titolo), el("span", "muted small", giorno(it.published)));
  }));
  const sezione = (titolo, body) => el("section", "shelf-section", el("h2", "", titolo), body);

  gs.addSidebarItem({ id: "rassegna", label: t("digest.nav"), icon: "▦", view: "rassegna" });

  gs.registerView("rassegna", {
    title: t("digest.nav"),
    async render(root) {
      let d;
      const body = gs.ui.page(root, { title: t("digest.nav"), subtitle: t("digest.title") });
      body.append(el("p", "muted", t("digest.loading")));
      try { d = await gs.api("/plugin-api/notizie/digest"); } catch (e) {
        return body.replaceChildren(gs.ui.empty({ icon: "▦", title: t("digest.error"), text: e.message }));
      }
      const r = riepilogo(d);
      const head = el("div", "nz-digest-head", el("b", "", intervallo(d.week_start, d.week_end)),
        el("span", "muted", t("digest.counts", { notizie: r.notizie, case: r.case, mine: r.mine })));
      if (!r.notizie && !r.mine) return body.replaceChildren(head, gs.ui.empty({ icon: "▦", title: t("digest.empty.t"), text: t("digest.empty.x") }));
      const parti = [head];
      if (r.mine) parti.push(sezione(t("digest.mine"), lista(d.mine)));
      for (const [casa, items] of sezioniCase(d.per_casa, 3)) parti.push(sezione(casa, lista(items)));
      body.replaceChildren(...parti.map((p) => fade(p)));
    },
  });
}
