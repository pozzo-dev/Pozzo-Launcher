// Ricette web: motore e catalogo multimediale da fonti web lecite ed RSS/JSON.

export const safeUrl = (u) => {
  const s = String(u || "").trim();
  return /^https?:\/\//i.test(s) || s.startsWith("/") ? s : "";
};

export const formatDuration = (sec) => {
  const n = Number(sec);
  if (!n || isNaN(n) || n <= 0) return "";
  const h = Math.floor(n / 3600);
  const m = Math.floor((n % 3600) / 60);
  const s = Math.floor(n % 60);
  if (h > 0) return `${h}h ${m ? m + "m" : ""}`.trim();
  return `${m}m ${s ? s + "s" : ""}`.trim();
};

export default function (gs, ctx) {
  const pluginId = ctx?.id || "ricette-web";
  const apiBase = `/plugin-api/${pluginId}`;
  const t = ctx.t;
  const esc = (s) => (gs?.esc ? gs.esc(s) : String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c])));

  const kindLabel = (k) => { const v = t(`kind.${k}`); return v === `kind.${k}` ? k : v; };

  const openUrl = async (url) => {
    const clean = safeUrl(url);
    if (!clean) return;
    try {
      await gs.api("/api/open", { body: { url: clean } });
    } catch (e) {
      if (typeof gs?.toast === "function") gs.toast(t("open.fail", { err: e.message }), true);
    }
  };

  gs.addSidebarItem({ id: "ricette-web", label: t("nav"), icon: "🌐", view: "ricette-web" });
  gs.addTutorial({
    id: pluginId, view: "ricette-web",
    steps: [
      { title: t("tut.1.t"), text: t("tut.1.x"), sel: ".rw-sources-bar" },
      { title: t("tut.2.t"), text: t("tut.2.x"), sel: ".rw-search-box" },
      { title: t("tut.3.t"), text: t("tut.3.x"), sel: ".rw-catalog" },
    ],
  });

  gs.registerView("ricette-web", {
    title: t("nav"),
    async render(el) {
      if (!el) return;
      const root = gs.ui.page(el, { title: t("nav"), subtitle: t("subtitle"), tutorial: pluginId });
      root.classList.add("rw-view");

      let recipes = [];
      let activeRecipeId = "";
      let activeTab = "items"; // "items" | "recipe_preview"
      let currentQuery = "";
      let items = [];
      let selectedItemId = null;
      let selectedItemDetail = null;
      let loading = false;
      let loadToken = 0;

      // Elementi strutturali
      const toolbar = document.createElement("div");
      toolbar.className = "rw-toolbar";

      const sourcesBar = document.createElement("div");
      sourcesBar.className = "rw-sources-bar";

      const content = document.createElement("div");
      content.className = "rw-content";

      root.append(toolbar, sourcesBar, content);

      // Carica elenco ricette
      async function loadRecipes() {
        try {
          const res = await gs.api(`${apiBase}/recipes`);
          recipes = Array.isArray(res?.recipes) ? res.recipes : [];
        } catch {
          recipes = [];
        }
      }

      // Lista paginata: prima pagina subito, il resto con infinite scroll
      const PAGE = 60;
      let offset = 0;
      let done = false;
      let busy = false;
      let observer = null;

      const cardHtml = (it) => {
        const poster = safeUrl(it.poster);
        const metaParts = [];
        if (it.year) metaParts.push(esc(it.year));
        if (it.duration) metaParts.push(esc(formatDuration(it.duration)));
        if (it.kind && it.kind !== 'film') metaParts.push(esc(kindLabel(it.kind)));
        const icon = it.kind === 'brano' ? '🎵' : '🎬';
        return `
          <article class="rw-card ${it.seen ? 'rw-seen' : ''}" data-item-id="${esc(it.id)}" tabindex="0" role="button">
            <div class="rw-poster">
              ${poster ? `<img class="rw-poster-img" src="${esc(poster)}" alt="" loading="lazy" decoding="async">` : `<div class="rw-poster-placeholder">${icon}</div>`}
              ${it.seen ? `<span class="rw-seen-badge">${esc(t("seen"))}</span>` : ''}
            </div>
            <div class="rw-card-body">
              <h4 class="rw-title" title="${esc(it.title)}">${esc(it.title)}</h4>
              ${metaParts.length ? `<div class="rw-meta">${metaParts.join(" · ")}</div>` : ''}
            </div>
          </article>`;
      };

      function appendCards(list) {
        const grid = content.querySelector(".rw-grid");
        if (!grid || !list.length) return;
        const tpl = document.createElement("template");
        tpl.innerHTML = list.map(cardHtml).join("");
        const frag = document.createDocumentFragment();
        frag.append(tpl.content);
        grid.appendChild(frag);
      }

      function updateMore() {
        const more = content.querySelector(".rw-more");
        if (!more) return;
        more.textContent = busy
          ? t("loading")
          : (items.length ? "" : t(recipes.length ? "empty.search" : "empty.none"));
        if (observer) { // riarma: se il sentinel è ancora visibile deve riscattare
          observer.disconnect();
          if (!done && !busy) observer.observe(more);
        }
      }

      async function fetchMore() {
        if (busy || done) return;
        busy = true;
        const myToken = loadToken;
        updateMore();
        const q = new URLSearchParams();
        if (activeRecipeId) q.set("recipe", activeRecipeId);
        if (currentQuery) q.set("q", currentQuery);
        q.set("offset", String(offset));
        q.set("limit", String(PAGE));
        let page = [];
        try {
          const res = await gs.api(`${apiBase}/list?${q.toString()}`);
          page = Array.isArray(res) ? res : [];
        } catch {
          done = true;
        }
        if (myToken !== loadToken) return; // risposta vecchia: ignora
        busy = false;
        offset += page.length;
        if (page.length < PAGE) done = true;
        items = items.concat(page);
        if (!selectedItemId && activeTab === "items") {
          appendCards(page);
          updateMore();
        }
      }

      function loadItems() {
        ++loadToken;
        items = [];
        offset = 0;
        done = false;
        busy = false;
        if (!selectedItemId && activeTab === "items") renderContent();
        return fetchMore();
      }

      function setupItemsView() {
        if (observer) observer.disconnect();
        content.innerHTML = `<div class="rw-grid"></div><div class="rw-more muted"></div>`;
        appendCards(items);
        observer = new IntersectionObserver((en) => {
          if (en.some((x) => x.isIntersecting)) fetchMore();
        }, { rootMargin: "400px" });
        updateMore();
      }

      // Catalogo: stato, aggiornamento e polling
      let pollTimer = null;
      let wasRefreshing = false;

      function showStatus(st) {
        const el = toolbar.querySelector(".rw-cat-status");
        if (!el) return;
        const refreshing = !!st?.refreshing;
        let msg;
        if (refreshing) {
          const pr = st.progress;
          msg = t("st.refreshing") + (pr != null && pr !== "" ? ` (${typeof pr === "number" && pr <= 1 ? Math.round(pr * 100) + "%" : pr})` : "");
        } else if (st?.updated_at) {
          msg = t("st.updated", { data: new Date(Number(st.updated_at) * 1000).toLocaleString(ctx.lang) });
        } else {
          msg = t("st.never");
        }
        if (st?.last_error) msg += " · " + t("st.error", { err: st.last_error });
        el.textContent = msg;
        el.classList.toggle("rw-error", !!st?.last_error);
        const b = toolbar.querySelector(".rw-refresh");
        if (b) b.disabled = refreshing;
      }

      async function pollStatus() {
        clearTimeout(pollTimer);
        pollTimer = null;
        if (!root.isConnected || document.hidden) return; // pagina lasciata o nascosta (riparte da visibilitychange)
        let st = null;
        try {
          st = await gs.api(`${apiBase}/catalog/status`);
        } catch { /* backend non pronto */ }
        if (!root.isConnected) return;
        showStatus(st);
        const refreshing = !!st?.refreshing;
        if (wasRefreshing && !refreshing) loadItems();
        wasRefreshing = refreshing;
        if (refreshing) pollTimer = setTimeout(pollStatus, 2000);
      }

      async function refreshCatalog() {
        try {
          const st = await gs.api(`${apiBase}/catalog/refresh`, { body: {} });
          wasRefreshing = true;
          showStatus(st);
        } catch (e) {
          if (typeof gs?.toast === "function") gs.toast(t("refresh.fail", { err: e.message }), true);
          return;
        }
        pollStatus();
      }

      document.addEventListener("visibilitychange", () => {
        if (!document.hidden && root.isConnected) pollStatus();
      });

      // Carica dettaglio elemento
      async function loadDetail(itemId) {
        selectedItemId = itemId;
        selectedItemDetail = null;
        loading = true;
        renderContent();

        try {
          const res = await gs.api(`${apiBase}/detail?id=${encodeURIComponent(itemId)}`);
          selectedItemDetail = res && typeof res === "object" ? res : null;
        } catch (e) {
          selectedItemDetail = null;
          if (typeof gs?.toast === "function") gs.toast(t("detail.fail", { err: e.message }), true);
        } finally {
          loading = false;
          renderContent();
        }
      }

      // Riproduce elemento o episodio
      async function playItem(itemId) {
        try {
          const target = await gs.api(`${apiBase}/play_target?id=${encodeURIComponent(itemId)}`);
          if (target?.url) {
            await openUrl(target.url);
          } else {
            throw new Error(t("play.nourl"));
          }
        } catch (e) {
          if (typeof gs?.toast === "function") {
            gs.toast(t("play.fail", { err: e.message }), true);
          }
        }
      }

      // Barra strumenti: costruita una volta (la ricerca non perde il focus)
      toolbar.innerHTML = `
        <div class="rw-tabs" role="tablist">
          <button type="button" role="tab" class="rw-tab" data-tab="items">🎬 ${esc(t("tab.items"))}</button>
          <button type="button" role="tab" class="rw-tab" data-tab="recipe_preview">📋 ${esc(t("tab.recipe"))}</button>
        </div>
        <div class="rw-search-box">
          <input type="search" class="rw-search" placeholder="${esc(t("search"))}" aria-label="${esc(t("search"))}">
        </div>
        <div class="rw-catalog">
          <span class="rw-cat-status muted"></span>
          <button type="button" class="rw-btn rw-sm rw-refresh" data-refresh>⟳ ${esc(t("refresh"))}</button>
        </div>`;
      function renderToolbar() {
        toolbar.querySelectorAll(".rw-tab").forEach((b) => b.classList.toggle("rw-active", b.dataset.tab === activeTab));
      }

      // Disegna elenco sorgenti
      function renderSources() {
        if (!recipes.length) {
          sourcesBar.innerHTML = "";
          return;
        }
        const activeRec = recipes.find((r) => r.id === activeRecipeId);
        const siteBtn = activeRec?.start_url
          ? `<button type="button" class="rw-btn rw-sm rw-site-btn" data-open-url="${esc(safeUrl(activeRec.start_url))}" title="${esc(t("site.title"))}">↗ ${esc(t("site"))}</button>`
          : "";

        sourcesBar.innerHTML = `
          <div class="rw-sources-label">${esc(t("sources"))}</div>
          <div class="rw-chips">
            <button type="button" class="rw-chip ${!activeRecipeId ? 'rw-active' : ''}" data-recipe="">${esc(t("all"))}</button>
            ${recipes.map((r) => `
              <button type="button" class="rw-chip ${r.id === activeRecipeId ? 'rw-active' : ''}" data-recipe="${esc(r.id)}">
                ${esc(r.name)}
              </button>
            `).join("")}
          </div>
          ${siteBtn}
        `;
      }

      // Disegna dettaglio con episodi
      function renderDetail() {
        if (loading && !selectedItemDetail) {
          return `<div class="rw-loading"><p class="muted">${esc(t("detail.loading"))}</p></div>`;
        }
        if (!selectedItemDetail) {
          return `
            <div class="rw-empty">
              <button type="button" class="rw-btn rw-back-btn" data-back-to-list>← ${esc(t("back"))}</button>
              <p class="muted rw-gap">${esc(t("notfound"))}</p>
            </div>
          `;
        }

        const det = selectedItemDetail;
        const poster = safeUrl(det.poster || det.backdrop);
        const icon = det.kind === 'brano' ? '🎵' : '🎬';
        const metaParts = [];
        if (det.year) metaParts.push(esc(det.year));
        if (det.duration) metaParts.push(esc(formatDuration(det.duration)));
        if (det.kind) metaParts.push(`<span class="rw-badge">${esc(kindLabel(det.kind))}</span>`);

        const episodes = Array.isArray(det.episodes) ? det.episodes : [];

        return `
          <div class="rw-detail">
            <div>
              <button type="button" class="rw-btn rw-back-btn" data-back-to-list>← ${esc(t("back"))}</button>
            </div>
            <div class="rw-detail-header">
              <div class="rw-detail-poster">
                ${poster ? `<img class="rw-detail-poster-img" src="${esc(poster)}" alt="">` : `<div class="rw-poster-placeholder">${icon}</div>`}
              </div>
              <div class="rw-detail-info">
                <h2 class="rw-detail-title">${esc(det.title)}</h2>
                ${det.series ? `<div class="rw-detail-series">${esc(det.series)}</div>` : ''}
                <div class="rw-meta">${metaParts.join(" · ")}</div>
                ${det.overview ? `<p class="rw-detail-overview">${esc(det.overview)}</p>` : ''}
                <div class="rw-detail-actions">
                  <button type="button" class="rw-btn rw-primary" data-play-id="${esc(det.id)}">▶ ${esc(t("play"))}</button>
                  ${det.url ? `<button type="button" class="rw-btn" data-open-url="${esc(safeUrl(det.url))}">↗ ${esc(t("original"))}</button>` : ''}
                </div>
              </div>
            </div>

            ${episodes.length ? `
              <div class="rw-episodes-section">
                <h3 class="rw-episodes-title">${esc(t("episodes", { n: episodes.length }))}</h3>
                <div class="rw-episode-list">
                  ${episodes.map((ep, idx) => {
                    const epMeta = [];
                    if (ep.duration) epMeta.push(esc(formatDuration(ep.duration)));
                    const epNum = ep.episode != null ? esc(t("ep", { n: ep.episode })) : `#${idx + 1}`;
                    const seasonPrefix = ep.season != null ? `S${esc(ep.season)} ` : '';

                    return `
                      <div class="rw-episode-item" data-play-id="${esc(ep.id)}">
                        <div class="rw-episode-badge">${seasonPrefix}${epNum}</div>
                        <div class="rw-episode-info">
                          <h4 class="rw-episode-title" title="${esc(ep.title)}">${esc(ep.title)}</h4>
                          ${epMeta.length ? `<div class="rw-meta">${epMeta.join(" · ")}</div>` : ''}
                        </div>
                        <button type="button" class="rw-btn rw-sm rw-primary" data-play-id="${esc(ep.id)}">▶ ${esc(t("play"))}</button>
                      </div>
                    `;
                  }).join("")}
                </div>
              </div>
            ` : ''}
          </div>
        `;
      }

      // Disegna anteprima ricetta (campi estratti in tabella)
      function renderRecipePreview() {
        if (!recipes.length) {
          return `
            <div class="rw-empty">
              <p class="muted">${esc(t("recipes.none"))}</p>
            </div>
          `;
        }

        const targetRecipe = recipes.find((r) => r.id === activeRecipeId) || recipes[0];
        if (!targetRecipe) {
          return `<div class="rw-empty"><p class="muted">${esc(t("recipe.none"))}</p></div>`;
        }

        // Righe per la tabella dei campi estratti
        const rows = [
          { sec: t("sec.general"), field: "name", val: targetRecipe.name },
          { sec: t("sec.general"), field: "host", val: targetRecipe.host },
          { sec: t("sec.general"), field: "type", val: targetRecipe.type },
          { sec: t("sec.general"), field: "start_url", val: targetRecipe.start_url, isUrl: true },
        ];

        if (targetRecipe.list) {
          for (const [k, v] of Object.entries(targetRecipe.list)) {
            rows.push({ sec: "[list]", field: k, val: v });
          }
        }
        if (targetRecipe.detail) {
          for (const [k, v] of Object.entries(targetRecipe.detail)) {
            rows.push({ sec: "[detail]", field: k, val: v });
          }
        }
        if (targetRecipe.episodes) {
          for (const [k, v] of Object.entries(targetRecipe.episodes)) {
            rows.push({ sec: "[episodes]", field: k, val: v });
          }
        }
        if (targetRecipe.pagination) {
          for (const [k, v] of Object.entries(targetRecipe.pagination)) {
            rows.push({ sec: "[pagination]", field: k, val: v });
          }
        }

        return `
          <div class="rw-preview">
            <div class="rw-preview-header">
              <div class="rw-preview-title-row">
                <h3 class="rw-preview-title">${esc(t("recipe.title", { nome: targetRecipe.name }))}</h3>
                <span class="rw-badge">${esc(String(targetRecipe.type || "").toUpperCase())}</span>
              </div>
              <div class="rw-meta">
                <span>${esc(t("host"))} <strong>${esc(targetRecipe.host)}</strong></span>
                <span>·</span>
                <span>${esc(t("starturl"))} <a href="#" class="rw-link" data-open-url="${esc(safeUrl(targetRecipe.start_url))}">${esc(targetRecipe.start_url)}</a></span>
              </div>
            </div>

            <h4 class="rw-section-subtitle">${esc(t("rules"))}</h4>
            <div class="rw-table-container">
              <table class="rw-table">
                <thead>
                  <tr>
                    <th>${esc(t("th.section"))}</th>
                    <th>${esc(t("th.field"))}</th>
                    <th>${esc(t("th.rule"))}</th>
                  </tr>
                </thead>
                <tbody>
                  ${rows.map((r) => {
                    const valHtml = r.isUrl && safeUrl(r.val)
                      ? `<a href="#" class="rw-link" data-open-url="${esc(safeUrl(r.val))}">${esc(r.val)}</a>`
                      : `<code>${esc(typeof r.val === 'object' ? JSON.stringify(r.val) : String(r.val ?? ''))}</code>`;
                    return `
                      <tr>
                        <td><strong>${esc(r.sec)}</strong></td>
                        <td>${esc(r.field)}</td>
                        <td>${valHtml}</td>
                      </tr>
                    `;
                  }).join("")}
                </tbody>
              </table>
            </div>
          </div>
        `;
      }

      // Render generale del contenuto
      function renderContent() {
        renderToolbar();
        renderSources();

        if (activeTab === "recipe_preview") {
          content.innerHTML = renderRecipePreview();
        } else if (selectedItemId) {
          content.innerHTML = renderDetail();
        } else {
          setupItemsView();
        }
      }

      // Event delegation sul nodo radice
      root.onclick = async (e) => {
        // Apri URL esterno
        const openEl = e.target.closest("[data-open-url]");
        if (openEl) {
          e.preventDefault();
          e.stopPropagation();
          await openUrl(openEl.dataset.openUrl);
          return;
        }

        if (e.target.closest("[data-refresh]")) {
          e.stopPropagation();
          await refreshCatalog();
          return;
        }

        // Cambio tab
        const tabEl = e.target.closest("[data-tab]");
        if (tabEl) {
          e.stopPropagation();
          activeTab = tabEl.dataset.tab;
          selectedItemId = null;
          selectedItemDetail = null;
          renderContent();
          return;
        }

        // Cambio sorgente
        const chipEl = e.target.closest("[data-recipe]");
        if (chipEl) {
          e.stopPropagation();
          activeRecipeId = chipEl.dataset.recipe;
          selectedItemId = null;
          selectedItemDetail = null;
          if (activeTab === "items") {
            await loadItems();
          } else {
            renderContent();
          }
          return;
        }

        // Torna alla lista da dettaglio
        const backEl = e.target.closest("[data-back-to-list]");
        if (backEl) {
          e.stopPropagation();
          selectedItemId = null;
          selectedItemDetail = null;
          renderContent();
          return;
        }

        // Riproduzione
        const playBtn = e.target.closest("[data-play-id]");
        if (playBtn) {
          e.stopPropagation();
          await playItem(playBtn.dataset.playId);
          return;
        }

        // Clic su card per dettaglio
        const cardEl = e.target.closest("[data-item-id]");
        if (cardEl) {
          e.stopPropagation();
          await loadDetail(cardEl.dataset.itemId);
          return;
        }
      };

      // Supporto tastiera (Enter su card)
      root.onkeydown = async (e) => {
        if (e.key === "Enter" || e.key === " ") {
          const cardEl = e.target.closest("[data-item-id]");
          if (cardEl) {
            e.preventDefault();
            await loadDetail(cardEl.dataset.itemId);
          }
        }
      };

      // Ricerca con debounce
      let searchTimer;
      root.oninput = (e) => {
        if (e.target.classList.contains("rw-search")) {
          clearTimeout(searchTimer);
          searchTimer = setTimeout(() => {
            currentQuery = e.target.value.trim();
            selectedItemId = null;
            selectedItemDetail = null;
            loadItems();
          }, 250);
        }
      };

      // Avvio: carica ricette e primo set di elementi
      await loadRecipes();
      pollStatus();
      await loadItems();
    },
  });
}
