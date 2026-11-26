// Il mio PC ce la fa?: semaforo nel dettaglio del gioco, tre indicatori (CPU, scheda video, RAM) e i consigli ripiegati.
const SEC = "pc-adatto";
const LIGHT = { ok: "good", impostazioni: "warn", insufficiente: "bad", sconosciuto: "muted" };

export default function (gs, ctx) {
  const { t, lang } = ctx;
  const cache = new Map();   // id gioco -> Promise del verdetto (le aperture successive non ri-chiedono nulla)
  const num = (n) => new Intl.NumberFormat(lang, { maximumFractionDigits: 1 }).format(n);

  gs.addTutorial({
    id: ctx.id, section: SEC,
    steps: [
      { title: t("tut.1.t"), text: t("tut.1.x"), sel: ".pa-head" },
      { title: t("tut.2.t"), text: t("tut.2.x"), sel: ".pa-meters" },
      { title: t("tut.3.t"), text: t("tut.3.x"), sel: ".pa-tips, .pa-box" },
    ],
  });

  function carica(id) {
    if (!cache.has(id)) {
      const p = gs.api(`/plugin-api/${SEC}/check/${encodeURIComponent(id)}`);
      p.catch(() => cache.delete(id));   // gli errori non restano in cache: al prossimo tentativo si riprova
      cache.set(id, p);
    }
    return cache.get(id);
  }

  /** Una barra: dove sei tu rispetto al minimo e al consigliato (livelli 1-5 per CPU e GPU, GB per la RAM). */
  function meter(m, hw) {
    const ram = m.part === "ram";
    const top = ram ? Math.max(m.rec || 0, m.min || 0, m.have, 8) * 1.25 : 5;
    const pos = (v) => Math.max(2, Math.min(100, (100 * v) / top));
    const val = (v) => (ram ? t("gb", { n: num(v) }) : t("tier", { n: v }));
    const name = m.part === "cpu" ? hw.cpu?.name : m.part === "gpu" ? hw.gpu?.name : "";
    return `<div class="pa-meter ${m.status || "none"}">
      <div class="pa-mh"><b>${gs.esc(t(`part.${m.part}`))}</b><span class="pa-st">${gs.esc(t(`st.${m.status || "none"}`))}</span></div>
      <div class="pa-track" role="img" aria-label="${gs.esc(t("aria", { tu: val(m.have), min: m.min != null ? val(m.min) : "—", rec: m.rec != null ? val(m.rec) : "—" }))}">
        <i style="--w:${pos(m.have)}%"></i>
        ${m.min != null ? `<em class="min" style="--x:${pos(m.min)}%" title="${gs.esc(t("min"))}"></em>` : ""}
        ${m.rec != null ? `<em class="rec" style="--x:${pos(m.rec)}%" title="${gs.esc(t("rec"))}"></em>` : ""}</div>
      <small class="muted">${gs.esc(name ? `${name} · ${val(m.have)}` : val(m.have))}${m.min != null ? ` · ${gs.esc(t("min"))} ${gs.esc(val(m.min))}` : ""}${m.rec != null ? ` · ${gs.esc(t("rec"))} ${gs.esc(val(m.rec))}` : ""}</small></div>`;
  }

  gs.addDetailSection({
    id: SEC,
    title: t("title"),
    async render(game) {
      let r;
      try { r = await carica(game.id); }
      catch (e) { return `<p class="muted">${gs.esc(t("error", { msg: e.message }))}</p>`; }
      const light = LIGHT[r.verdict] || "muted";
      const raw = r.requirements?.minimum?.raw || r.requirements?.recommended?.raw;
      return `<div class="pa-head pa-${light}"><span class="pa-light" aria-hidden="true"><i></i><i></i><i></i></span>
          <div><b>${gs.esc(t(`v.${r.verdict}`))}</b>${r.note ? `<small class="muted">${gs.esc(t(`note.${r.note}`))}</small>` : ""}</div></div>
        ${r.meters?.some((m) => m.status) ? `<div class="pa-meters">${r.meters.map((m) => meter(m, r.hw || {})).join("")}</div>` : ""}
        ${r.tips?.length ? `<details class="pa-tips" open><summary>${gs.esc(t("tips"))}</summary><ul>${r.tips.map((k) => `<li>${gs.esc(t(`tip.${k}`))}</li>`).join("")}</ul></details>` : ""}
        ${raw ? `<details class="pa-box"><summary>${gs.esc(t("raw"))}</summary><pre>${gs.esc(raw)}</pre></details>` : ""}`;
    },
  });
}
