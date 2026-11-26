// Pulizia libreria: riquadri con quanto c'e' da sistemare, copertine da selezionare, azioni di gruppo e file identici su disco.
import { afterApply, baseName, confirmText, duplicates, fmtBytes, freeable, freeableTotal, incomplete, linkable, neverPlayed, stale } from "./logica.js";

const VIEW = "pulizia";
const MAX = 300;  // copertine mostrate per scheda: con librerie enormi la pagina resta leggera
const ACTIONS = { hide: { field: "hidden", value: true }, dropped: { field: "status", value: "dropped" }, backlog: { field: "status", value: "backlog" } };

export default function (gs, ctx) {
  const { t, lang } = ctx;
  const bytes = (n) => fmtBytes(n, lang);
  let dupIds = new Set(), builtAt = null;
  // «File identici su disco»: stato fuori dal render, cosi' sopravvive tra una visita e l'altra alla pagina
  let disk = null, scanning = false, busy = false;
  const refreshDup = () => {
    const lib = gs.library();
    if (!lib || lib.builtAt === builtAt) return;
    builtAt = lib.builtAt;
    dupIds = new Set(duplicates(lib.games).flat().map((g) => g.id));
  };
  gs.addTileBadge({ id: "dup", render: (g) => { refreshDup(); return dupIds.has(g.id) ? t("badge") : null; } });
  gs.addSidebarItem({ id: VIEW, label: t("nav"), icon: "⌫", view: VIEW });
  gs.addTutorial({
    id: ctx.id, view: VIEW,
    steps: [
      { title: t("tut.1.t"), text: t("tut.1.x"), sel: ".pl-sum" },
      { title: t("tut.2.t"), text: t("tut.2.x"), sel: ".pl-grid, .pl-disk" },
      { title: t("tut.3.t"), text: t("tut.3.x"), sel: ".pl-bar" },
    ],
  });

  gs.registerView(VIEW, {
    title: t("nav"),
    render(el) {
      let tab = gs.store.get("pulizia.tab", "dup"), years = gs.store.get("pulizia.anni", 2);
      const sel = new Set();
      const platName = (g) => gs.library().plats.get(g.platform)?.name || g.store || g.platform;
      const lists = () => {
        const games = gs.library().games;
        return {
          dup: duplicates(games).map((l) => ({ ids: l.map((g) => g.id), g: l[0], extra: t("copies", { n: l.length }), group: l })),
          mai: neverPlayed(games).map((g) => ({ ids: [g.id], g, extra: g.year || "" })),
          fermi: stale(games, years).map((g) => ({ ids: [g.id], g, extra: t("last", { data: new Date(g.grp.last * 1000).toLocaleDateString(lang, { month: "short", year: "numeric" }) }) })),
          meta: incomplete(games).map(({ g, m }) => ({ ids: [g.id], g, extra: t("missing", { cosa: m.map((x) => t(`m.${x}`)).join(", ") }) })),
        };
      };
      const targets = (r) => (r.ids.length > 1 ? r.ids.slice(1) : r.ids);   // duplicati: si tiene la prima copia

      const card = (r, i) => {
        const on = targets(r).every((id) => sel.has(id));
        const covers = (r.group || [r.g]).slice(0, 3).map((g) => `<img src="${gs.ui.cover(g.id, 200)}" alt="" loading="lazy" data-onerr="remove">`).join("");
        return `<article class="pl-card${on ? " on" : ""}${r.group ? " stack" : ""}">
          <label class="pl-pick"><input type="checkbox" data-i="${i}" ${on ? "checked" : ""} aria-label="${gs.esc(t("select", { titolo: r.g.title }))}">
            <span class="pl-covers">${covers}<b>${gs.esc(r.g.title)}</b></span></label>
          <div class="pl-info"><b title="${gs.esc(r.g.title)}">${gs.esc(r.g.title)}</b><span class="muted">${gs.esc(platName(r.g))}</span>
            <span class="pl-extra">${gs.esc(r.extra)}</span></div>
          <button class="icon-btn pl-open" type="button" data-open="${gs.esc(r.g.id)}" title="${gs.esc(t("open"))}" aria-label="${gs.esc(t("open"))}">↗</button></article>`;
      };

      const draw = () => {
        const all = lists();
        const counts = { dup: all.dup.length, mai: all.mai.length, fermi: all.fermi.length, meta: all.meta.length };
        const sum = ["dup", "mai", "fermi", "meta", "disk"].map((k) => `<button class="pl-sum-card${k === tab ? " on" : ""}" type="button" data-tab="${k}">
            <b>${k === "disk" ? (disk ? gs.esc(bytes(disk.freeable)) : "—") : counts[k].toLocaleString(lang)}</b><span>${gs.esc(t(`tab.${k}`))}</span>
            <small class="muted">${gs.esc(t(`tab.${k}.x`))}</small></button>`).join("");
        const body = gs.ui.page(el, { title: t("nav"), subtitle: t("subtitle"), tutorial: ctx.id });
        body.innerHTML = `<nav class="pl-sum" aria-label="${gs.esc(t("nav"))}">${sum}</nav><section class="pl-main"></section>`;
        const main = body.querySelector(".pl-main");
        if (tab === "disk") return drawDisk(main);
        const list = all[tab], shown = list.slice(0, MAX);
        el._rows = shown;
        if (!list.length) { main.append(gs.ui.empty({ icon: "✓", title: t("clean.t"), text: t(`clean.${tab}`) })); return; }
        main.innerHTML = `<div class="pl-bar">
            ${tab === "fermi" ? `<label class="pl-years">${gs.esc(t("years.l"))} <select class="field" id="pl-y">${[1, 2, 3, 5].map((y) => `<option value="${y}" ${y === years ? "selected" : ""}>${gs.esc(t("years", { n: y }))}</option>`).join("")}</select></label>` : ""}
            <button class="btn" type="button" id="pl-all">${gs.esc(t("all"))}</button>
            <button class="btn" type="button" id="pl-none" ${sel.size ? "" : "disabled"}>${gs.esc(t("none"))}</button>
            <span class="pl-count">${gs.esc(t("selected", { n: sel.size }))}</span>
            ${Object.keys(ACTIONS).map((k) => `<button class="btn${k === "hide" ? " primary" : ""}" type="button" data-act="${k}" ${sel.size ? "" : "disabled"}>${gs.esc(t(`act.${k}`))}</button>`).join("")}
            ${tab === "dup" ? `<button class="btn" type="button" id="pl-manual-dupes" title="${gs.esc(t("manual.x"))}">${gs.esc(t("manual"))}</button>` : ""}</div>
          ${tab === "dup" ? `<p class="muted small">${gs.esc(t("dup.note"))}</p>` : ""}
          <div class="pl-grid">${shown.map(card).join("")}</div>
          ${list.length > shown.length ? `<p class="muted">${gs.esc(t("more", { n: list.length - shown.length }))}</p>` : ""}`;
      };

      el.onchange = (e) => {
        if (e.target.id === "pl-y") { years = +e.target.value; gs.store.set("pulizia.anni", years); sel.clear(); return draw(); }
        if (e.target.type === "radio" && e.target.dataset.g !== undefined) {   // copia da tenere: si ricalcola lo spazio
          disk.groups[+e.target.dataset.g].keep = +e.target.dataset.j;
          disk.freeable = freeableTotal(disk.groups);
          return draw();
        }
        const i = e.target.dataset.i;
        if (i === undefined) return;
        for (const id of targets(el._rows[+i])) (e.target.checked ? sel.add(id) : sel.delete(id));
        draw();
      };
      el.onclick = async (e) => {
        const b = e.target.closest("[data-tab],[data-act],[data-open],#pl-all,#pl-none,#pl-manual-dupes,#pl-dup-scan,[data-dup]");
        if (!b || b.disabled) return;
        if (b.dataset.open) return gs.openGame(+b.dataset.open);
        if (b.dataset.tab) { tab = b.dataset.tab; gs.store.set("pulizia.tab", tab); sel.clear(); return draw(); }
        if (b.id === "pl-all") { el._rows.forEach((r) => targets(r).forEach((id) => sel.add(id))); return draw(); }
        if (b.id === "pl-none") { sel.clear(); return draw(); }
        if (b.id === "pl-dup-scan") { if (!busy && !scanning) await scan(); return; }
        if (b.dataset.dup) return applyDup(+b.dataset.g, b.dataset.dup);
        if (b.id === "pl-manual-dupes") {
          if (!confirm(t("manual.confirm"))) return;
          try {
            const r = await gs.api("/api/manual/dedupe", { body: {} });
            gs.toast(r.removed ? t("manual.done", { n: r.removed }) : t("manual.none"));
            if (r.removed) await gs.refresh();
          } catch (err) { gs.toast(err.message, true); }
          return draw();
        }
        const label = t(`act.${b.dataset.act}`);
        if (!sel.size || !confirm(t("act.confirm", { azione: label, n: sel.size }))) return;
        let ok = 0, fail = 0;
        for (const id of sel) { try { await gs.api(`/api/game/${id}/flag`, { body: ACTIONS[b.dataset.act] }); ok++; } catch { fail++; } }
        gs.toast(t(fail ? "act.partial" : "act.done", { azione: label, ok, fail }), !!fail);
        sel.clear();
        await gs.refresh();
        draw();
      };

      const dupCard = (g, i) => {
        const can = linkable(g);
        const files = g.files.map((f, j) => `<label class="pl-dup-file">
            <input type="radio" name="keep-${i}" data-g="${i}" data-j="${j}" ${j === g.keep ? "checked" : ""} ${busy ? "disabled" : ""}>
            <span><b>${gs.esc(f.game || baseName(f.path))}</b> ${f.region ? `<span class="muted">${gs.esc(f.region)}</span>` : ""}
              ${j !== g.keep && (f.dev != null ? f.dev !== g.files[g.keep].dev : !!j && f.same_volume_as_first === false) ? `<span class="badge">${gs.esc(t("disk.other"))}</span>` : ""}
              ${f.is_hardlink ? `<span class="badge">${gs.esc(t("disk.linked"))}</span>` : ""}<br><code>${gs.esc(f.path)}</code></span></label>`).join("");
        return `<article class="pl-dup-card"><header><b>${gs.esc(bytes(freeable(g)))}</b>
            <span class="muted">${gs.esc(t("disk.group", { n: g.files.length, size: bytes(g.size) }))}</span></header>
          <p class="muted small">${gs.esc(t("disk.keep"))}</p>${files}
          <div class="row wrap"><button class="btn" type="button" data-dup="hardlink" data-g="${i}" ${can && !busy ? "" : "disabled"} title="${gs.esc(can ? t("disk.linkX") : t("disk.cantLink"))}">${gs.esc(t("disk.link"))}</button>
            <button class="btn" type="button" data-dup="delete" data-g="${i}" ${busy ? "disabled" : ""}>${gs.esc(t("disk.delete"))}</button></div></article>`;
      };
      const drawDisk = (main) => {
        main.className = "pl-main pl-disk";
        if (scanning) { main.innerHTML = `<p class="muted">${gs.esc(t("disk.scanning"))}</p>`; return; }
        if (!disk) {
          main.append(gs.ui.empty({ icon: "⧉", title: t("disk.t"), text: t("disk.x"), action: { label: t("disk.scan"), run: scan } }));
          return;
        }
        main.innerHTML = `<div class="pl-bar"><span class="pl-count">${gs.esc(t("disk.total", { size: bytes(disk.freeable), n: disk.groups.length }))}</span>
            <button class="btn" type="button" id="pl-dup-scan" ${busy ? "disabled" : ""}>${gs.esc(t("disk.rescan"))}</button></div>`
          + (disk.groups.length ? disk.groups.map(dupCard).join("") : `<p class="muted">${gs.esc(t("disk.none"))}</p>`);
      };
      const scan = async () => {
        scanning = true; draw();
        try { const r = await gs.api(`/plugin-api/${VIEW}/dup-files`); disk = { groups: r.groups || [], freeable: r.freeable || 0 }; }
        catch (err) { gs.toast(err.message, true); }
        scanning = false; draw();
      };
      const applyDup = async (i, action) => {
        const g = disk.groups[i];
        if (busy || !confirm(confirmText(action, g, g.keep, t))) return;
        busy = true; draw();
        try {
          const r = await gs.api(`/plugin-api/${VIEW}/dup-apply`, { body: { hash: g.hash, keep: g.files[g.keep].path, action } });
          const res = r.results || [], bad = res.filter((x) => !x.ok).length;
          gs.toast(t(action === "delete" ? "disk.deleted" : "disk.linkedN", { n: res.length - bad, fail: bad }), !!bad);
          const next = afterApply(g, action, res);
          disk.groups.splice(i, 1, ...(next ? [next] : []));
          disk.freeable = freeableTotal(disk.groups);
        } catch (err) { gs.toast(err.message, true); }
        busy = false; draw();
      };
      draw();
    },
  });
}
