// Calendario uscite: un calendario per mese con le copertine dei giochi in uscita, la lista dei desideri in cima.
import { perMese, settimane } from "./logica.js";

export default function (gs, ctx) {
  const { t, lang } = ctx;
  const VIEW = "calendario-uscite";
  let tutti = false;  // false: solo i generi che giochi di piu'

  gs.addSidebarItem({ id: VIEW, label: t("nav"), icon: "▦", view: VIEW });
  gs.addTutorial({
    id: ctx.id, view: VIEW,
    steps: [
      { title: t("tut.1.t"), text: t("tut.1.x") },
      { title: t("tut.2.t"), text: t("tut.2.x"), sel: ".cu-filter" },
      { title: t("tut.3.t"), text: t("tut.3.x"), sel: ".cu-cal" },
      { title: t("tut.4.t"), text: t("tut.4.x"), sel: ".cu-wish" },
    ],
  });

  const fmt = (d, o) => new Date(d + "T12:00:00").toLocaleDateString(lang, o);
  const quando = (v) => (v.giorni === 0 ? t("today") : v.giorni === 1 ? t("tomorrow") : t("inDays", { n: v.giorni }));
  const key = (v) => gs.fold(v.titolo);

  function card(v, inWish) {
    const art = v.copertina ? `<img src="${gs.esc(v.copertina)}" alt="" loading="lazy" data-onerr="remove">` : "";
    return `<article class="cu-card" data-day="${gs.esc(v.data)}">
      <div class="cu-art">${art}<span class="cu-count">${gs.esc(quando(v))}</span></div>
      <div class="cu-info"><b title="${gs.esc(v.titolo)}">${gs.esc(v.titolo)}</b>
        <span class="muted">${gs.esc(fmt(v.data, { day: "numeric", month: "long", year: "numeric" }))}</span>
        <span class="muted cu-plat">${gs.esc(v.piattaforme.join(" · "))}</span>
        ${inWish ? `<span class="chip on cu-in">♥ ${gs.esc(t("inWish"))}</span>`
          : `<button class="btn cu-wish" type="button" data-wish="${gs.esc(v.titolo)}" data-cover="${gs.esc(v.copertina || "")}">♡ ${gs.esc(t("addWish"))}</button>`}
      </div></article>`;
  }

  function month(m, wish) {
    const head = settimane(lang).map((d) => `<span class="cu-wd">${gs.esc(d)}</span>`).join("");
    const cells = m.celle.map((c) => {
      if (!c) return `<span class="cu-cell empty"></span>`;
      const thumbs = c.uscite.slice(0, 2).map((v) => (v.copertina
        ? `<img src="${gs.esc(v.copertina)}" alt="" title="${gs.esc(v.titolo)}" loading="lazy" data-onerr="remove">` : "")).join("");
      const more = c.uscite.length > 2 ? `<span class="cu-more">+${c.uscite.length - 2}</span>` : "";
      return c.uscite.length
        ? `<button class="cu-cell has" type="button" data-goto="${gs.esc(c.data)}" title="${gs.esc(c.uscite.map((v) => v.titolo).join(", "))}">`
          + `<span class="cu-n">${c.giorno}</span><span class="cu-thumbs">${thumbs}${more}</span></button>`
        : `<span class="cu-cell${c.oggi ? " today" : ""}"><span class="cu-n">${c.giorno}</span></span>`;
    }).join("");
    return `<section class="shelf-section cu-month">
      <h2><span class="cu-mname">${gs.esc(fmt(m.chiave + "-01", { month: "long", year: "numeric" }))}</span><small>${gs.esc(t("count", { n: m.uscite.length }))}</small></h2>
      <div class="cu-cal">${head}${cells}</div>
      <div class="shelf-lane cu-lane">${m.uscite.map((v) => card(v, wish.has(key(v)))).join("")}</div></section>`;
  }

  gs.registerView(VIEW, {
    title: t("nav"),
    async render(el) {
      const draw = async () => {
        const actions = `<div class="row tight cu-filter" role="group" aria-label="${gs.esc(t("filter"))}">`
          + `<button class="chip${tutti ? "" : " on"}" type="button" data-tutti="0">${gs.esc(t("mine"))}</button>`
          + `<button class="chip${tutti ? " on" : ""}" type="button" data-tutti="1">${gs.esc(t("all"))}</button></div>`;
        const body = gs.ui.page(el, { title: t("nav"), subtitle: t("subtitle"), actions, tutorial: ctx.id });
        el.querySelectorAll("[data-tutti]").forEach((b) => { b.onclick = () => { tutti = b.dataset.tutti === "1"; draw(); }; });
        body.innerHTML = `<p class="muted">${gs.esc(t("loading"))}</p>`;
        let d, wl;
        try {
          [d, wl] = await Promise.all([gs.api(`/plugin-api/${VIEW}/uscite${tutti ? "?tutti=true" : ""}`), gs.api("/api/wishlist").catch(() => ({}))]);
        } catch (e) {
          body.innerHTML = "";
          const nokey = [t("err.nokey"), t("err.key")].includes(e.message);  // stessi testi del server, nella stessa lingua
          body.append(gs.ui.empty({ icon: "▦", title: t(nokey ? "nokey.t" : "error.t"), text: e.message,
            action: nokey && typeof openSettings === "function" ? { label: t("nokey.btn"), run: () => openSettings("src") } : { label: t("retry"), run: draw } }));
          return;
        }
        const wish = new Set((wl.items || []).map((w) => gs.fold(w.title)));
        body.innerHTML = "";
        if (d.desideri.length) {
          const s = document.createElement("section");
          s.className = "shelf-section cu-wishlist";
          s.innerHTML = `<h2>${gs.esc(t("fromWish"))}</h2><div class="shelf-lane cu-lane">${d.desideri.map((v) => card(v, true)).join("")}</div>`;
          body.append(s);
        }
        const mesi = perMese(d.prossime, new Date());
        if (!mesi.length && !d.desideri.length) {
          body.append(gs.ui.empty({ icon: "▦", title: t("none.t"), text: t("none.x") }));
          return;
        }
        body.insertAdjacentHTML("beforeend", mesi.map((m) => month(m, wish)).join("")
          + `<p class="muted small">${gs.esc(t(d.generi.length ? "sourceGenres" : "source"))}</p>`);
        body.onclick = async (e) => {
          const go = e.target.closest("[data-goto]");
          if (go) {
            const cards = [...body.querySelectorAll(`.cu-card[data-day="${go.dataset.goto}"]`)];
            body.querySelectorAll(".cu-card.on").forEach((c) => c.classList.remove("on"));
            cards.forEach((c) => c.classList.add("on"));
            cards[0]?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "start" });
            return;
          }
          const b = e.target.closest("[data-wish]");
          if (!b) return;
          b.disabled = true;
          try {
            await gs.api("/api/wishlist/add", { body: { title: b.dataset.wish, cover: b.dataset.cover } });
            b.outerHTML = `<span class="chip on cu-in">♥ ${gs.esc(t("inWish"))}</span>`;
            gs.toast(t("added", { titolo: b.dataset.wish }));
          } catch (err) { b.disabled = false; gs.toast(err.message, true); }
        };
      };
      await draw();
    },
  });
}
