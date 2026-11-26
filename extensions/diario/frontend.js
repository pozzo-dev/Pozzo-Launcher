// Diario di gioco: la storia di un gioco giorno per giorno, con partite, note, schermate e copie dei salvataggi.
// La nota semplice del gioco resta nella scheda dell'app: qui c'e' la cronologia.
export default function (gs, ctx) {
  const { t, lang } = ctx;
  const SEC = "diario";

  const dur = (s) => {
    const h = Math.floor(s / 3600), m = Math.round((s % 3600) / 60);
    return h ? t("dur.hm", { h, m }) : t("dur.m", { m: Math.max(1, m) });
  };
  const ora = (ts) => new Date(ts * 1000).toLocaleTimeString(lang, { hour: "2-digit", minute: "2-digit" });
  const giorno = (ts) => {
    const d = new Date(ts * 1000), oggi = new Date();
    const diff = Math.round((new Date(oggi.getFullYear(), oggi.getMonth(), oggi.getDate()) - new Date(d.getFullYear(), d.getMonth(), d.getDate())) / 86400000);
    return diff === 0 ? t("today") : diff === 1 ? t("yesterday")
      : d.toLocaleDateString(lang, { weekday: "long", day: "numeric", month: "long", ...(d.getFullYear() === oggi.getFullYear() ? {} : { year: "numeric" }) });
  };
  const dayKey = (ts) => new Date(ts * 1000).toDateString();

  gs.addTutorial({
    id: ctx.id, section: SEC,
    steps: [
      { title: t("tut.1.t"), text: t("tut.1.x"), sel: ".di-box" },
      { title: t("tut.2.t"), text: t("tut.2.x"), sel: ".di-form" },
      { title: t("tut.3.t"), text: t("tut.3.x"), sel: ".di-days" },
    ],
  });

  function riga(r) {
    if (r.tipo === "nota") return `<li class="di-item di-note"><span class="di-ico" aria-hidden="true">✎</span><div>
        <span class="di-time">${ora(r.t)}</span><button class="icon-btn di-del" type="button" data-t="${r.t}" title="${gs.esc(t("delete"))}" aria-label="${gs.esc(t("delete"))}">✕</button>
        <p>${gs.esc(r.testo).replace(/\n/g, "<br>")}</p></div></li>`;
    if (r.tipo === "partita") return `<li class="di-item"><span class="di-ico" aria-hidden="true">▶</span><div>
        <span class="di-time">${ora(r.t)}</span> ${gs.esc(t("played", { durata: dur(r.secondi) }))}</div></li>`;
    if (r.tipo === "salvataggio") return `<li class="di-item"><span class="di-ico" aria-hidden="true">⛁</span><div>
        <span class="di-time">${ora(r.t)}</span> ${gs.esc(t("save"))}${r.note ? ` · <span class="muted">${gs.esc(r.note)}</span>` : ""}</div></li>`;
    return `<li class="di-item"><span class="di-ico" aria-hidden="true">▣</span><div><span class="di-time">${ora(r.t)}</span>
        ${gs.esc(t("shots", { n: r.shots.length }))}<div class="di-shots">${r.shots.map((s) =>
          `<a href="${gs.esc(s.url)}" target="_blank" rel="noopener"><img src="${gs.esc(s.url)}?w=320" alt="" loading="lazy" data-onerr="remove"></a>`).join("")}</div></div></li>`;
  }

  gs.addDetailSection({
    id: SEC,
    title: t("title"),
    async render(game) {
      const box = document.createElement("div");
      box.className = "di-box";
      const draw = async () => {
        let d;
        try { d = await gs.api(`/plugin-api/diario/gioco?id=${game.id}`); } catch (e) { box.textContent = e.message; return; }
        // schermate e salvataggi vengono dall'app: se mancano il diario resta con partite e note
        const [sh, sv] = await Promise.all([gs.api(`/api/game/${game.id}/shots`).catch(() => ({})), gs.api(`/api/game/${game.id}/saves`).catch(() => ({}))]);
        const righe = [
          ...d.voci.map((v) => ({ tipo: "nota", t: v.t, testo: v.testo })),
          ...d.sessioni.map((s) => ({ tipo: "partita", t: s.inizio, secondi: s.secondi })),
          ...(sv.items || []).filter((b) => b.time).map((b) => ({ tipo: "salvataggio", t: b.time, note: b.note })),
        ];
        // le schermate dello stesso giorno stanno in una riga sola
        const perGiorno = new Map();
        for (const s of sh.shots || []) {
          const k = dayKey(s.taken);
          if (!perGiorno.has(k)) righe.push(perGiorno.set(k, { tipo: "schermate", t: s.taken, shots: [] }).get(k));
          perGiorno.get(k).shots.push(s);
        }
        righe.sort((a, b) => b.t - a.t);
        const giorni = [];
        for (const r of righe) {
          if (giorni.at(-1)?.k !== dayKey(r.t)) giorni.push({ k: dayKey(r.t), t: r.t, righe: [] });
          giorni.at(-1).righe.push(r);
        }
        box.innerHTML = `<div class="di-sum">${d.partite
            ? `<span><b>${gs.esc(dur(d.totale))}</b> ${gs.esc(t("sum.total"))}</span><span><b>${d.partite}</b> ${gs.esc(t("sum.sessions"))}</span>`
            : `<span class="muted">${gs.esc(t("sum.none"))}</span>`}
            <span><b>${d.voci.length}</b> ${gs.esc(t("sum.notes"))}</span></div>
          <form class="di-form"><textarea class="field" rows="2" maxlength="4000" placeholder="${gs.esc(t("placeholder"))}" aria-label="${gs.esc(t("newNote"))}"></textarea>
            <button class="btn primary" type="submit">${gs.esc(t("add"))}</button></form>
          ${giorni.length ? `<ol class="di-days">${giorni.map((g) => `<li><h4>${gs.esc(giorno(g.t))}</h4><ul>${g.righe.map(riga).join("")}</ul></li>`).join("")}</ol>`
            : `<p class="muted di-empty">${gs.esc(t("empty"))}</p>`}`;
      };
      box.addEventListener("submit", async (e) => {
        e.preventDefault();
        const ta = box.querySelector("textarea");
        if (!ta.value.trim()) return;
        try { await gs.api("/plugin-api/diario/aggiungi", { body: { id: game.id, testo: ta.value } }); } catch (err) { return gs.toast(err.message, true); }
        draw();
      });
      box.addEventListener("click", async (e) => {
        const b = e.target.closest(".di-del");
        if (!b || !confirm(t("confirmDelete"))) return;
        try { await gs.api("/plugin-api/diario/elimina", { body: { id: game.id, t: +b.dataset.t } }); } catch (err) { return gs.toast(err.message, true); }
        draw();
      });
      await draw();
      return box;
    },
  });
}
