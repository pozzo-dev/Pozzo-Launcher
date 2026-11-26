// Obiettivi: sfide proposte dalla tua libreria (un clic per accettarle), obiettivi ad anello, serie di giorni e distintivi.
const VIEW = "obiettivi";

export default function (gs, ctx) {
  const { t, lang } = ctx;
  const num = (n) => new Intl.NumberFormat(lang, { maximumFractionDigits: 1 }).format(n || 0);
  const consoleName = (id) => gs.library()?.plats?.get?.(id)?.name || id;

  gs.addSidebarItem({ id: VIEW, label: t("nav"), icon: "◎", view: VIEW });
  gs.addTutorial({
    id: ctx.id, view: VIEW,
    steps: [
      { title: t("tut.1.t"), text: t("tut.1.x") },
      { title: t("tut.2.t"), text: t("tut.2.x"), sel: ".ob-offers" },
      { title: t("tut.3.t"), text: t("tut.3.x"), sel: ".ob-mine" },
      { title: t("tut.4.t"), text: t("tut.4.x"), sel: ".ob-streak" },
    ],
  });

  /** Testo di un obiettivo o di una proposta, nella lingua dell'interfaccia. */
  const label = (o) => (o.tipo === "finisci" ? t("goal.finisci", { titolo: o.titolo || o.gioco })
    : o.tipo === "prova" ? t("goal.prova", { console: consoleName(o.console) })
      : t(`goal.${o.tipo}`, { n: o.n, periodo: t(`period.${o.periodo}`) }));

  /** Anello di avanzamento (SVG): pct da 0 a 100. */
  const ring = (pct, inner) => {
    const r = 26, c = 2 * Math.PI * r;
    return `<div class="ob-ring"><svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="${r}" class="bg"/>`
      + `<circle cx="32" cy="32" r="${r}" class="fg" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${(c * (1 - pct / 100)).toFixed(1)}"/></svg>`
      + `<span>${inner}</span></div>`;
  };

  gs.registerView(VIEW, {
    title: t("nav"),
    async render(el) {
      let d;
      const plain = () => d.obiettivi.map(({ id, tipo, n, periodo, gioco, console }) => ({ id, tipo, n, periodo, gioco, console }));
      const save = async (obiettivi) => {
        try { d = await gs.api(`/plugin-api/${VIEW}/salva`, { body: { obiettivi } }); draw(); } catch (e) { gs.toast(e.message, true); }
      };

      const draw = () => {
        const body = gs.ui.page(el, { title: t("nav"), subtitle: t("subtitle"), tutorial: ctx.id });
        const s = d.serie;
        body.innerHTML = `<section class="ob-streak${s.attuale ? " on" : ""}"><b>${s.attuale}</b>
            <div><strong>${gs.esc(t(s.attuale === 1 ? "streak.one" : "streak.many", { n: s.attuale }))}</strong>
            <span class="muted">${gs.esc(t(s.attuale ? "streak.keep" : "streak.start"))} · ${gs.esc(t("streak.best", { n: s.migliore }))}</span></div></section>
          ${d.proposte.length ? `<section class="shelf-section ob-offers"><h2>${gs.esc(t("offers"))}</h2><div class="ob-grid">${d.proposte.map((p, i) => `
            <article class="ob-card offer">${p.id_gioco ? `<img class="ob-cover" src="${gs.ui.cover(p.id_gioco, 160)}" alt="" data-onerr="remove">` : `<span class="ob-glyph" aria-hidden="true">${p.tipo === "prova" ? "◇" : "◎"}</span>`}
              <div><b>${gs.esc(label(p))}</b><span class="muted">${gs.esc(t(`why.${p.tipo}`, { n: p.giochi || 0 }))}</span></div>
              <button class="btn primary" type="button" data-accept="${i}">${gs.esc(t("accept"))}</button></article>`).join("")}</div></section>` : ""}
          <section class="shelf-section ob-mine"><h2>${gs.esc(t("mine"))}</h2>
            ${d.obiettivi.length ? `<div class="ob-grid">${d.obiettivi.map((o) => {
              const pct = Math.min(100, Math.round((100 * o.valore) / o.n));
              const inner = o.fatto ? "✓" : o.tipo === "finisci" || o.tipo === "prova" ? "…" : `${pct}%`;
              return `<article class="ob-card${o.fatto ? " done" : ""}">${ring(o.fatto ? 100 : pct, inner)}
                <div><b>${gs.esc(label(o))}</b><span class="muted">${gs.esc(o.fatto ? t("done") : o.tipo === "finisci" || o.tipo === "prova" ? t("open") : `${num(o.valore)} / ${num(o.n)}`)}</span></div>
                <button class="icon-btn ob-del" type="button" data-del="${gs.esc(o.id)}" title="${gs.esc(t("delete"))}" aria-label="${gs.esc(t("delete"))}">✕</button></article>`;
            }).join("")}</div>` : `<p class="muted">${gs.esc(t("mine.empty"))}</p>`}
            <details class="ob-custom"><summary>${gs.esc(t("custom"))}</summary>
              <form class="row wrap ob-form">
                <select class="field" name="tipo" aria-label="${gs.esc(t("custom.what"))}">${["finiti", "ore", "giorni"].map((k) => `<option value="${k}">${gs.esc(t(`type.${k}`))}</option>`).join("")}</select>
                <input class="field" name="n" type="number" min="1" max="10000" value="3" required aria-label="${gs.esc(t("custom.n"))}">
                <select class="field" name="periodo" aria-label="${gs.esc(t("custom.when"))}">${["settimana", "mese", "anno"].map((k) => `<option value="${k}">${gs.esc(t(`period.${k}`))}</option>`).join("")}</select>
                <button class="btn primary" type="submit">${gs.esc(t("add"))}</button></form></details></section>
          <section class="shelf-section"><h2>${gs.esc(t("badges"))}</h2><div class="ob-badges">${d.distintivi.map((b) => `
            <div class="ob-badge${b.ottenuto ? " on" : ""}">${ring(Math.round((100 * b.valore) / b.soglia), b.ottenuto ? "★" : "")}
              <b>${gs.esc(t(`badge.${b.id}.t`))}</b><small class="muted">${gs.esc(b.ottenuto ? t(`badge.${b.id}.x`) : `${num(b.valore)} / ${num(b.soglia)}`)}</small></div>`).join("")}</div></section>`;
      };

      el.onsubmit = (e) => {
        e.preventDefault();
        const f = new FormData(e.target);
        save([...plain(), { tipo: f.get("tipo"), n: f.get("n"), periodo: f.get("periodo") }]);
      };
      el.onclick = (e) => {
        const acc = e.target.closest("[data-accept]");
        if (acc) { const p = d.proposte[+acc.dataset.accept]; acc.disabled = true; return save([...plain(), p]); }
        const del = e.target.closest("[data-del]");
        if (del) save(plain().filter((o) => o.id !== del.dataset.del));
      };
      el.innerHTML = `<p class="muted">…</p>`;
      try { d = await gs.api(`/plugin-api/${VIEW}/stato`); draw(); } catch (e) { el.innerHTML = ""; el.append(gs.ui.empty({ icon: "◎", title: t("error"), text: e.message })); }
    },
  });
}
