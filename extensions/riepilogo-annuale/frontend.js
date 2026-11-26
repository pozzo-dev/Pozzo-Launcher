// Riepilogo annuale: il tuo anno di gioco raccontato come una storia a schermo intero (i numeri completi restano in Statistiche).
const VIEW = "riepilogo-annuale";
const DURATA = 6500;  // ms per scheda prima di passare alla successiva

export default function (gs, ctx) {
  const { t, lang } = ctx;
  const num = (n) => new Intl.NumberFormat(lang, { maximumFractionDigits: 1 }).format(n || 0);
  const mese = (i) => new Date(2024, i, 1).toLocaleDateString(lang, { month: "long" });
  const giorno = (i) => new Date(2024, 0, 1 + i).toLocaleDateString(lang, { weekday: "long" });  // 1/1/2024 = lunedi'
  // copertina con un segnaposto colorato e il titolo sotto: se l'immagine manca resta quello, come negli scaffali
  const hue = (s) => [...String(s)].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 7);
  const cover = (g, w = 600) => `<span class="ra-tile" style="--h:${hue(g.titolo)}"><b>${gs.esc(g.titolo)}</b>`
    + `${g.id ? `<img src="${gs.ui.cover(g.id, w)}" alt="" data-onerr="remove">` : ""}</span>`;

  gs.addSidebarItem({ id: VIEW, label: t("nav"), icon: "✦", view: VIEW });
  gs.addTutorial({
    id: ctx.id, view: VIEW,
    steps: [
      { title: t("tut.1.t"), text: t("tut.1.x") },
      { title: t("tut.2.t"), text: t("tut.2.x"), sel: ".ra-years" },
      { title: t("tut.3.t"), text: t("tut.3.x"), sel: ".ra-play" },
      { title: t("tut.4.t"), text: t("tut.4.x") },
    ],
  });

  /** Le schede della storia: ognuna e' HTML; le vuote si saltano. */
  function schede(d) {
    const [primo] = d.top;
    const maxM = Math.max(1, ...d.per_mese);
    return [
      `<div class="ra-s ra-intro"><div class="ra-mosaic">${d.top.map((g) => cover(g, 300)).join("")}</div>
        <p class="ra-k">${gs.esc(t("s.intro.k"))}</p><h2 class="ra-big">${gs.esc(t("s.intro.t", { anno: d.anno }))}</h2></div>`,
      `<div class="ra-s"><p class="ra-k">${gs.esc(t("s.hours.k"))}</p><h2 class="ra-huge">${num(d.ore)}</h2>
        <p class="ra-l">${gs.esc(t("s.hours.l"))}</p><p class="ra-sub">${gs.esc(t("s.hours.sub", { partite: d.partite, giorni: d.giorni, giochi: d.giochi }))}</p></div>`,
      primo && `<div class="ra-s ra-goty"><div class="ra-cover">${cover(primo)}</div><div>
        <p class="ra-k">${gs.esc(t("s.goty.k"))}</p><h2 class="ra-big">${gs.esc(primo.titolo)}</h2>
        <p class="ra-sub">${gs.esc(t("s.goty.sub", { ore: num(primo.ore), partite: primo.partite }))}</p></div></div>`,
      d.top.length > 1 && `<div class="ra-s"><p class="ra-k">${gs.esc(t("s.top.k"))}</p><ol class="ra-top">${d.top.map((g, i) =>
        `<li style="--i:${i}">${cover(g, 160)}<span><b>${gs.esc(g.titolo)}</b><small>${gs.esc(g.console)}</small></span>`
        + `<em>${gs.esc(t("hours", { n: num(g.ore) }))}</em></li>`).join("")}</ol></div>`,
      d.mese !== null && `<div class="ra-s"><p class="ra-k">${gs.esc(t("s.habits.k"))}</p>
        <dl class="ra-facts"><div><dt>${gs.esc(t("s.console"))}</dt><dd>${gs.esc(d.console || "")}</dd><small>${gs.esc(t("hours", { n: num(d.console_ore) }))}</small></div>
        <div><dt>${gs.esc(t("s.month"))}</dt><dd class="ra-cap">${gs.esc(mese(d.mese))}</dd><small>${gs.esc(t("hours", { n: num(d.mese_ore) }))}</small></div>
        <div><dt>${gs.esc(t("s.day"))}</dt><dd class="ra-cap">${gs.esc(giorno(d.giorno_settimana))}</dd></div></dl>
        <div class="ra-months">${d.per_mese.map((h, i) => `<div><i style="--h:${Math.round((100 * h) / maxM)}%"></i>`
          + `<span>${gs.esc(mese(i).slice(0, 1).toUpperCase())}</span></div>`).join("")}</div></div>`,
      (d.sessione_piu_lunga || d.finiti) && `<div class="ra-s"><p class="ra-k">${gs.esc(t("s.records.k"))}</p><dl class="ra-facts">
        ${d.sessione_piu_lunga ? `<div><dt>${gs.esc(t("s.longest"))}</dt><dd>${gs.esc(t("hours", { n: num(d.sessione_piu_lunga.ore) }))}</dd>
          <small>${gs.esc(d.sessione_piu_lunga.titolo)}</small></div>` : ""}
        ${d.finiti ? `<div><dt>${gs.esc(t("s.done"))}</dt><dd>${d.finiti}</dd></div>` : ""}</dl></div>`,
      `<div class="ra-s ra-end"><h2 class="ra-big">${gs.esc(t("s.end.t", { anno: d.anno }))}</h2>
        <div class="row ra-end-btns"><button class="btn primary" type="button" data-ra="img">${gs.esc(t("saveImg"))}</button>
        <button class="btn" type="button" data-ra="stats">${gs.esc(t("allStats"))}</button></div></div>`,
    ].filter(Boolean);
  }

  /** Storia a schermo intero: frecce, spazio, clic a sinistra/destra; Esc chiude. */
  function storia(d) {
    const s = schede(d);
    let i = 0, timer = 0;
    const opener = document.activeElement;
    const box = document.createElement("div");
    box.className = "ra-story";
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-modal", "true");
    box.setAttribute("aria-label", t("s.intro.t", { anno: d.anno }));
    box.innerHTML = `<div class="ra-bars">${s.map(() => "<i><b></b></i>").join("")}</div>
      <button class="icon-btn ra-close" type="button" aria-label="${gs.esc(t("close"))}" title="${gs.esc(t("close"))}">✕</button>
      <div class="ra-stage" aria-live="polite"></div>
      <button class="ra-nav prev" type="button" aria-label="${gs.esc(t("prev"))}"></button>
      <button class="ra-nav next" type="button" aria-label="${gs.esc(t("next"))}"></button>`;
    const stage = box.querySelector(".ra-stage"), bars = [...box.querySelectorAll(".ra-bars i")];
    const show = (n) => {
      i = Math.max(0, Math.min(s.length - 1, n));
      stage.innerHTML = s[i];
      bars.forEach((b, k) => { b.className = k < i ? "done" : k === i ? "now" : ""; });
      clearTimeout(timer);
      if (i < s.length - 1) timer = setTimeout(() => show(i + 1), DURATA);  // l'ultima resta: ha i pulsanti
    };
    const close = () => {
      clearTimeout(timer);
      document.removeEventListener("keydown", key, true);
      box.remove();
      opener?.focus?.();
    };
    const key = (e) => {
      const k = e.key;
      if (k === "Escape") close();
      else if (k === "ArrowRight" || (k === " " && !e.target.closest?.("button"))) show(i + 1);
      else if (k === "ArrowLeft") show(i - 1);
      else return;
      e.preventDefault(); e.stopPropagation();  // le scorciatoie dell'app restano ferme
    };
    box.onclick = (e) => {
      if (e.target.closest(".ra-close")) return close();
      if (e.target.closest(".ra-nav.prev")) return show(i - 1);
      if (e.target.closest(".ra-nav.next")) return show(i + 1);
      const b = e.target.closest("[data-ra]");
      if (b?.dataset.ra === "img") salva(d);
      if (b?.dataset.ra === "stats") { close(); if (typeof setView === "function") setView({ type: "stats" }); }
    };
    document.addEventListener("keydown", key, true);
    document.body.append(box);
    box.querySelector(".ra-close").focus();
    show(0);
  }

  /** Immagine 1080x1350 da condividere, con i colori del tema. */
  function salva(d) {
    const cs = getComputedStyle(document.documentElement);
    const v = (n, d0) => cs.getPropertyValue(n).trim() || d0;
    const css = { bg: v("--bg", "#151821"), bg2: v("--bg-3", "#232a3d"), text: v("--text", "#f2f4f8"), muted: v("--muted", "#9aa4b8"), accent: v("--accent", "#7c8cff") };
    const c = document.createElement("canvas");
    c.width = 1080; c.height = 1350;
    const x = c.getContext("2d");
    const g = x.createLinearGradient(0, 0, 1080, 1350);
    g.addColorStop(0, css.bg); g.addColorStop(1, css.bg2);
    x.fillStyle = g; x.fillRect(0, 0, 1080, 1350);
    const font = "system-ui, -apple-system, 'Segoe UI', sans-serif";
    const text = (s, px, py, size, weight = 700, color = css.text, align = "left") => {
      x.font = `${weight} ${size}px ${font}`; x.fillStyle = color; x.textAlign = align; x.fillText(s, px, py);
    };
    const fit = (s, w, size) => { x.font = `600 ${size}px ${font}`; let o = s; while (x.measureText(o).width > w && o.length > 4) o = o.slice(0, -2); return o === s ? s : o + "…"; };
    text(t("img.title", { anno: d.anno }), 80, 140, 64, 800, css.accent);
    text(t("hours", { n: num(d.ore) }), 80, 300, 150, 800);
    text(t("s.hours.sub", { partite: d.partite, giorni: d.giorni, giochi: d.giochi }), 80, 360, 34, 500, css.muted);
    text(t("s.top.k"), 80, 480, 40, 700, css.accent);
    d.top.forEach((g, k) => {
      const y = 550 + k * 78;
      text(`${k + 1}`, 80, y, 44, 800, css.muted);
      text(fit(g.titolo, 720, 42), 150, y, 42, 600);
      text(t("hours", { n: num(g.ore) }), 1000, y, 42, 700, css.muted, "right");
    });
    let y = 1010;
    const line = (label, value) => { text(label, 80, y, 30, 500, css.muted); text(value, 80, y + 46, 46, 700); y += 120; };
    if (d.console) line(t("s.console"), `${d.console} · ${t("hours", { n: num(d.console_ore) })}`);
    if (d.mese !== null) line(t("s.month"), `${mese(d.mese)} · ${t("hours", { n: num(d.mese_ore) })}`);
    if (d.finiti) line(t("s.done"), String(d.finiti));
    text("Pozzo Launcher", 1000, 1300, 30, 700, css.muted, "right");
    const a = document.createElement("a");
    a.download = t("img.file", { anno: d.anno }) + ".png";
    a.href = c.toDataURL("image/png");
    a.click();
  }

  gs.registerView(VIEW, {
    title: t("nav"),
    async render(el) {
      const show = async (anno) => {
        let d;
        try { d = await gs.api(`/plugin-api/${VIEW}/anno${anno ? "?anno=" + anno : ""}`); }
        catch (e) { el.innerHTML = ""; el.append(gs.ui.empty({ icon: "✦", title: t("error"), text: e.message })); return; }
        const anni = d.anni.length ? d.anni : [d.anno];
        const actions = `<div class="row tight ra-years" role="group" aria-label="${gs.esc(t("year"))}">${anni.map((y) =>
          `<button class="chip${y === d.anno ? " on" : ""}" type="button" data-anno="${y}">${y}</button>`).join("")}</div>`;
        const body = gs.ui.page(el, { title: t("nav"), subtitle: t("subtitle"), actions, tutorial: ctx.id });
        el.querySelectorAll("[data-anno]").forEach((b) => { b.onclick = () => show(+b.dataset.anno); });
        if (!d.partite) {
          body.append(gs.ui.empty({ icon: "✦", title: t("empty.t", { anno: d.anno }), text: t("empty.x") }));
          return;
        }
        body.innerHTML = `<section class="ra-hero"><div class="ra-mosaic">${d.top.map((g) => cover(g, 300)).join("")}</div>
          <div class="ra-hero-txt"><p class="ra-k">${gs.esc(t("s.intro.t", { anno: d.anno }))}</p>
          <h2>${gs.esc(t("hours", { n: num(d.ore) }))}</h2>
          <p class="muted">${gs.esc(t("s.hours.sub", { partite: d.partite, giorni: d.giorni, giochi: d.giochi }))}</p>
          <div class="row"><button class="btn primary ra-play" type="button">▶ ${gs.esc(t("play", { anno: d.anno }))}</button>
          <button class="btn" type="button" data-ra-img>${gs.esc(t("saveImg"))}</button></div></div></section>`;
        body.querySelector(".ra-play").onclick = () => storia(d);
        body.querySelector("[data-ra-img]").onclick = () => salva(d);
      };
      await show(0);
    },
  });
}
