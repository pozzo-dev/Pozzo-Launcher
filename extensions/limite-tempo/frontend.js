// Limite di tempo: quanto resta oggi, la settimana in un grafico e le regole (limiti, preavviso, chiusura) nella stessa pagina.
const VIEW = "limite-tempo";

export default function (gs, ctx) {
  const { t, lang } = ctx;
  const fmt = (s) => {
    const h = Math.floor(Math.abs(s) / 3600), m = Math.round((Math.abs(s) % 3600) / 60);
    return h ? t(m ? "dur.hm" : "dur.h", { h, m }) : t("dur.m", { m });
  };
  const giorno = (i) => new Date(2024, 0, 1 + i).toLocaleDateString(lang, { weekday: "short" });  // 1/1/2024 = lunedi'

  gs.addSidebarItem({ id: VIEW, label: t("nav"), icon: "◔", view: VIEW });
  gs.addTutorial({
    id: ctx.id, view: VIEW,
    steps: [
      { title: t("tut.1.t"), text: t("tut.1.x"), sel: ".lt-today" },
      { title: t("tut.2.t"), text: t("tut.2.x"), sel: ".lt-week" },
      { title: t("tut.3.t"), text: t("tut.3.x"), sel: ".lt-rules" },
    ],
  });

  gs.registerView(VIEW, {
    title: t("nav"),
    async render(el) {
      let d;
      try { d = await gs.api(`/plugin-api/${VIEW}/stato`); }
      catch (e) { el.innerHTML = ""; el.append(gs.ui.empty({ icon: "◔", title: t("error"), text: e.message })); return; }
      const draw = () => {
        const body = gs.ui.page(el, { title: t("nav"), subtitle: t("subtitle", { profilo: d.profilo }), tutorial: ctx.id });
        const lim = d.giorno_ore * 3600, pct = lim ? Math.min(100, (100 * d.oggi) / lim) : 0;
        const over = d.rimasto !== null && d.rimasto <= 0;
        const r = 52, c = 2 * Math.PI * r;
        const max = Math.max(lim, ...d.giorni, 3600);
        body.innerHTML = `<div class="lt-top">
          <section class="lt-card lt-today${over ? " over" : ""}">
            <div class="lt-ring"><svg viewBox="0 0 120 120" aria-hidden="true"><circle cx="60" cy="60" r="${r}" class="bg"/>
              <circle cx="60" cy="60" r="${r}" class="fg" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${(c * (1 - (lim ? pct : 0) / 100)).toFixed(1)}"/></svg>
              <span><b>${gs.esc(fmt(d.oggi))}</b><small>${gs.esc(t("today"))}</small></span></div>
            <div><h2>${gs.esc(d.rimasto === null ? t("nolimit") : over ? t("over", { tempo: fmt(d.rimasto) }) : t("left", { tempo: fmt(d.rimasto) }))}</h2>
              <p class="muted">${gs.esc(d.attivo ? (d.chiudi ? t("mode.close") : t("mode.warn")) : t("mode.off"))}</p>
              ${d.settimana_ore ? `<p class="muted">${gs.esc(t("weekUsed", { usato: fmt(d.settimana), limite: d.settimana_ore }))}</p>` : ""}</div>
          </section>
          <section class="lt-card lt-week"><h3>${gs.esc(t("week"))}</h3>
            <div class="lt-bars">${d.giorni.map((s, i) => `<div class="${i === d.oggi_idx ? "now" : ""}${lim && s >= lim ? " over" : ""}" title="${gs.esc(fmt(s))}">
              <i style="--h:${Math.round((100 * s) / max)}%"></i><span>${gs.esc(giorno(i))}</span></div>`).join("")}
              ${lim ? `<b class="lt-limit" style="--h:${Math.round((100 * lim) / max)}%"><em>${gs.esc(t("limitLine", { h: d.giorno_ore }))}</em></b>` : ""}</div></section></div>
          <form class="lt-card lt-rules"><h3>${gs.esc(t("rules"))}</h3>
            <label class="chk"><input type="checkbox" name="attivo" ${d.attivo ? "checked" : ""}> ${gs.esc(t("r.on"))}</label>
            <div class="row wrap lt-hours">
              <label>${gs.esc(t("r.day"))}<input class="field" type="number" name="giorno_ore" min="0" max="24" step="0.5" value="${d.giorno_ore || ""}" placeholder="${gs.esc(t("r.none"))}"></label>
              <label>${gs.esc(t("r.week"))}<input class="field" type="number" name="settimana_ore" min="0" max="168" step="0.5" value="${d.settimana_ore || ""}" placeholder="${gs.esc(t("r.none"))}"></label></div>
            <label class="chk"><input type="checkbox" name="preavviso" ${d.preavviso ? "checked" : ""}> ${gs.esc(t("r.soon"))}</label>
            <fieldset class="lt-end"><legend>${gs.esc(t("r.end"))}</legend>
              <label class="chk"><input type="radio" name="chiudi" value="0" ${d.chiudi ? "" : "checked"}> ${gs.esc(t("r.warn"))}</label>
              <label class="chk"><input type="radio" name="chiudi" value="1" ${d.chiudi ? "checked" : ""}> ${gs.esc(t("r.close"))}</label></fieldset>
            <p class="muted small">${gs.esc(t("r.note"))}</p>
            <button class="btn primary" type="submit">${gs.esc(t("save"))}</button></form>`;
        body.querySelector("form").onsubmit = async (e) => {
          e.preventDefault();
          const f = new FormData(e.target);
          try {
            d = await gs.api(`/plugin-api/${VIEW}/salva`, { body: { attivo: f.has("attivo"), giorno_ore: f.get("giorno_ore") || 0,
              settimana_ore: f.get("settimana_ore") || 0, preavviso: f.has("preavviso"), chiudi: f.get("chiudi") === "1" } });
            gs.toast(t("saved"));
            draw();
          } catch (err) { gs.toast(err.message, true); }
        };
      };
      draw();
    },
  });
}
