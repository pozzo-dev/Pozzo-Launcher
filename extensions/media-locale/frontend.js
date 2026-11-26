// Media locale: vista media center unificata stile Netflix (Hero cinematografica, Caroselli, Modal Dettaglio, Impostazioni Drawer).
import * as logicaModule from "./logica.js";
import {
  formatDuration,
  resumeOf,
  isSeen,
  groupEpisodes,
  nextEpisode,
  compositeKey,
  sourceBadge,
  filterHubItems,
  mergeContinueWatching,
  pickHeroItem,
  federatedList,
  categoryOf,
  matchLibraryItem,
  WATCHLIST_CATEGORIES,
  saveCatalogSnapshot,
  loadCatalogSnapshot,
  mergeWatchlists,
  collapseSingleEpisodeSeries,
  seriesSummary,
  activeProfile,
  profileKey,
  migrateToProfileKey,
} from "./logica.js";
import * as playerModule from "./player.js";
import { attachPlay, play, loadContinueCache, removeFromContinueCache, animateSpinners, takeHandoff, HANDOFF_KEY, setPlayerT } from "./player.js";

// testi: ctx.t arriva in default(); setT serve ai test che usano gli helper da soli
let tr = (k) => k;
let lang;
export const setT = (fn, l) => { tr = fn; lang = l; };
const tx = (k, p) => String(tr(k, p)).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const BADGE_KEYS = { "Disco Locale": "src.disk", "Web / Streaming": "src.web" };
const badgeText = (b) => (b?.label ? b.label.split(" · ").map((x) => (BADGE_KEYS[x] ? tr(BADGE_KEYS[x]) : x)).join(" · ") : "");

export const WATCHLIST_STATUSES = logicaModule.WATCHLIST_STATUSES || {
  plan_to_watch: { id: "plan_to_watch", label: "Da guardare", icon: "📌", order: 1 },
  watching: { id: "watching", label: "In corso", icon: "▶", order: 2 },
  on_hold: { id: "on_hold", label: "In pausa", icon: "⏸", order: 3 },
  completed: { id: "completed", label: "Completato", icon: "✓", order: 4 },
  dropped: { id: "dropped", label: "Abbandonato", icon: "✕", order: 5 },
};

export const WATCHLIST_PRIORITIES = logicaModule.WATCHLIST_PRIORITIES || {
  high: { id: "high", label: "Alta", icon: "🔥", weight: 3 },
  medium: { id: "medium", label: "Media", icon: "⚡", weight: 2 },
  low: { id: "low", label: "Bassa", icon: "💤", weight: 1 },
};

export const normalizeWatchlistEntry = logicaModule.normalizeWatchlistEntry || function (entry, itemFallback = null) {
  const e = entry && typeof entry === "object" ? entry : {};
  const fb = itemFallback && typeof itemFallback === "object" ? itemFallback : {};
  const source = String(e.source || fb.source || "media-locale").trim() || "media-locale";
  const rawId = e.item_id ?? e.id ?? fb.item_id ?? fb.id ?? "";
  let itemId = String(rawId).trim();
  if (itemId === "undefined" || itemId === "null") itemId = "";
  let itemKey = String(e.item_key || "").trim();
  if (!itemKey) {
    itemKey = (compositeKey ? compositeKey({ id: itemId || e.id, source }) : `${source}:${itemId}`) || (compositeKey ? compositeKey(fb) : "");
  }
  if (!itemId && itemKey.includes(":")) {
    itemId = itemKey.split(":", 2)[1] || "";
  }
  const title = String(e.title || fb.title || itemId || itemKey || "").trim();
  const kind = String(e.kind || fb.kind || "film").trim() || "film";
  const series = String(e.series ?? fb.series ?? "").trim();
  const poster = String(e.poster ?? fb.poster ?? "").trim();
  const backdrop = String(e.backdrop ?? fb.backdrop ?? "").trim();
  const genre = String(e.genre ?? e.genres ?? fb.genre ?? fb.genres ?? "").trim();
  const overview = String(e.overview ?? fb.overview ?? "").trim();
  const url = String(e.url ?? fb.url ?? "").trim();
  const rawYear = e.year != null && e.year !== "" ? e.year : fb.year;
  const parsedYear = rawYear != null && rawYear !== "" && Number.isFinite(Number(rawYear)) ? Math.trunc(Number(rawYear)) : null;
  const statusKey = String(e.status || "").trim();
  const status = WATCHLIST_STATUSES[statusKey] ? statusKey : "plan_to_watch";
  const prioKey = String(e.priority || "").trim();
  const priority = WATCHLIST_PRIORITIES[prioKey] ? prioKey : "medium";
  const rawRating = Number(e.rating ?? 0);
  const rating = Number.isFinite(rawRating) ? Math.min(10, Math.max(0, Math.round(rawRating))) : 0;
  const notes = e.notes != null ? String(e.notes) : "";
  const added_at = Number.isFinite(Number(e.added_at)) ? Number(e.added_at) : 0;
  const updated_at = Number.isFinite(Number(e.updated_at)) ? Number(e.updated_at) : added_at;
  return {
    ...fb,
    ...e,
    item_key: itemKey,
    item_id: itemId,
    id: itemId || e.id || fb.id || itemKey,
    source,
    title,
    kind,
    series,
    poster,
    backdrop,
    year: parsedYear,
    genre,
    overview,
    url,
    status,
    priority,
    rating,
    notes,
    added_at,
    updated_at,
  };
};

export const sortAndFilterWatchlist = logicaModule.sortAndFilterWatchlist || function (entries, { status = "all", priority = "all", query = "", sortBy = "priority" } = {}) {
  const list = Array.isArray(entries) ? entries : [];
  const stFilter = String(status || "all").trim();
  const prFilter = String(priority || "all").trim();
  const q = String(query || "").trim().toLowerCase();
  const sortMode = String(sortBy || "priority").trim();
  const filtered = list.filter((raw) => {
    if (!raw) return false;
    const e = normalizeWatchlistEntry(raw);
    if (stFilter && stFilter !== "all") {
      if (stFilter === "active") {
        if (e.status === "completed" || e.status === "dropped") return false;
      } else if (e.status !== stFilter) return false;
    }
    if (prFilter && prFilter !== "all" && e.priority !== prFilter) return false;
    if (q) {
      const hay = [e.title, e.series, e.notes, e.genre, e.overview].map((v) => String(v || "").toLowerCase());
      if (!hay.some((f) => f.includes(q))) return false;
    }
    return true;
  });
  const weightOf = (e) => WATCHLIST_PRIORITIES[e?.priority]?.weight ?? 2;
  const orderOf = (e) => WATCHLIST_STATUSES[e?.status]?.order ?? 1;
  const isFinished = (e) => e?.status === "completed" || e?.status === "dropped";
  const recencyOf = (e) => Number(e?.updated_at || e?.added_at || 0);
  return filtered.slice().sort((a, b) => {
    if (sortMode === "status") return (orderOf(a) - orderOf(b)) || (weightOf(b) - weightOf(a)) || String(a?.title || "").localeCompare(String(b?.title || ""));
    if (sortMode === "rating") return (Number(b?.rating || 0) - Number(a?.rating || 0)) || (weightOf(b) - weightOf(a)) || String(a?.title || "").localeCompare(String(b?.title || ""));
    if (sortMode === "recent") return (recencyOf(b) - recencyOf(a)) || String(a?.title || "").localeCompare(String(b?.title || ""));
    if (sortMode === "title") return String(a?.title || "").localeCompare(String(b?.title || ""));
    return ((isFinished(a) ? 1 : 0) - (isFinished(b) ? 1 : 0)) || (weightOf(b) - weightOf(a)) || (Number(b?.updated_at || 0) - Number(a?.updated_at || 0)) || String(a?.title || "").localeCompare(String(b?.title || ""));
  });
};

export const watchlistStats = logicaModule.watchlistStats || function (entries) {
  const stats = { total: 0, plan_to_watch: 0, watching: 0, on_hold: 0, completed: 0, dropped: 0, high_priority: 0 };
  for (const raw of entries || []) {
    if (!raw) continue;
    const st = WATCHLIST_STATUSES[raw.status] ? raw.status : "plan_to_watch";
    const pr = WATCHLIST_PRIORITIES[raw.priority] ? raw.priority : "medium";
    stats.total += 1;
    stats[st] += 1;
    if (pr === "high") stats.high_priority += 1;
  }
  return stats;
};

export const isHttpUrl = (u) => /^https?:\/\//i.test(String(u || ""));

export const safeMediaUrl = (u) => {
  const s = String(u || "").trim();
  return /^https?:\/\//i.test(s) || s.startsWith("/") ? s : "";
};

const defaultEsc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));

const FAVS_KEY = "pm_favorites";

/** Chiave (senza «gs.») per profilo di un dato salvato in localStorage, con migrazione della vecchia chiave globale. */
function pkey(base) {
  try { return migrateToProfileKey(localStorage, "gs." + base).slice(3); } catch { return profileKey(base); }
}

// Preferenze del lettore: le chiavi sono quelle di player.js; se non esporta le funzioni vale questo ripiego.
const PREF_DEFAULTS = { autonext: true, skipIntro: false, skipSecs: 85 };
export function loadPlayerPrefsCompat(storage) {
  if (typeof playerModule.loadPlayerPrefs === "function") return playerModule.loadPlayerPrefs(storage);
  const st = storage || (typeof localStorage !== "undefined" ? localStorage : null);
  const rd = (k) => { try { return st?.getItem(k); } catch { return null; } };
  const secs = Number(rd("gs.pm_skip_secs"));
  return {
    autonext: rd("gs.pm_autonext") == null ? PREF_DEFAULTS.autonext : rd("gs.pm_autonext") !== "0",
    skipIntro: rd("gs.pm_skip_intro") === "1",
    skipSecs: secs >= 5 && secs <= 600 ? Math.round(secs) : PREF_DEFAULTS.skipSecs,
  };
}
export function savePlayerPrefsCompat(patch, storage) {
  if (typeof playerModule.savePlayerPrefs === "function") return playerModule.savePlayerPrefs(patch, storage);
  const st = storage || (typeof localStorage !== "undefined" ? localStorage : null);
  const wr = (k, v) => { try { st?.setItem(k, v); } catch { /* storage pieno */ } };
  if ("autonext" in patch) wr("gs.pm_autonext", patch.autonext ? "1" : "0");
  if ("skipIntro" in patch) wr("gs.pm_skip_intro", patch.skipIntro ? "1" : "0");
  if ("skipSecs" in patch) wr("gs.pm_skip_secs", String(Math.min(600, Math.max(5, Math.round(Number(patch.skipSecs) || PREF_DEFAULTS.skipSecs)))));
}

function loadFavs(gs) {
  try {
    const k = pkey(FAVS_KEY);
    const list = gs?.store?.get ? gs.store.get(k, []) : JSON.parse(localStorage.getItem("gs." + k) || "[]");
    return new Set(Array.isArray(list) ? list : []);
  } catch {
    return new Set();
  }
}

function saveFavs(gs, favs) {
  const arr = [...favs];
  const k = pkey(FAVS_KEY);
  try { if (gs?.store?.set) gs.store.set(k, arr); } catch {}
  try { localStorage.setItem("gs." + k, JSON.stringify(arr)); } catch {}
}

export function isAnimeItem(item) {
  if (!item) return false;
  if (item.kind === "anime" || item.category === "anime") return true;
  const provId = String(item.channel_id || item.recipe_id || item.source_label || item.id || "").toLowerCase();
  const url = String(item.url || "").toLowerCase();
  if (
    provId.includes("animeunity") ||
    provId.includes("animeworld") ||
    url.includes("animeunity") ||
    url.includes("animeworld")
  ) {
    return true;
  }
  if (
    provId.includes("streamingcommunity") ||
    provId.includes("altadefinizione01") ||
    url.includes("streamingcommunity") ||
    url.includes("altadefinizione")
  ) {
    const g = String(item.genre || item.genres || "").toLowerCase();
    return g.includes("anime") || g.includes("animazione");
  }
  const g = String(item.genre || item.genres || "").toLowerCase();
  if (g.includes("anime") || g.includes("animazione")) return true;
  const s = (String(item.title || "") + " " + String(item.series || "")).toLowerCase();
  const animeKeywords = [
    "one piece", "naruto", "dragon ball", "bleach", "attack on titan",
    "shingeki", "death note", "jujutsu", "demon slayer", "kimetsu",
    "my hero academia", "boku no hero", "hunter x hunter", "fullmetal",
    "chainsaw man", "spy x family", "tokyo ghoul", "evangelion", "sword art online", "frieren"
  ];
  return animeKeywords.some((kw) => s.includes(kw));
}

export function isStream4meItem(item) {
  if (!item) return false;
  const s = String(item.source || "").toLowerCase();
  const a = String(item.addon || "").toLowerCase();
  const id = String(item.id || "").toLowerCase();
  return s === "stream4me" || s === "s4me" || a.includes("stream4me") || s.includes("kodi") || id.startsWith("s4me:") || id.startsWith("stream4me:") || id.startsWith("s4m:") || id.startsWith("kodi:");
}

export function normalizePlayItem(item) {
  if (!item || typeof item !== "object") return item;
  const s = String(item.source || "").toLowerCase();
  const id = String(item.id || "").toLowerCase();
  if (
    isStream4meItem(item) ||
    s === "web" ||
    s.includes("ricette") ||
    id.startsWith("s4me:") ||
    id.startsWith("stream4me:") ||
    id.startsWith("s4m:") ||
    id.startsWith("kodi:") ||
    id.startsWith("recipe:")
  ) {
    return { ...item, source: "ricette-web" };
  }
  return item;
}

export function deduplicateStream4meEpisodes(episodes, parentItem = null, fallbackSeriesTitle = "") {
  if (!Array.isArray(episodes) || !episodes.length) return [];
  const p = parentItem && typeof parentItem === "object" ? parentItem : {};
  const seriesTitle = String(fallbackSeriesTitle || p.series || p.title || "").trim();
  const seenKeys = new Set();
  const out = [];
  episodes.forEach((ep, idx) => {
    if (!ep) return;
    const season = ep.season != null && !Number.isNaN(Number(ep.season)) ? Number(ep.season) : 1;
    const epNum = ep.episode != null && !Number.isNaN(Number(ep.episode)) ? Number(ep.episode) : (idx + 1);
    const dedupKey = `${season}:${epNum}`;
    if (seenKeys.has(dedupKey)) return;
    seenKeys.add(dedupKey);
    out.push({
      ...ep,
      id: ep.id ?? `${p.id || "s4m"}_ep_${idx + 1}`,
      title: ep.title || tr("ep.n", { n: epNum }),
      series: ep.series || seriesTitle,
      kind: ep.kind || "episodio",
      genre: ep.genre || p.genre || "",
      season,
      episode: epNum,
      poster: ep.poster || p.poster,
      backdrop: ep.backdrop || p.backdrop || p.poster,
      overview: ep.overview || "",
      source: ep.source || "stream4me",
    });
  });
  return out;
}

export function renderWatchlistControlsHtml(itemKey, entry = null, esc = defaultEsc) {
  const k = String(itemKey ?? "");
  if (!k) return "";
  if (!entry) {
    return `
      <div class="pm-wl-controls">
        <button type="button" class="pm-player-btn pm-primary" data-wl-add="${esc(k)}">📋 ＋ ${tx("wl.add")}</button>
        <button type="button" class="pm-player-btn" data-wl-add="${esc(k)}" data-wl-add-priority="high" title="${tx("wl.addPrio.high")}">🔥 ${tx("prio.high")}</button>
        <button type="button" class="pm-player-btn" data-wl-add="${esc(k)}" data-wl-add-priority="medium" title="${tx("wl.addPrio.medium")}">⚡ ${tx("prio.medium")}</button>
        <button type="button" class="pm-player-btn" data-wl-add="${esc(k)}" data-wl-add-priority="low" title="${tx("wl.addPrio.low")}">💤 ${tx("prio.low")}</button>
      </div>
    `.trim();
  }

  const norm = normalizeWatchlistEntry(entry, { item_key: k });
  const ratingOptions = [`<option value="0" ${!norm.rating ? "selected" : ""}>${tx("wl.noRating")}</option>`];
  for (let r = 1; r <= 10; r++) {
    ratingOptions.push(`<option value="${r}" ${norm.rating === r ? "selected" : ""}>★ ${r}</option>`);
  }

  return `
    <div class="pm-wl-controls">
      <select class="pm-source-select" data-wl-status="${esc(k)}" aria-label="${tx("wl.status")}">
        <option value="plan_to_watch" ${norm.status === "plan_to_watch" ? "selected" : ""}>📌 ${tx("st.plan_to_watch")}</option>
        <option value="watching" ${norm.status === "watching" ? "selected" : ""}>▶ ${tx("st.watching")}</option>
        <option value="on_hold" ${norm.status === "on_hold" ? "selected" : ""}>⏸ ${tx("st.on_hold")}</option>
        <option value="completed" ${norm.status === "completed" ? "selected" : ""}>✓ ${tx("st.completed")}</option>
        <option value="dropped" ${norm.status === "dropped" ? "selected" : ""}>✕ ${tx("st.dropped")}</option>
      </select>
      <select class="pm-source-select" data-wl-priority="${esc(k)}" aria-label="${tx("wl.priority")}">
        <option value="high" ${norm.priority === "high" ? "selected" : ""}>🔥 ${tx("prio.full.high")}</option>
        <option value="medium" ${norm.priority === "medium" ? "selected" : ""}>⚡ ${tx("prio.full.medium")}</option>
        <option value="low" ${norm.priority === "low" ? "selected" : ""}>💤 ${tx("prio.full.low")}</option>
      </select>
      <select class="pm-source-select" data-wl-rating="${esc(k)}" aria-label="${tx("wl.rating")}">
        ${ratingOptions.join("")}
      </select>
      <input type="text" class="pm-wl-note-input" data-wl-note-input="${esc(k)}" value="${esc(norm.notes || "")}" placeholder="${tx("wl.notePh")}">
      <button type="button" class="pm-player-btn" data-wl-save-note="${esc(k)}">${tx("wl.saveNote")}</button>
      <button type="button" class="pm-player-btn" data-wl-remove="${esc(k)}">✕ ${tx("remove")}</button>
    </div>
  `.trim();
}

export function renderWatchlistViewHtml(entries = [], filterState = {}, esc = defaultEsc) {
  const list = Array.isArray(entries) ? entries : [];
  const statusFilter = filterState?.status || "all";
  const priorityFilter = filterState?.priority || "all";
  const sortBy = filterState?.sortBy || "priority";
  const query = filterState?.query || "";
  const categoryFilter = filterState?.category || "all";

  const stats = watchlistStats(list);
  const filtered = sortAndFilterWatchlist(list, {
    category: categoryFilter,
    status: statusFilter,
    priority: priorityFilter,
    query,
    sortBy,
  });

  const statPills = [
    { status: "all", label: tr("wl.total"), count: stats.total, active: statusFilter === "all" && priorityFilter === "all" },
    { status: "plan_to_watch", label: "📌 " + tr("st.plan_to_watch"), count: stats.plan_to_watch, active: statusFilter === "plan_to_watch" },
    { status: "watching", label: "▶ " + tr("st.watching"), count: stats.watching, active: statusFilter === "watching" },
    { status: "on_hold", label: "⏸ " + tr("st.on_hold"), count: stats.on_hold, active: statusFilter === "on_hold" },
    { status: "completed", label: "✓ " + tr("st.completedPl"), count: stats.completed, active: statusFilter === "completed" },
    { status: "all", priority: "high", label: "🔥 " + tr("prio.filter.high"), count: stats.high_priority, active: priorityFilter === "high" },
  ];

  const statusTabs = [
    { id: "all", label: tr("all") },
    { id: "plan_to_watch", label: "📌 " + tr("st.plan_to_watch") },
    { id: "watching", label: "▶ " + tr("st.watching") },
    { id: "on_hold", label: "⏸ " + tr("st.on_hold") },
    { id: "completed", label: "✓ " + tr("st.completed") },
    { id: "dropped", label: "✕ " + tr("st.dropped") },
  ];

  const catTabs = [
    { id: "all", label: tr("all"), count: stats.total },
    ...Object.values(WATCHLIST_CATEGORIES).map((c) => ({ id: c.id, label: `${c.icon} ${tr("cat." + c.id)}`, count: stats.by_category[c.id] })),
  ];
  const unlinked = list.filter((x) => x && !normalizeWatchlistEntry(x).linked_key).length;

  return `
    <div class="pm-netflix-home">
      <div class="pm-wl-head">
        <div class="pm-season-tabs pm-wl-cats" role="tablist" aria-label="${tx("wl.category")}">
          ${catTabs.map((t) => `
            <button type="button" role="tab" class="pm-season-tab ${categoryFilter === t.id ? "pm-active" : ""}" data-wl-category="${esc(t.id)}">
              ${esc(t.label)} <span class="pm-wl-count">${esc(t.count)}</span>
            </button>
          `).join("")}
        </div>
        <div class="pm-wl-head-actions">
          <button type="button" class="pm-player-btn" data-wl-match ${unlinked ? "" : "disabled"} title="${tx("wl.match.title")}">🔗 ${tx("wl.match")}${unlinked ? ` (${esc(unlinked)})` : ""}</button>
          <button type="button" class="pm-player-btn" data-wl-export title="${tx("wl.export.title")}">⬇ ${tx("wl.export")}</button>
          <button type="button" class="pm-player-btn" data-wl-import-open data-wl-restore title="${tx("wl.restore.title")}">⬆ ${tx("wl.restore")}</button>
          <button type="button" class="pm-player-btn pm-primary" data-wl-import-open>⬇ ${tx("wl.import")}</button>
        </div>
      </div>

      <div class="pm-wl-stats">
        ${statPills.map((p) => `
          <button type="button" class="pm-wl-stat-pill ${p.active ? "pm-active" : ""}" data-wl-filter-status="${esc(p.status)}" ${p.priority ? `data-wl-stat-priority="${esc(p.priority)}"` : ""}>
            <span>${esc(p.label)}</span>
            <strong>${esc(p.count)}</strong>
          </button>
        `).join("")}
      </div>

      <div class="pm-wl-toolbar">
        <div class="pm-season-tabs" role="tablist">
          ${statusTabs.map((t) => `
            <button type="button" role="tab" class="pm-season-tab ${statusFilter === t.id ? "pm-active" : ""}" data-wl-filter-status="${esc(t.id)}">
              ${esc(t.label)}
            </button>
          `).join("")}
        </div>
        <div class="pm-flex-ac-g8-wrap">
          <select class="pm-source-select" data-wl-filter-priority aria-label="${tx("prio.filter")}">
            <option value="all" ${priorityFilter === "all" ? "selected" : ""}>${tx("prio.filter.all")}</option>
            <option value="high" ${priorityFilter === "high" ? "selected" : ""}>🔥 ${tx("prio.filter.high")}</option>
            <option value="medium" ${priorityFilter === "medium" ? "selected" : ""}>⚡ ${tx("prio.filter.medium")}</option>
            <option value="low" ${priorityFilter === "low" ? "selected" : ""}>💤 ${tx("prio.filter.low")}</option>
          </select>
          <select class="pm-source-select" data-wl-sort aria-label="${tx("wl.sort")}">
            <option value="priority" ${sortBy === "priority" ? "selected" : ""}>${tx("sort.priority")}</option>
            <option value="status" ${sortBy === "status" ? "selected" : ""}>${tx("sort.status")}</option>
            <option value="recent" ${sortBy === "recent" ? "selected" : ""}>${tx("sort.recent")}</option>
            <option value="rating" ${sortBy === "rating" ? "selected" : ""}>${tx("sort.rating")}</option>
            <option value="title" ${sortBy === "title" ? "selected" : ""}>${tx("sort.title")}</option>
          </select>
        </div>
      </div>

      ${filtered.length ? `
        <div class="pm-wl-list">
          ${filtered.map((raw) => {
            const e = normalizeWatchlistEntry(raw);
            const k = e.item_key || compositeKey(e) || String(e.id || "");
            const poster = safeMediaUrl(e.poster || e.backdrop);
            const defaultIcon = e.kind === "brano" ? "🎵" : (e.kind === "episodio" ? "📺" : "🎬");
            const badge = badgeOf(e);
            const badgeLabel = badgeText(badge) || e.source || tr("src.local");
            const badgeIcon = badge?.icon ? `${badge.icon} ` : "";
            const prioMeta = WATCHLIST_PRIORITIES[e.priority] || WATCHLIST_PRIORITIES.medium;
            const stMeta = WATCHLIST_STATUSES[e.status] || WATCHLIST_STATUSES.plan_to_watch;
            const catMeta = WATCHLIST_CATEGORIES[e.category] || WATCHLIST_CATEGORIES.film;
            const pct = e.total > 0 ? Math.min(100, Math.round((e.progress / e.total) * 100)) : 0;
            const progressHtml = e.total > 0
              ? `<div class="pm-wl-progress" title="${esc(e.progress)}/${esc(e.total)}"><span class="pm-wl-progress-bar"><i style="width:${pct}%"></i></span><span class="pm-wl-progress-txt">${esc(e.progress)}/${esc(e.total)}</span></div>`
              : (e.progress > 0 ? `<span class="pm-badge">${tx("wl.epSeen", { n: e.progress })}</span>` : "");

            const ratingOpts = [`<option value="0" ${!e.rating ? "selected" : ""}>${tx("wl.noRating")}</option>`];
            for (let r = 1; r <= 10; r++) {
              ratingOpts.push(`<option value="${r}" ${e.rating === r ? "selected" : ""}>★ ${r}</option>`);
            }

            return `
              <article class="pm-wl-card" data-wl-card="${esc(k)}">
                <div class="pm-list-thumb" data-detail-key="${esc(k)}" data-detail-id="${esc(e.id)}" style="width: 64px; height: 92px;">
                  ${poster ? `<img class="pm-list-thumb-img" src="${esc(poster)}" alt="" loading="lazy">` : defaultIcon}
                </div>
                <div class="pm-list-info" style="gap: 6px;">
                  <div class="pm-flex-ac-g8-wrap">
                    <h4 class="pm-list-title" title="${esc(e.title)}" data-detail-key="${esc(k)}" data-detail-id="${esc(e.id)}" style="font-size: 1rem; cursor: pointer;">${esc(e.title)}</h4>
                    <span class="pm-wl-priority-badge pm-wl-priority-${esc(e.priority)}">${esc(prioMeta.icon)} ${tx("prio." + prioMeta.id)}</span>
                    <span class="pm-wl-status-badge">${esc(stMeta.icon)} ${tx("st." + stMeta.id)}</span>
                    <span class="pm-wl-cat-badge">${esc(catMeta.icon)} ${tx("cat." + catMeta.id)}</span>
                    ${e.linked_key
                      ? `<span class="pm-wl-link pm-wl-linked" title="${esc(e.linked_key)}">✓ ${tx("wl.linked")}</span>`
                      : `<span class="pm-wl-link pm-wl-unlinked">${tx("wl.unlinked")}</span>`}
                    <span class="pm-source-badge">${esc(badgeIcon)}${esc(badgeLabel)}</span>
                    ${e.series && e.series !== e.title ? `<span class="pm-badge">${esc(e.series)}</span>` : ""}
                    ${e.year ? `<span class="pm-badge">${esc(e.year)}</span>` : ""}
                    ${e.genre ? `<span class="pm-badge">${esc(e.genre)}</span>` : ""}
                  </div>
                  ${progressHtml}
                  <div class="pm-wl-controls">
                    <select class="pm-source-select" data-wl-status="${esc(k)}" aria-label="${tx("sort.status")}">
                      <option value="plan_to_watch" ${e.status === "plan_to_watch" ? "selected" : ""}>📌 ${tx("st.plan_to_watch")}</option>
                      <option value="watching" ${e.status === "watching" ? "selected" : ""}>▶ ${tx("st.watching")}</option>
                      <option value="on_hold" ${e.status === "on_hold" ? "selected" : ""}>⏸ ${tx("st.on_hold")}</option>
                      <option value="completed" ${e.status === "completed" ? "selected" : ""}>✓ ${tx("st.completed")}</option>
                      <option value="dropped" ${e.status === "dropped" ? "selected" : ""}>✕ ${tx("st.dropped")}</option>
                    </select>
                    <select class="pm-source-select" data-wl-priority="${esc(k)}" aria-label="${tx("wl.priority")}">
                      <option value="high" ${e.priority === "high" ? "selected" : ""}>🔥 ${tx("prio.full.high")}</option>
                      <option value="medium" ${e.priority === "medium" ? "selected" : ""}>⚡ ${tx("prio.full.medium")}</option>
                      <option value="low" ${e.priority === "low" ? "selected" : ""}>💤 ${tx("prio.full.low")}</option>
                    </select>
                    <select class="pm-source-select" data-wl-rating="${esc(k)}" aria-label="${tx("wl.rating")}">
                      ${ratingOpts.join("")}
                    </select>
                    <input type="text" class="pm-wl-note-input" data-wl-note-input="${esc(k)}" value="${esc(e.notes || "")}" placeholder="${tx("wl.notePh")}">
                    <button type="button" class="pm-player-btn" data-wl-save-note="${esc(k)}" style="padding: 4px 10px; font-size: 0.78rem;">${tx("wl.saveNote")}</button>
                  </div>
                </div>
                <div class="pm-list-actions">
                  ${e.linked_key
                    ? `<button type="button" class="pm-player-btn pm-primary" data-wl-play="${esc(e.linked_key)}">▶ ${tx("play")}</button>`
                    : `<button type="button" class="pm-player-btn pm-primary" data-wl-search="${esc(e.title)}" data-wl-search-cat="${esc(e.category)}">🔎 ${tx("search")}</button>`}
                  <button type="button" class="pm-player-btn" data-wl-remove="${esc(k)}" title="${tx("wl.remove")}">✕</button>
                </div>
              </article>
            `;
          }).join("")}
        </div>
      ` : `
        <div class="pm-provider-status">
          <p class="muted pm-m0">${tx("wl.empty")}</p>
        </div>
      `}
    </div>
  `.trim();
}

const WL_IMPORT_PROVIDERS = {
  anilist: { label: "AniList", hint: "wli.hint.anilist", input: "user" },
  mal: { label: "MyAnimeList", hint: "wli.hint.mal", input: "file", accept: ".xml,text/xml" },
  csv: { label: "Trakt / Letterboxd (CSV)", hint: "wli.hint.csv", input: "file", accept: ".csv,text/csv" },
  json: { label: "Trakt (JSON)", hint: "wli.hint.json", input: "file", accept: ".json,application/json" },
  pozzo: { label: "wli.label.pozzo", hint: "wli.hint.pozzo", input: "file", accept: ".json,application/json" },
  text: { label: "wli.label.text", hint: "wli.hint.text", input: "text" },
};

/** Dialogo «Importa watchlist». state: {provider, username, content, filename, prepared, skipped, warnings, defaultCat, busy, error}. */
export function renderWatchlistImportDialogHtml(state = {}, esc = defaultEsc) {
  const st = state || {};
  const provider = WL_IMPORT_PROVIDERS[st.provider] ? st.provider : "anilist";
  const meta = WL_IMPORT_PROVIDERS[provider];
  const prepared = Array.isArray(st.prepared) ? st.prepared : null;
  const defCat = WATCHLIST_CATEGORIES[st.defaultCat] ? st.defaultCat : "serie";
  const countBy = (fn) => { const m = {}; for (const e of prepared || []) { const k = fn(e); m[k] = (m[k] || 0) + 1; } return m; };

  let preview = "";
  if (prepared) {
    const byCat = countBy((e) => e.category);
    const bySt = countBy((e) => e.status);
    const linked = prepared.filter((e) => e.linked_key).length;
    const warnings = Array.isArray(st.warnings) ? st.warnings : [];
    preview = `
      <div class="pm-settings-section pm-wli-preview">
        <strong>${tx("wli.preview", { n: prepared.length })}</strong>
        <div class="pm-wli-line">${Object.values(WATCHLIST_CATEGORIES).map((c) => `<span class="pm-wl-cat-badge">${esc(c.icon)} ${tx("cat." + c.id)}: ${esc(byCat[c.id] || 0)}</span>`).join(" ")}</div>
        <div class="pm-wli-line">${Object.values(WATCHLIST_STATUSES).filter((x) => bySt[x.id]).map((x) => `<span class="pm-wl-status-badge">${esc(x.icon)} ${tx("st." + x.id)}: ${esc(bySt[x.id])}</span>`).join(" ")}</div>
        <div class="pm-wli-line"><span class="pm-wl-link pm-wl-linked">✓ ${tx("wli.linked", { n: linked })}</span> <span class="pm-wl-link pm-wl-unlinked">${tx("wli.unlinked", { n: prepared.length - linked })}</span>${st.skipped ? ` <span class="muted">${tx("wli.skipped", { n: Array.isArray(st.skipped) ? st.skipped.length : st.skipped })}</span>` : ""}</div>
        ${warnings.length ? `<ul class="pm-wli-warnings">${warnings.slice(0, 8).map((w) => `<li>${esc(typeof w === "string" ? w : (w?.message || JSON.stringify(w)))}</li>`).join("")}${warnings.length > 8 ? `<li>${tx("wli.moreWarnings", { n: warnings.length - 8 })}</li>` : ""}</ul>` : ""}
        <label class="pm-wli-field">${tx("wli.defCat")}
          <select class="pm-source-select" data-wli-defcat>
            ${Object.values(WATCHLIST_CATEGORIES).map((c) => `<option value="${esc(c.id)}" ${defCat === c.id ? "selected" : ""}>${esc(c.icon)} ${tx("cat." + c.id)}</option>`).join("")}
          </select>
        </label>
      </div>`;
  }

  return `
    <div class="pm-settings-overlay" data-close-settings-backdrop>
      <div class="pm-settings-modal" role="dialog" aria-modal="true" aria-label="${tx("wl.import")}">
        <div class="pm-settings-header">
          <h3 class="pm-settings-title">⬇ ${tx("wl.import")}</h3>
          <button type="button" class="pm-modal-close" data-close-settings style="position: static;" title="${tx("close")}">✕</button>
        </div>
        <div class="pm-settings-content">
          <div class="pm-settings-section">
            <label class="pm-wli-field">${tx("wli.service")}
              <select class="pm-source-select" data-wli-provider>
                ${Object.entries(WL_IMPORT_PROVIDERS).map(([id, p]) => `<option value="${esc(id)}" ${provider === id ? "selected" : ""}>${esc(p.label.startsWith("wli.") ? tr(p.label) : p.label)}</option>`).join("")}
              </select>
            </label>
            <p class="muted pm-f555">${tx(meta.hint)}</p>
            ${meta.input === "user" ? `<input type="text" class="pm-wl-note-input" style="max-width:none;" data-wli-username value="${esc(st.username || "")}" placeholder="${tx("wli.user")}" autocomplete="off">` : ""}
            ${meta.input === "file" ? `<input type="file" data-wli-file accept="${esc(meta.accept)}">${st.filename ? ` <span class="muted">${esc(st.filename)}</span>` : ""}` : ""}
            ${meta.input === "text" ? `<textarea class="pm-wli-text" data-wli-text rows="8" placeholder="${tx("wli.hint.text")}">${esc(st.content || "")}</textarea>` : ""}
            <p class="muted pm-c94d">${tx("wli.privacy")}</p>
          </div>
          ${st.error ? `<div class="pm-wli-error" role="alert">⚠ ${esc(st.error)}</div>` : ""}
          ${preview}
          <div class="pm-wli-actions">
            <button type="button" class="pm-player-btn" data-wli-analyze ${st.busy ? "disabled" : ""}>${st.busy === "analyze" ? tx("wli.analyzing") : tx("wli.analyze")}</button>
            ${prepared && prepared.length ? `<button type="button" class="pm-player-btn pm-primary" data-wli-commit ${st.busy ? "disabled" : ""}>${st.busy === "commit" ? tx("wli.importing") : tx("wli.commit", { n: prepared.length })}</button>` : ""}
          </div>
        </div>
      </div>
    </div>
  `.trim();
}

export function renderHeroHtml(item, esc = defaultEsc) {
  if (!item) return "";
  const key = compositeKey ? compositeKey(item) : `${item.source || "locale"}:${item.id ?? ""}`;
  const badge = badgeOf(item);
  const badgeLabel = badgeText(badge) || item.source_label || item.source || tr("src.local");
  const badgeIcon = badge?.icon ? `${badge.icon} ` : "";
  const bg = safeMediaUrl(item.backdrop || item.poster);
  const title = item.title || "";
  const desc = item.overview || "";
  const dur = item.duration ? formatDuration(item.duration) : "";

  return `
    <article class="pm-hero" data-play-key="${esc(key)}" data-play-id="${esc(item.id ?? '')}">
      ${bg ? `<img class="pm-hero-backdrop" src="${esc(bg)}" alt="" loading="lazy">` : ""}
      <div class="pm-hero-gradient"></div>
      <div class="pm-hero-body">
        <div class="pm-hero-badges pm-flex-ac-g8">
          <span class="pm-source-badge">${esc(badgeIcon)}${esc(badgeLabel)}</span>
          ${item.year ? `<span class="pm-badge">${esc(item.year)}</span>` : ""}
          ${item.genre ? `<span class="pm-badge">${esc(item.genre)}</span>` : ""}
          <span class="pm-badge">HD</span>
          ${dur ? `<span class="pm-badge">${esc(dur)}</span>` : ""}
        </div>
        <h2 class="pm-hero-title">${esc(title)}</h2>
        ${desc ? `<p class="pm-hero-desc">${esc(desc)}</p>` : ""}
        <div class="pm-hero-actions pm-flex-g10-mt8">
          <button type="button" class="pm-player-btn pm-primary" data-play-key="${esc(key)}" data-play-id="${esc(item.id ?? '')}">
            ▶ ${tx("play")}
          </button>
          <button type="button" class="pm-player-btn" data-detail-key="${esc(key)}" data-detail-id="${esc(item.id ?? '')}">
            ℹ ${tx("moreInfo")}
          </button>
        </div>
      </div>
    </article>
  `.trim();
}

export function renderCardHtml(item, isFav = false, esc = defaultEsc, options = {}) {
  if (!item) return "";
  const key = compositeKey ? compositeKey(item) : `${item.source || "locale"}:${item.id ?? ""}`;
  const badge = badgeOf(item);
  const badgeLabel = badgeText(badge) || item.source_label || item.source || tr("src.local");
  const badgeIcon = badge?.icon ? `${badge.icon} ` : "";
  const poster = safeMediaUrl(item.poster);
  const seen = isSeen(item);
  const title = item.title || "";
  const dur = item.duration ? formatDuration(item.duration) : "";
  let meta = "";
  if (item.kind === "episodio" || (item.series && (item.season != null || item.episode != null))) {
    const epPrefix = (item.season != null || item.episode != null) ? `S${item.season ?? 1}E${item.episode ?? 1}` : "";
    meta = [item.series, epPrefix, dur].filter(Boolean).join(" · ");
  } else if (item.kind === "brano") {
    meta = [item.series || item.album, dur].filter(Boolean).join(" · ");
  } else {
    meta = [item.series, item.year, dur].filter(Boolean).join(" · ");
  }

  const defaultIcon = item.kind === "brano" ? "🎵" : (item.kind === "episodio" ? "📺" : "🎬");
  const isS4me = Boolean(isStream4meItem(item) || item.channel_id || options.showPin);
  const pinnedIds = options.pinnedIds instanceof Set ? options.pinnedIds : new Set(Array.isArray(options.pinnedIds) ? options.pinnedIds : []);
  const isPinned = Boolean(options.isPinned ?? (item.id != null && pinnedIds.has(String(item.id))));

  const wlMap = options.watchlistMap;
  const wlEntry = options.wlEntry || (wlMap instanceof Map ? (wlMap.get(key) || (item.id != null ? wlMap.get(String(item.id)) : null)) : null);
  const wlIcon = wlEntry ? (wlEntry.priority === "high" ? "🔥" : "📌") : "📋";

  return `
    <article class="pm-card ${seen ? 'pm-seen' : ''}" data-play-key="${esc(key)}" data-play-id="${esc(item.id)}" data-detail-key="${esc(key)}" data-detail-id="${esc(item.id)}" ${isS4me ? `data-s4me-open="${esc(item.id ?? '')}"` : ""}>
      <div class="pm-poster">
        ${poster ? `<img class="pm-poster-img" src="${esc(poster)}" alt="" loading="lazy">` : `<div class="pm-poster-placeholder">${defaultIcon}</div>`}
        <span class="pm-source-badge pm-abs-db54">${esc(badgeIcon)}${esc(badgeLabel)}</span>
        ${seen ? `<span class="pm-seen-badge pm-seen">✓</span>` : ""}
        <button type="button" class="pm-fav-btn" data-fav-key="${esc(key)}" data-fav-id="${esc(item.id)}" style="position: absolute; top: 6px; left: 6px; z-index: 3; background: var(--panel); border: 1px solid var(--line); border-radius: 999px; width: 24px; height: 24px; display: inline-flex; align-items: center; justify-content: center; font-size: 0.8rem; cursor: pointer; color: ${isFav ? 'var(--accent)' : 'var(--muted)'};" title="${isFav ? tx("fav.remove") : tx("fav.add")}">${isFav ? '★' : '☆'}</button>
        <button type="button" class="pm-fav-btn" data-wl-toggle="${esc(key)}" data-wl-id="${esc(item.id ?? '')}" style="position: absolute; top: 6px; left: 34px; z-index: 3; background: var(--panel); border: 1px solid ${wlEntry ? 'var(--accent)' : 'var(--line)'}; border-radius: 999px; width: 24px; height: 24px; display: inline-flex; align-items: center; justify-content: center; font-size: 0.72rem; cursor: pointer; color: ${wlEntry ? 'var(--accent)' : 'var(--muted)'};" title="${tx("wl.edit")}">${wlIcon}</button>
        ${isS4me && item.id != null ? `
          <button type="button" class="pm-pin-btn ${wlEntry ? 'pm-pinned' : ''}" data-wl-toggle="${esc(key)}" data-wl-id="${esc(item.id)}" title="${wlEntry ? tx("wl.remove") : tx("wl.add")}">
            ${wlEntry ? "✓ " + tx("wl.in") : "＋ Watchlist"}
          </button>
        ` : ""}
      </div>
      <div class="pm-card-body">
        <h4 class="pm-title" title="${esc(title)}">${esc(title)}</h4>
        ${meta ? `<div class="pm-meta">${esc(meta)}</div>` : ""}
      </div>
    </article>
  `.trim();
}

export function renderCarouselHtml(title, items, options = {}, esc = defaultEsc) {
  if (!items || !items.length) return "";
  const favs = options.favs || new Set();
  const pinnedIds = options.pinnedIds || new Set();
  const watchlistMap = options.watchlistMap || new Map();
  const type = options.type || "card";

  let cardsHtml = "";
  if (type === "resume") {
    cardsHtml = items.map((it) => {
      const pct = resumeOf(it);
      const poster = safeMediaUrl(it.backdrop || it.poster);
      const key = compositeKey ? compositeKey(it) : `${it.source || "locale"}:${it.id ?? ""}`;
      const badge = badgeOf(it);
      const badgeLabel = badgeText(badge) || it.source || tr("src.local");
      const badgeIcon = badge?.icon ? `${badge.icon} ` : "";
      let sub = "";
      if (it.kind === "episodio") {
        sub = it.series ? `${it.series} · S${it.season ?? 1}E${it.episode ?? 1}` : tr("ep.n", { n: it.episode ?? 1 });
      } else if (it.kind === "brano") {
        sub = it.series || it.album || "";
      } else if (it.year) {
        sub = String(it.year);
      }
      return `
        <article class="pm-resume-card" data-play-key="${esc(key)}" data-play-id="${esc(it.id)}" data-detail-key="${esc(key)}" data-detail-id="${esc(it.id)}">
          <div class="pm-backdrop">
            ${poster ? `<img class="pm-backdrop-img" src="${esc(poster)}" alt="" loading="lazy">` : `<div class="pm-poster-placeholder">▶</div>`}
            <span class="pm-source-badge pm-abs-db54">${esc(badgeIcon)}${esc(badgeLabel)}</span>
            <div class="pm-progress">
              <div class="pm-progress-bar" style="width: ${pct}%;"></div>
            </div>
          </div>
          <div class="pm-card-body">
            <h4 class="pm-title" title="${esc(it.title)}">${esc(it.title)}</h4>
            <div class="pm-meta">
              ${sub ? `<span>${esc(sub)}</span>` : ""}
              <span class="pm-progress-label">${pct}%${it.resume_pos ? ` · ${esc(formatDuration(it.resume_pos))}` : ""}</span>
            </div>
          </div>
        </article>
      `;
    }).join("");
  } else if (type === "series") {
    cardsHtml = items.map((s) => {
      const rep = s.repItem || {};
      const poster = safeMediaUrl(rep.poster);
      const isFav = s.isFav || favs.has("series:" + s.name);
      const sKey = `series:${s.name}`;
      const wlEntry = watchlistMap instanceof Map ? (watchlistMap.get(sKey) || (rep.id != null ? watchlistMap.get(compositeKey(rep)) : null)) : null;
      const wlIcon = wlEntry ? (wlEntry.priority === "high" ? "🔥" : "📌") : "📋";
      // numeri solo se reali: le righe del catalogo streaming non sono episodi (prima «1 stagione · 2 episodi» per Breaking Bad)
      const meta = s.known === false
        ? (s.label || tr("cat.serie"))
        : `${s.seasonsCount || 1} stagion${(s.seasonsCount || 1) === 1 ? 'e' : 'i'} · ${s.count || 1} episod${(s.count || 1) === 1 ? 'o' : 'i'}`;
      const badge = badgeOf(rep);
      const badgeLabel = badgeText(badge) || rep.source || tr("src.local");
      const badgeIcon = badge?.icon ? `${badge.icon} ` : "";
      return `
        <article class="pm-card ${s.allSeen ? 'pm-seen' : ''}" data-series-name="${esc(s.name)}">
          <div class="pm-poster">
            ${poster ? `<img class="pm-poster-img" src="${esc(poster)}" alt="" loading="lazy">` : `<div class="pm-poster-placeholder">📺</div>`}
            <span class="pm-source-badge pm-abs-db54">${esc(badgeIcon)}${esc(badgeLabel)}</span>
            ${s.allSeen ? `<span class="pm-seen-badge pm-seen">✓ ${tx("seen.series")}</span>` : ""}
            <button type="button" class="pm-fav-btn" data-fav-id="series:${esc(s.name)}" style="position: absolute; top: 6px; left: 6px; z-index: 3; background: var(--panel); border: 1px solid var(--line); border-radius: 999px; width: 24px; height: 24px; display: inline-flex; align-items: center; justify-content: center; font-size: 0.8rem; cursor: pointer; color: ${isFav ? 'var(--accent)' : 'var(--muted)'};" title="${isFav ? tx("fav.remove") : tx("fav.add")}">${isFav ? '★' : '☆'}</button>
            <button type="button" class="pm-fav-btn" data-wl-toggle="series:${esc(s.name)}" style="position: absolute; top: 6px; left: 34px; z-index: 3; background: var(--panel); border: 1px solid ${wlEntry ? 'var(--accent)' : 'var(--line)'}; border-radius: 999px; width: 24px; height: 24px; display: inline-flex; align-items: center; justify-content: center; font-size: 0.72rem; cursor: pointer; color: ${wlEntry ? 'var(--accent)' : 'var(--muted)'};" title="${tx("wl.edit")}">${wlIcon}</button>
          </div>
          <div class="pm-card-body">
            <h4 class="pm-title" title="${esc(s.name)}">${esc(s.name)}</h4>
            <div class="pm-meta">${esc(meta)}</div>
          </div>
        </article>
      `;
    }).join("");
  } else {
    cardsHtml = items.map((it) => {
      const key = compositeKey ? compositeKey(it) : String(it.id);
      const isFav = favs.has(key) || favs.has(String(it.id));
      return renderCardHtml(it, isFav, esc, { pinnedIds, watchlistMap });
    }).join("");
  }

  const countLabel = `${items.length} ${items.length === 1 ? 'titolo' : 'titoli'}`;

  return `
    <section class="pm-carousel">
      <div class="pm-carousel-header">
        <h3 class="pm-carousel-title">${esc(title)}</h3>
        <div class="pm-carousel-controls" style="display: flex; align-items: center; gap: 6px;">
          <span class="pm-carousel-count">${esc(countLabel)}</span>
          <button type="button" class="pm-carousel-btn" data-carousel-scroll="-1" title="${tx("scroll.left")}" aria-label="${tx("scroll.left")}">‹</button>
          <button type="button" class="pm-carousel-btn" data-carousel-scroll="1" title="${tx("scroll.right")}" aria-label="${tx("scroll.right")}">›</button>
        </div>
      </div>
      <div class="pm-carousel-row" data-carousel-row>
        ${cardsHtml}
      </div>
    </section>
  `.trim();
}

export function renderListHtml(items = [], options = {}, esc = defaultEsc) {
  if (!items || !items.length) {
    return `<p class="muted pm-tc-75fc">${tx("empty.items")}</p>`;
  }
  const favs = options.favs || new Set();
  const watchlistMap = options.watchlistMap || new Map();
  return `
    <div class="pm-list">
      ${items.map((it) => {
        const key = compositeKey ? compositeKey(it) : String(it.id ?? "");
        const isFav = favs.has(key) || favs.has(String(it.id));
        const wlEntry = watchlistMap instanceof Map ? (watchlistMap.get(key) || (it.id != null ? watchlistMap.get(String(it.id)) : null)) : null;
        const wlIcon = wlEntry ? (wlEntry.priority === "high" ? "🔥" : "📌") : "📋";
        const badge = badgeOf(it);
        const badgeLabel = badgeText(badge) || it.source || tr("src.local");
        const badgeIcon = badge?.icon ? `${badge.icon} ` : "";
        const poster = safeMediaUrl(it.poster || it.backdrop);
        const dur = it.duration ? formatDuration(it.duration) : "";
        let metaParts = [badgeIcon + badgeLabel, it.year, dur].filter(Boolean);
        if (it.kind === "episodio" && it.series) {
          const ep = (it.season != null || it.episode != null) ? `S${it.season ?? 1}E${it.episode ?? 1}` : "";
          metaParts = [it.series, ep, dur].filter(Boolean);
        }
        const defaultIcon = it.kind === "brano" ? "🎵" : (it.kind === "episodio" ? "📺" : "🎬");
        return `
          <div class="pm-list-row" data-play-key="${esc(key)}" data-play-id="${esc(it.id ?? '')}" data-detail-key="${esc(key)}" data-detail-id="${esc(it.id ?? '')}">
            <div class="pm-list-thumb">
              ${poster ? `<img class="pm-list-thumb-img" src="${esc(poster)}" alt="" loading="lazy">` : defaultIcon}
            </div>
            <div class="pm-list-info">
              <h4 class="pm-list-title" title="${esc(it.title)}">${esc(it.title)}</h4>
              <div class="pm-list-meta">
                ${metaParts.map((m) => `<span>${esc(m)}</span>`).join(" · ")}
              </div>
            </div>
            <div class="pm-list-actions">
              <button type="button" class="pm-fav-btn" data-wl-toggle="${esc(key)}" style="background: transparent; border: none; font-size: 1rem; cursor: pointer; color: ${wlEntry ? 'var(--accent)' : 'var(--muted)'}; padding: 6px;" title="${tx("wl.edit")}">${wlIcon}</button>
              <button type="button" class="pm-fav-btn" data-fav-key="${esc(key)}" data-fav-id="${esc(it.id ?? '')}" style="background: transparent; border: none; font-size: 1.1rem; cursor: pointer; color: ${isFav ? 'var(--accent)' : 'var(--muted)'}; padding: 6px;" title="${isFav ? tx("fav.remove") : tx("fav.add")}">${isFav ? '★' : '☆'}</button>
              <button type="button" class="pm-player-btn pm-primary" data-play-key="${esc(key)}" data-play-id="${esc(it.id ?? '')}" style="padding: 4px 10px; font-size: .8rem;">▶ ${tx("play")}</button>
            </div>
          </div>
        `;
      }).join("")}
    </div>
  `.trim();
}

export function renderMediaContextMenuHtml(item, options = {}, esc = defaultEsc) {
  if (!item) return "";
  const k = options.key || (item.key || (typeof compositeKey === "function" ? compositeKey(item) : ""));
  const id = options.id != null ? String(options.id) : String(item.id ?? "");
  const isContinueItem = Boolean(options.isContinueItem);
  const isS4me = Boolean(options.isS4me);
  const isPinnedS4me = Boolean(options.isPinnedS4me);
  const isFav = Boolean(options.isFav);

  const itemsHtml = [];
  itemsHtml.push(`<button type="button" class="pm-ctx-item" data-ctx-play="${esc(k)}" data-ctx-id="${esc(id)}">▶ ${tx("play")}</button>`);
  itemsHtml.push(`<button type="button" class="pm-ctx-item" data-ctx-detail="${esc(k)}" data-ctx-id="${esc(id)}">ℹ ${tx("info")}</button>`);
  itemsHtml.push(`<button type="button" class="pm-ctx-item" data-ctx-fav="${esc(k)}" data-ctx-id="${esc(id)}">${isFav ? "★ " + tx("fav.remove") : "☆ " + tx("fav.add")}</button>`);

  if (isContinueItem) {
    itemsHtml.push(`<button type="button" class="pm-ctx-item pm-ctx-danger" data-ctx-remove-continue="${esc(k)}" data-ctx-item-id="${esc(id)}">✕ ${tx("continue.remove")}</button>`);
  }

  itemsHtml.push(options.isInWatchlist
    ? `<button type="button" class="pm-ctx-item pm-ctx-danger" data-wl-toggle="${esc(k)}" data-wl-id="${esc(id)}">🗑 ${tx("wl.remove")}</button>`
    : `<button type="button" class="pm-ctx-item" data-wl-toggle="${esc(k)}" data-wl-id="${esc(id)}">📋 ${tx("wl.add")}</button>`);

  return itemsHtml.join("");
}

export function renderDetailModal(target, groups = {}, options = {}, esc = defaultEsc) {
  if (!target) return "";
  const favs = options.favs || new Set();
  const pinnedIds = options.pinnedIds instanceof Set ? options.pinnedIds : new Set(Array.isArray(options.pinnedIds) ? options.pinnedIds : []);
  const watchlistMap = options.watchlistMap || new Map();
  const detailLoading = Boolean(options.loadingDetail);
  const isSeries = Boolean(!detailLoading && (typeof target === "string" || target.series || groups[target.title || target.name || target]));
  const seriesName = typeof target === "string" ? target : (target.series || target.title || target.name || "");
  const seasons = groups[seriesName] || null;

  if (isSeries && seasons) {
    const seasonKeys = Object.keys(seasons).sort((a, b) => Number(a) - Number(b));
    let currentSeason = options.selectedSeason != null ? String(options.selectedSeason) : seasonKeys[0];
    if (!seasonKeys.includes(currentSeason)) currentSeason = seasonKeys[0] || "1";

    const allEps = seasonKeys.flatMap((k) => seasons[k] || []);
    const repEp = allEps.find((e) => e.poster || e.backdrop) || allEps[0] || (typeof target === "object" ? target : {});
    const backdrop = safeMediaUrl(repEp.backdrop || repEp.poster);
    const overview = repEp.overview || (typeof target === "object" ? target.overview : "") || "";
    const currentEps = seasons[currentSeason] || [];

    const lastWatched = allEps.filter(isSeen).pop();
    const nextToWatch = (lastWatched ? nextEpisode(allEps, lastWatched.id) : null) || allEps.find((e) => !isSeen(e)) || allEps[0];
    const isSeriesFav = favs.has("series:" + seriesName);
    const badge = badgeOf(repEp);
    const badgeLabel = badgeText(badge) || repEp.source || tr("src.local");
    const badgeIcon = badge?.icon ? `${badge.icon} ` : "";
    const pinTargetId = (typeof target === "object" && target?.id) ? target.id : repEp.id;
    const isS4meSeries = Boolean(isStream4meItem(repEp) || repEp.channel_id || (typeof target === "object" && (isStream4meItem(target) || target.channel_id)));
    const isPinnedSeries = Boolean(pinTargetId != null && pinnedIds.has(String(pinTargetId)));
    const wlKey = (typeof target === "object" && target?.id) ? (compositeKey(target) || `series:${seriesName}`) : `series:${seriesName}`;
    const wlEntry = options.wlEntry ?? (watchlistMap instanceof Map ? (watchlistMap.get(wlKey) || watchlistMap.get(`series:${seriesName}`) || (repEp.id != null ? watchlistMap.get(compositeKey(repEp)) : null)) : null);

    return `
      <div class="pm-modal-overlay" data-close-modal-backdrop>
        <div class="pm-modal-detail" role="dialog" aria-modal="true">
          <button type="button" class="pm-modal-close" data-close-modal title="${tx("close")}">✕</button>
          <div class="pm-modal-header">
            ${backdrop ? `<img class="pm-modal-backdrop" src="${esc(backdrop)}" alt="" loading="lazy">` : ""}
            <div class="pm-modal-gradient"></div>
            <div class="pm-modal-header-body">
              <div class="pm-flex-ac-g8">
                <span class="pm-source-badge">${esc(badgeIcon)}${esc(badgeLabel)}</span>
                <span class="pm-badge">${tx(seasonKeys.length === 1 ? "seasons.one" : "seasons.n", { n: seasonKeys.length })}</span>
                <span class="pm-badge">${tx("episodes.n", { n: allEps.length })}</span>
                ${repEp.genre ? `<span class="pm-badge">${esc(repEp.genre)}</span>` : ""}
              </div>
              <h2 class="pm-modal-title">${esc(seriesName)}</h2>
              ${overview ? `<p class="pm-hero-desc" style="-webkit-line-clamp: 4;">${esc(overview)}</p>` : ""}
              <div class="pm-flex-ac-wrap-fd38">
                ${nextToWatch ? `
                  <button type="button" class="pm-player-btn pm-primary" data-play-key="${esc(compositeKey ? compositeKey(nextToWatch) : nextToWatch.id)}" data-play-id="${esc(nextToWatch.id)}">
                    ▶ ${tx("play")}: S${esc(nextToWatch.season ?? 1)}E${esc(nextToWatch.episode ?? 1)} · ${esc(nextToWatch.title)}
                  </button>
                ` : ""}
                <button type="button" class="pm-player-btn" data-fav-id="series:${esc(seriesName)}">
                  ${isSeriesFav ? "★ " + tx("fav.isSeries") : "☆ " + tx("fav.add")}
                </button>
                <button type="button" class="pm-player-btn ${wlEntry ? 'pm-primary' : ''}" data-wl-toggle="${esc(wlKey)}"${pinTargetId != null ? ` data-wl-id="${esc(pinTargetId)}"` : ""}>
                  ${wlEntry ? "✓ " + tx("wl.in") : "＋ Watchlist"}
                </button>
              </div>
              ${renderWatchlistControlsHtml(wlKey, wlEntry, esc)}
            </div>
          </div>
          <div class="pm-modal-body">
            <div class="pm-season-tabs" role="tablist">
              ${seasonKeys.map((s) => `
                <button type="button" role="tab" class="pm-season-tab ${String(s) === String(currentSeason) ? 'pm-active' : ''}" data-modal-season="${esc(s)}">
                  ${tx("season.n", { n: s })}
                </button>
              `).join("")}
            </div>
            <div class="pm-episode-list">
              ${currentEps.map((ep) => {
                const epPoster = safeMediaUrl(ep.poster || repEp.poster || backdrop);
                const seen = isSeen(ep);
                const pct = resumeOf(ep);
                const key = compositeKey ? compositeKey(ep) : String(ep.id);
                const isFav = favs.has(key) || favs.has(String(ep.id));
                return `
                  <article class="pm-episode-card ${seen ? 'pm-seen' : ''}" data-play-key="${esc(key)}" data-play-id="${esc(ep.id)}">
                    <div class="pm-episode-thumb">
                      ${epPoster ? `<img class="pm-episode-thumb-img" src="${esc(epPoster)}" alt="" loading="lazy">` : `<div class="pm-poster-placeholder">▶</div>`}
                      ${seen ? `<span class="pm-seen-badge pm-seen">✓</span>` : ""}
                    </div>
                    <div class="pm-episode-info">
                      <div class="pm-episode-num">${ep.episode != null ? tx("ep.n", { n: ep.episode }) : ""}</div>
                      <h4 class="pm-episode-title" title="${esc(ep.title)}">${esc(ep.title)}</h4>
                      ${ep.overview ? `<p class="pm-episode-desc">${esc(ep.overview)}</p>` : ""}
                      <div class="pm-meta">
                        ${ep.duration ? `<span>${esc(formatDuration(ep.duration))}</span>` : ""}
                        ${pct > 0 && !seen ? `<span class="pm-progress-label">${pct}%</span>` : ""}
                      </div>
                    </div>
                    <button type="button" class="pm-fav-btn" data-fav-key="${esc(key)}" data-fav-id="${esc(ep.id)}" style="background: transparent; border: none; font-size: 1.1rem; cursor: pointer; color: ${isFav ? 'var(--accent)' : 'var(--muted)'}; padding: 6px;" title="${isFav ? tx("fav.remove") : tx("fav.add")}">${isFav ? '★' : '☆'}</button>
                  </article>
                `;
              }).join("")}
            </div>
          </div>
        </div>
      </div>
    `.trim();
  }

  // Standalone item (Film, Brano, Stream4me item, etc.)
  const item = target;
  const key = compositeKey ? compositeKey(item) : `${item.source || "locale"}:${item.id ?? ""}`;
  const badge = badgeOf(item);
  const badgeLabel = badgeText(badge) || item.source_label || item.source || tr("src.local");
  const badgeIcon = badge?.icon ? `${badge.icon} ` : "";
  const bg = safeMediaUrl(item.backdrop || item.poster);
  const dur = item.duration ? formatDuration(item.duration) : "";
  const isFav = favs.has(key) || favs.has(String(item.id));
  const isS4me = Boolean(isStream4meItem(item) || item.channel_id || options.showPin);
  const isPinned = Boolean(options.isPinned ?? (item.id != null && pinnedIds.has(String(item.id))));
  const detailEpisodes = Array.isArray(options.episodes) ? options.episodes : (Array.isArray(item.episodes) ? item.episodes : []);
  const wlEntry = options.wlEntry ?? (watchlistMap instanceof Map ? (watchlistMap.get(key) || (item.id != null ? watchlistMap.get(String(item.id)) : null)) : null);

  return `
    <div class="pm-modal-overlay" data-close-modal-backdrop>
      <div class="pm-modal-detail" role="dialog" aria-modal="true">
        <button type="button" class="pm-modal-close" data-close-modal title="${tx("close")}">✕</button>
        <div class="pm-modal-header">
          ${bg ? `<img class="pm-modal-backdrop" src="${esc(bg)}" alt="" loading="lazy">` : ""}
          <div class="pm-modal-gradient"></div>
          <div class="pm-modal-header-body">
            <div class="pm-flex-ac-g8">
              <span class="pm-source-badge">${esc(badgeIcon)}${esc(badgeLabel)}</span>
              ${item.year ? `<span class="pm-badge">${esc(item.year)}</span>` : ""}
              ${item.genre ? `<span class="pm-badge">${esc(item.genre)}</span>` : ""}
              <span class="pm-badge">HD</span>
              ${dur ? `<span class="pm-badge">${esc(dur)}</span>` : ""}
            </div>
            <h2 class="pm-modal-title">${esc(item.title || "")}</h2>
            ${item.overview ? `<p class="pm-hero-desc" style="-webkit-line-clamp: 5;">${esc(item.overview)}</p>` : ""}
            <div class="pm-flex-ac-wrap-cb18">
              <button type="button" class="pm-player-btn pm-primary" data-play-key="${esc(key)}" data-play-id="${esc(item.id ?? '')}">
                ▶ ${tx("play")}
              </button>
              <button type="button" class="pm-player-btn" data-fav-key="${esc(key)}" data-fav-id="${esc(item.id ?? '')}">
                ${isFav ? "★ " + tx("fav.is") : "☆ " + tx("fav.add")}
              </button>
              <button type="button" class="pm-player-btn ${wlEntry ? 'pm-primary' : ''}" data-wl-toggle="${esc(key)}" data-wl-id="${esc(item.id ?? '')}">
                ${wlEntry ? "✓ " + tx("wl.in") : "＋ Watchlist"}
              </button>
            </div>
            ${renderWatchlistControlsHtml(key, wlEntry, esc)}
          </div>
        </div>
        ${detailLoading || detailEpisodes.length ? `
          <div class="pm-modal-body">
            ${detailLoading ? `<p class="muted pm-m0-t88" role="status"><span class="pm-loading-spin pm-inline" aria-hidden="true"></span>${tx("s4m.loadingEps")}</p>` : ""}
            ${detailEpisodes.length ? `
              <h4 class="pm-m0-t95-939c">${tx("s4m.episodes", { n: detailEpisodes.length })}</h4>
              <div class="pm-episode-list">
                ${detailEpisodes.map((ep, idx) => {
                  const epKey = compositeKey ? compositeKey(ep) : `${ep.source || item.source || "stream4me"}:${ep.id ?? idx}`;
                  const epPoster = safeMediaUrl(ep.poster || item.poster || bg);
                  return `
                    <article class="pm-episode-card" data-play-key="${esc(epKey)}" data-play-id="${esc(ep.id ?? '')}">
                      <div class="pm-episode-thumb">
                        ${epPoster ? `<img class="pm-episode-thumb-img" src="${esc(epPoster)}" alt="" loading="lazy">` : `<div class="pm-poster-placeholder">▶</div>`}
                      </div>
                      <div class="pm-episode-info">
                        <div class="pm-episode-num">${ep.episode != null ? tx("ep.n", { n: ep.episode }) : tx("stream.n", { n: idx + 1 })}</div>
                        <h4 class="pm-episode-title" title="${esc(ep.title || item.title || '')}">${esc(ep.title || item.title || '')}</h4>
                        ${ep.overview ? `<p class="pm-episode-desc">${esc(ep.overview)}</p>` : ""}
                      </div>
                      <button type="button" class="pm-player-btn pm-primary" data-play-key="${esc(epKey)}" data-play-id="${esc(ep.id ?? '')}" style="padding: 5px 12px; font-size: 0.8rem;">▶ ${tx("play")}</button>
                    </article>
                  `;
                }).join("")}
              </div>
            ` : ""}
          </div>
        ` : ""}
      </div>
    </div>
  `.trim();
}

export function renderStream4meBrowserHtml(state = {}, esc = defaultEsc) {
  const {
    installed = false,
    providers = [],
    activeProvider = null,
    activePath = "",
    query = "",
    browsedItems = [],
    pinnedIds = new Set(),
    favs = new Set(),
    watchlistMap = new Map(),
    loading = false,
    error = "",
  } = state || {};

  const pinSet = pinnedIds instanceof Set ? pinnedIds : new Set(Array.isArray(pinnedIds) ? pinnedIds.map(String) : []);
  const favSet = favs instanceof Set ? favs : new Set(Array.isArray(favs) ? favs.map(String) : []);
  const provList = Array.isArray(providers) ? providers : [];
  const itemsList = Array.isArray(browsedItems) ? browsedItems : [];

  if (!activeProvider) {
    if (!installed && !provList.length) {
      return `
        <div class="pm-empty-banner pm-tc-mt16-9794">
          <div class="pm-mb10-76ac">🧩</div>
          <h3 style="margin: 0 0 8px 0; font-size: 1.2rem; color: var(--text);">${tx("s4m.notInstalled")}</h3>
          <p class="muted pm-t88-e063">
            ${tx("s4m.installHint")}
          </p>
          <button type="button" class="pm-player-btn pm-primary" data-install-stream4me style="font-size: 0.95rem; padding: 8px 20px;">
            ⬇ ${tx("s4m.install1")}
          </button>
        </div>
      `.trim();
    }

    return `
      <div class="pm-s4me-browser">
        <div class="pm-provider-header">
          <div class="pm-flex-col-g4">
            <h3 style="margin: 0; font-size: 1.25rem; color: var(--text);">🧩 ${tx("s4m.browser")}</h3>
            <p class="muted pm-m0-t84">${tx("s4m.browserHint")}</p>
          </div>
          <div class="pm-provider-search-bar">
            <input type="search" class="pm-provider-search-input" data-provider-search-input value="${esc(query)}" placeholder="${tx("s4m.searchPh")}">
            <button type="button" class="pm-player-btn pm-primary" data-provider-search-btn>🔍 ${tx("s4m.searchBtn")}</button>
          </div>
        </div>
        ${loading ? `
          <div class="pm-provider-status">
            <p class="muted">${tx("s4m.searching")}</p>
          </div>
        ` : ""}
        ${error ? `
          <div class="pm-provider-status">
            <p class="pm-3d45">${esc(error)}</p>
            <button type="button" class="pm-player-btn" data-provider-retry>↻ ${tx("retry")}</button>
          </div>
        ` : ""}
        ${query && itemsList.length ? `
          <div class="pm-mb24">
            <h4 class="pm-9fa1">${tx("s4m.results", { q: query, n: itemsList.length })}</h4>
            <div class="pm-grid">
              ${itemsList.map((it) => {
                const sIt = { ...it, source: it.source || "stream4me", source_label: it.source_label || it.channel_name || "Stream4me" };
                const ck = compositeKey ? compositeKey(sIt) : String(sIt.id ?? "");
                const isFav = favSet.has(ck) || favSet.has(String(sIt.id ?? ""));
                return renderCardHtml(sIt, isFav, esc, { showPin: true, pinnedIds: pinSet, watchlistMap });
              }).join("")}
            </div>
          </div>
        ` : ""}
        <div class="pm-provider-grid">
          ${provList.map((p) => {
            const pId = p.id || p.channel || p.name || "";
            const pName = p.name || p.title || pId;
            const cats = Array.isArray(p.categories) ? p.categories : (p.category ? [p.category] : []);
            return `
              <article class="pm-provider-card" data-open-provider="${esc(pId)}">
                <div class="pm-provider-card-top">
                  <span class="pm-provider-icon">🧩</span>
                  <div class="pm-mw0-f1">
                    <h4 class="pm-provider-title" title="${esc(pName)}">${esc(pName)}</h4>
                    ${p.language ? `<span class="pm-badge">${esc(p.language)}</span>` : ""}
                  </div>
                </div>
                ${cats.length ? `
                  <div class="pm-provider-tags">
                    ${cats.map((c) => `<span class="pm-badge">${esc(c)}</span>`).join("")}
                  </div>
                ` : ""}
                <div class="pm-provider-card-footer">
                  <button type="button" class="pm-player-btn pm-primary pm-w100-jc" data-open-provider="${esc(pId)}">
                    ${tx("s4m.openCatalog")} →
                  </button>
                </div>
              </article>
            `;
          }).join("")}
        </div>
      </div>
    `.trim();
  }

  const provName = activeProvider.name || activeProvider.title || activeProvider.id || "Provider";
  const menus = Array.isArray(activeProvider.menus) ? activeProvider.menus : [];

  return `
    <div class="pm-s4me-browser">
      <div class="pm-provider-nav">
        <div class="pm-flex-ac-g12-wrap">
          <button type="button" class="pm-player-btn" data-close-provider>← ${tx("s4m.allProviders")}</button>
          <h3 style="margin: 0; font-size: 1.2rem; color: var(--text);">🧩 ${esc(provName)}</h3>
        </div>
        <div class="pm-provider-search-bar">
          <input type="search" class="pm-provider-search-input" data-provider-search-input value="${esc(query)}" placeholder="${tx("s4m.searchIn", { name: provName })}">
          <button type="button" class="pm-player-btn pm-primary" data-provider-search-btn>🔍 ${tx("search")}</button>
        </div>
      </div>
      ${menus.length ? `
        <div class="pm-season-tabs pm-mb14" role="tablist">
          ${menus.map((m) => {
            const mPath = m.path ?? m.id ?? m.action ?? "";
            const mLabel = m.label || m.title || m.name || mPath || tr("catalog");
            const isAct = !query && (String(mPath) === String(activePath));
            return `
              <button type="button" role="tab" class="pm-season-tab ${isAct ? 'pm-active' : ''}" data-provider-path="${esc(mPath)}">
                ${esc(mLabel)}
              </button>
            `;
          }).join("")}
        </div>
      ` : ""}
      ${loading ? `
        <div class="pm-provider-status">
          <p class="muted">${tx("s4m.exploring", { name: provName })}</p>
        </div>
      ` : error ? `
        <div class="pm-provider-status">
          <p class="pm-bd40">${esc(error)}</p>
          <button type="button" class="pm-player-btn" data-provider-retry>↻ ${tx("retry")}</button>
        </div>
      ` : itemsList.length ? `
        <div class="pm-grid">
          ${itemsList.map((it) => {
            const sIt = { ...it, source: it.source || "stream4me", source_label: it.source_label || provName };
            const ck = compositeKey ? compositeKey(sIt) : String(sIt.id ?? "");
            const isFav = favSet.has(ck) || favSet.has(String(sIt.id ?? ""));
            return renderCardHtml(sIt, isFav, esc, { showPin: true, pinnedIds: pinSet, watchlistMap });
          }).join("")}
        </div>
      ` : `
        <div class="pm-provider-status">
          <p class="muted">${tx("s4m.emptySection")}</p>
        </div>
      `}
    </div>
  `.trim();
}

const SRC_STATE_LABEL = { ok: "src.ok", error: "src.error", absent: "src.absent", slow: "src.slow", unknown: "src.unknown" };

/** Payload per media-server/config: source, base_url + (api_key | username/password | token). */
export function buildServerPayload({ type = "jellyfin", url = "", user = "", password = "", key = "" } = {}) {
  const source = type === "plex" ? "plex" : "jellyfin";
  const body = { source, base_url: String(url).trim() };
  const k = String(key).trim();
  if (source === "plex") body.token = k;
  else if (String(user).trim() && password) Object.assign(body, { username: String(user).trim(), password });
  else body.api_key = k;
  return body;
}

/** Riga di stato del catalogo ricette-web: { text, chip }. */
export function catalogSummary(st) {
  if (!st) return { text: tr("cat.status.none"), chip: "" };
  const total = st.total ?? st.count ?? st.items;
  const n = total != null ? " · " + tr("titles.n", { n: total }) : "";
  if (st.refreshing) return { text: tr("updating") + (typeof st.progress === "number" && st.progress <= 1 ? ` (${Math.round(st.progress * 100)}%)` : ""), chip: tr("update") };
  const when = st.updated_at ? tr("updatedOn", { data: new Date(Number(st.updated_at) * 1000).toLocaleString(lang) }) : tr("cat.never");
  return { text: when + n + (st.last_error ? " · " + tr("errorWith", { err: st.last_error }) : ""), chip: st.last_error ? tr("src.error") : (total != null ? tr("titles.n", { n: total }) : "") };
}

/** Stato sorgente da un errore di fetch: 404 / non trovata = estensione assente. */
export function stateFromError(err) {
  const m = `${err?.status ?? ""} ${err?.message ?? ""}`;
  return /404|not found|non trovat|non installat/i.test(m) ? "absent" : "error";
}

// Piu' badge se logica.js espone sourceBadges (elemento presente in piu' sorgenti), altrimenti uno solo.
const badgeOf = (item) => {
  const list = (typeof logicaModule.sourceBadges === "function" ? logicaModule.sourceBadges(item) : null) || [];
  const bs = list.length ? list : [sourceBadge(item?.source)];
  return { icon: bs[0]?.icon, label: bs.map((b) => b.label).join(" · ") };
};

const SRC_NAMES = { "media-locale": "src.local", "media-server": "Server", "ricette-web": "Web" };
const CHIP_TEXT = { ok: "chip.ok", slow: "chip.slow", error: "chip.error", absent: "chip.absent" };
/** Chip di stato per sorgente dei risultati federati; 'absent' resta grigio. */
export function renderSourceChips(statuses, esc = defaultEsc) {
  return (Array.isArray(statuses) ? statuses : []).map((s) => {
    const st = CHIP_TEXT[s.state] ? s.state : "error";
    const n = st === "ok" || st === "slow" ? ` · ${Number(s.count) || 0}` : "";
    return `<span class="pm-src-chip pm-src-${st}">${esc(SRC_NAMES[s.id] ? tr(SRC_NAMES[s.id]) : s.id)}: ${tx(CHIP_TEXT[st])}${n}</span>`;
  }).join("");
}

export function renderSettingsModal(data = {}, esc = defaultEsc) {
  const roots = data.roots || [];
  const srcStates = data.srcStates || {};
  const catalog = data.catalog || null;
  const serverConfigured = Array.isArray(data.serverConfigured) ? data.serverConfigured : [];
  const catalogLine = catalogSummary(catalog);
  const srcChip = (key, text) => {
    const st = srcStates[key]?.state || "unknown";
    return `<span class="pm-src-chip pm-src-${st}">${esc(text || srcStates[key]?.text || tr(SRC_STATE_LABEL[st]))}</span>`;
  };
  const absentMsg = (ext) => `<p class="muted pm-m0-t82">${tx("absent", { ext })}</p>`;
  const scanning = Boolean(data.scanning);
  const canPick = Boolean(typeof window !== "undefined" && window.pywebview?.api?.pick_folder);
  const installedAddons = data.installedAddons || [];
  const activeRecipes = data.activeRecipes || [];
  const providers = Array.isArray(data.providers) ? data.providers : [];
  const availableInactiveProviders = Array.isArray(data.availableInactiveProviders) ? data.availableInactiveProviders : [];
  const prefs = { ...PREF_DEFAULTS, ...(data.playerPrefs || {}) };
  const stream4meInstalled = installedAddons.some((a) => (a.name || a.id || "").toLowerCase().includes("stream4me")) || Boolean(data.stream4meStatus) || providers.length > 0;

  return `
    <div class="pm-settings-overlay" data-close-settings-backdrop>
      <div class="pm-settings-modal" role="dialog" aria-modal="true">
        <div class="pm-settings-header">
          <h3 class="pm-settings-title">⚙ ${tx("settings.title")}</h3>
          <button type="button" class="pm-modal-close" data-close-settings style="position: static;" title="${tx("close")}">✕</button>
        </div>
        <div class="pm-settings-content">
            <div class="pm-settings-section">
              <div class="pm-flex-jsb-ac">
                <strong class="pm-t95">${tx("set.folders")}</strong> ${srcChip("locale", roots.length ? tr("set.nFolders", { n: roots.length }) : tr("set.noFolder"))}
                <button type="button" class="pm-player-btn" data-scan-now ${scanning ? "disabled" : ""}>
                  ${scanning ? "⟳ " + tx("set.scanning") : "↻ " + tx("set.scanNow")}
                </button>
              </div>
              <p class="muted pm-m0-t82">${tx("set.foldersHint")}</p>
              <div class="pm-flex-g6">
                <input type="text" class="pm-root-input pm-f1-mw0-t84-f5be" placeholder="${tx("set.pathPh")}">
                ${canPick ? `<button type="button" class="pm-player-btn" data-pick-root>${tx("browse")}</button>` : ""}
                <button type="button" class="pm-player-btn pm-primary" data-add-root>＋ ${tx("add")}</button>
              </div>
              <div class="pm-flex-col-g6-mt8">
                ${roots.length ? roots.map((r) => `
                  <div class="pm-flex-ac-jsb-5ba9">
                    <span class="pm-ovh-ell-nowrap-f1" title="${esc(r.path)}">📁 ${esc(r.path)}</span>
                    <button type="button" class="pm-player-btn" data-remove-root="${esc(r.path)}" style="padding: 2px 8px; font-size: 0.74rem;">✕ ${tx("remove")}</button>
                  </div>
                `).join("") : `<p class="muted pm-t82-e343">${tx("set.noFolders")}</p>`}
              </div>
            </div>
            <div class="pm-settings-section">
              <div class="pm-flex-jsb-ac">
                <strong class="pm-t95">${tx("set.server")}</strong> ${srcChip("server")}
              </div>
              ${srcStates.server?.state === "absent" ? absentMsg("media-server") : `
              <p class="muted pm-m0-t82">${tx("set.serverHint")}${serverConfigured.length ? " " + tx("set.configured", { list: serverConfigured.join(", ") }) : ""}</p>
              <div class="pm-flex-g8">
                <select id="pm-server-type" class="pm-source-select pm-6519">
                  <option value="jellyfin">Jellyfin</option>
                  <option value="plex">Plex</option>
                </select>
                <input type="text" id="pm-server-url" placeholder="http://192.168.1.100:8096" class="pm-f1-mw0-t84-f5be">
              </div>
              <div class="pm-flex-g8-wrap">
                <input type="text" id="pm-server-user" placeholder="${tx("set.user")}" autocomplete="off" class="pm-f1-t84-64e7">
                <input type="password" id="pm-server-pass" placeholder="${tx("set.pass")}" autocomplete="new-password" class="pm-f1-t84-64e7">
              </div>
              <input type="password" id="pm-server-token" placeholder="${tx("set.token")}" autocomplete="off" class="pm-t84-66d3">
              <div class="pm-flex-g8-ac">
                <button type="button" class="pm-player-btn pm-primary" data-save-server>${tx("set.save")}</button>
                <button type="button" class="pm-player-btn" data-test-server>${tx("set.test")}</button>
                <span class="pm-server-status muted pm-t82"></span>
              </div>`}
            </div>
${srcStates.kodi?.state === "absent" ? `<div class="pm-settings-section"><div class="pm-flex-jsb-ac"><strong class="pm-t95">Kodi & Stream4me</strong> ${srcChip("kodi")}</div>${absentMsg("ricette-web")}</div>` : `
            <div class="pm-settings-section">
              <div class="pm-flex-jsb-ac">
                <strong class="pm-t95">${tx("set.kodi")}</strong>
                ${srcChip("kodi", tr(stream4meInstalled ? "s4m.installed" : "s4m.notInstalledShort"))}
              </div>
              <p class="muted pm-m0-t82">${tx("set.kodiHint")}</p>
              <div>
                <button type="button" class="pm-player-btn pm-primary" data-install-stream4me>
                  ${stream4meInstalled ? "↻ " + tx("s4m.update") : "⬇ " + tx("s4m.installShort")}
                </button>
                <button type="button" class="pm-player-btn" data-cleanup-stream4me title="${tx("s4m.cleanup.title")}">
                  🧹 ${tx("s4m.cleanup")}
                </button>
              </div>

              <div class="pm-mt10-flex-col-6085">
                <strong class="pm-t88">${tx("prov.manage")}</strong>
                <div class="pm-flex-wrap-g6">
                  <input type="text" id="pm-prov-name" placeholder="${tx("prov.namePh")}" class="pm-f1-t84-b179">
                  <input type="text" id="pm-prov-host" placeholder="${tx("prov.hostPh")}" class="pm-f1-t84-8999">
                  <select id="pm-prov-cat" class="pm-source-select">
                    <option value="movie,tvshow">${tx("prov.cat.both")}</option>
                    <option value="anime">Anime</option>
                    <option value="movie">${tx("prov.cat.movie")}</option>
                    <option value="tvshow">${tx("prov.cat.tv")}</option>
                    <option value="live">${tx("prov.cat.live")}</option>
                  </select>
                  <button type="button" class="pm-player-btn pm-primary" data-add-provider>＋ ${tx("prov.add")}</button>
                </div>

                ${availableInactiveProviders.length ? `
                  <div class="pm-flex-g6-ac-mt4">
                    <select id="pm-prov-enable" class="pm-source-select pm-f1">
                      ${availableInactiveProviders.map((ip) => `<option value="${esc(ip.id || ip.channel || ip.name)}">${esc(ip.name || ip.title || ip.id)}</option>`).join("")}
                    </select>
                    <button type="button" class="pm-player-btn" data-enable-provider>${tx("prov.enable")}</button>
                  </div>
                ` : ""}

                ${providers.length ? `
                  <div class="pm-flex-col-g5-mt6">
                    <span class="muted pm-t8">${tx("prov.active", { n: providers.length })}</span>
                    ${providers.map((p) => {
                      const pid = p.id || p.channel || p.name || "";
                      const pname = p.name || p.title || pid;
                      return `
                        <div class="pm-flex-ac-jsb-5249">
                          <span>🧩 <strong>${esc(pname)}</strong> ${p.host ? `<span class="muted">(${esc(p.host)})</span>` : ""}</span>
                          <button type="button" class="pm-player-btn" data-remove-provider="${esc(pid)}" style="padding: 2px 8px; font-size: 0.74rem;">🗑 ${tx("remove")}</button>
                        </div>
                      `;
                    }).join("")}
                  </div>
                ` : ""}
              </div>

              <div class="pm-mt10-fb10">
                <strong class="pm-t86">${tx("addon.custom")}</strong>
                <div class="pm-flex-g6-mt6">
                  <input type="text" id="pm-addon-input" placeholder="${tx("addon.ph")}" class="pm-f1-mw0-t84-f5be">
                  <button type="button" class="pm-player-btn" data-install-addon>${tx("addon.install")}</button>
                </div>
              </div>
              <div class="pm-flex-col-g6-mt8">
                <strong class="pm-t84">${tx("addon.active")}</strong>
                ${installedAddons.length ? installedAddons.map((a) => `
                  <div class="pm-flex-ac-jsb-bfc5">
                    <span>🧩 ${esc(a.name || a.id)}</span>
                    <span class="muted">${esc(a.version || "")}</span>
                  </div>
                `).join("") : ""}
                ${activeRecipes.length ? activeRecipes.map((r) => `
                  <div class="pm-flex-ac-jsb-bfc5">
                    <span>📜 ${esc(r.title || r.name || r.id)}</span>
                    <span class="muted">${tx("recipe")}</span>
                  </div>
                `).join("") : ""}
                ${!installedAddons.length && !activeRecipes.length ? `<span class="muted pm-t8">${tx("addon.none")}</span>` : ""}
              </div>
            </div>
`}
            <div class="pm-settings-section">
              <div class="pm-flex-jsb-ac">
                <strong class="pm-t95">${tx("set.recipes")}</strong> ${srcChip("ricette", catalogLine.chip)}
              </div>
              ${srcStates.ricette?.state === "absent" ? absentMsg("ricette-web") : `
              <p class="muted pm-catalog-line pm-m0-t82">${esc(catalogLine.text)}</p>
              <div><button type="button" class="pm-player-btn" data-refresh-catalog ${catalog?.refreshing ? "disabled" : ""}>⟳ ${tx("refreshCatalog")}</button></div>`}
            </div>
            <div class="pm-settings-section pm-player-prefs">
              <strong class="pm-t95">${tx("set.player")}</strong>
              <label class="pm-pref-row"><input type="checkbox" data-pref-autonext ${prefs.autonext ? "checked" : ""}> ${tx("set.autonext")}</label>
              <label class="pm-pref-row"><input type="checkbox" data-pref-skipintro ${prefs.skipIntro ? "checked" : ""}> ${tx("set.skipintro")}</label>
              <label class="pm-pref-row">${tx("set.skipsecs")} <input type="number" class="pm-pref-secs" data-pref-skipsecs min="5" max="600" step="1" value="${esc(prefs.skipSecs)}" ${prefs.skipIntro ? "" : "disabled"}></label>
            </div>
            <div class="pm-settings-section">
              <strong class="pm-t95">${tx("set.meta")}</strong>
              <p class="muted pm-m0-t82">${tx("set.metaHint")}</p>
              <div class="pm-mt6">
                <button type="button" class="pm-player-btn pm-primary" data-enrich-metadata>
                  🔍 ${tx("set.enrich")}
                </button>
              </div>
              <div class="pm-enrich-status muted pm-mt8-t82"></div>
            </div>
        </div>
      </div>
    </div>
  `.trim();
}

export { attachPlay, play, loadContinueCache };

/** Renderizza l'HTML del widget dashboard Media Locale (vuoto o card con avanzamento). */
export function renderMediaWidgetHtml(item, esc = defaultEsc) {
  if (!item || isSeen(item) || !(resumeOf(item) > 0 || Number(item.resume_pos || item.pos || 0) > 0)) {
    return `
      <div class="gs-empty-widget pm-flex-col-ac-1d36">
        <div class="pm-8486">🎬</div>
        <div class="pm-flex-col-g2">
          <p class="pm-m0-t95-54b1">${tx("widget.none")}</p>
          <p class="pm-m0-t8-c416">${tx("widget.hint")}</p>
        </div>
        <button type="button" class="btn primary gs-media-open-btn" style="background: var(--accent); color: var(--bg); border: none; padding: 6px 14px; border-radius: 6px; font-weight: 500; cursor: pointer; margin-top: 4px;">
          ${tx("widget.open")}
        </button>
      </div>
    `.trim();
  }

  const title = item.title || tr("media.item");
  const pos = Number(item.resume_pos ?? item.pos ?? 0);
  const dur = Number(item.duration ?? 0);
  let percent = resumeOf(item);
  if (percent <= 0 && pos > 0 && dur > 0) {
    percent = Math.min(100, Math.max(1, Math.round((pos / dur) * 100)));
  }

  const imgUrl = safeMediaUrl(item.backdrop || item.poster);

  let subtitle = "";
  if (item.kind === "episodio" || item.series) {
    const epPart = (item.season != null || item.episode != null) ? `S${item.season ?? 1}E${item.episode ?? 1}` : "";
    subtitle = [item.series, epPart].filter(Boolean).join(" · ");
  } else if (item.year) {
    subtitle = String(item.year);
  }

  let timeInfo = "";
  if (dur > 0 && pos > 0) {
    const rem = Math.max(0, dur - pos);
    timeInfo = `${formatDuration(pos)} / ${formatDuration(dur)} · ${formatDuration(rem)} rimasti`;
  } else if (pos > 0) {
    timeInfo = formatDuration(pos);
  } else if (dur > 0) {
    timeInfo = formatDuration(dur);
  }

  const key = compositeKey ? compositeKey(item) : `${item.source || "locale"}:${item.id ?? ""}`;
  const badge = badgeOf(item);
  const badgeLabel = badgeText(badge) || item.source_label || item.source || tr("src.local");

  return `
    <div class="gs-resume-card pm-flex-g14-ac-w100">
      <div class="gs-resume-cover pm-fs0-ovh-rel-36c9">
        ${imgUrl ? `<img class="pm-poster-img" src="${esc(imgUrl)}" alt="" style="width: 100%; height: 100%; object-fit: cover; display: block;" loading="lazy">` : `<div class="pm-d733">🎬</div>`}
        <span class="pm-source-badge" style="position: absolute; top: 4px; right: 4px; font-size: 0.7rem; padding: 2px 5px; border-radius: 4px; background: var(--panel); border: 1px solid var(--line); color: var(--text);">${esc(badgeLabel)}</span>
      </div>
      <div class="gs-resume-info pm-flex-col-g6-a4a1">
        <div class="pm-mw0">
          <h3 class="gs-resume-title" style="margin: 0; font-size: 1rem; font-weight: 600; color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${esc(title)}">${esc(title)}</h3>
          ${subtitle ? `<div class="gs-resume-meta pm-t8-ovh-ell-bd4f">${esc(subtitle)}</div>` : ""}
        </div>
        <div class="pm-flex-col-g3-w100">
          <div class="gs-progress-bar pm-ovh-w100-b380">
            <div style="width: ${percent}%; height: 100%; background: var(--accent); border-radius: 999px; transition: width 0.3s ease;"></div>
          </div>
          <div class="pm-flex-jsb-ac-2308">
            <span>${esc(timeInfo)}</span>
            <span class="pm-a81c">${percent}%</span>
          </div>
        </div>
        <div class="pm-flex-g8-mt2">
          <button type="button" class="btn primary gs-media-play-btn" data-play-key="${esc(key)}" data-play-id="${esc(item.id ?? '')}" style="background: var(--accent); color: var(--bg); border: none; padding: 5px 14px; border-radius: 6px; font-weight: 600; font-size: 0.84rem; cursor: pointer; display: inline-flex; align-items: center; gap: 4px;">
            ▶ ${tx("play")}
          </button>
          <button type="button" class="btn gs-media-open-btn" style="background: var(--panel); color: var(--text); border: 1px solid var(--line); padding: 5px 10px; border-radius: 6px; font-size: 0.84rem; cursor: pointer;">
            ${tx("openMedia")}
          </button>
        </div>
      </div>
    </div>
  `.trim();
}

/** Genera la definizione del widget dashboard per Media locale. */
export function createMediaWidgetDef(gsInstance, ctxInstance) {
  const pluginId = ctxInstance?.id || "media-locale";
  const sidebarId = ctxInstance?.id || "media";

  const widgetDef = {
    id: "media:continue",
    title: tr("w.continue"),
    description: tr("w.continue.d"),
    category: "extensions",
    defaultSpan: 2,
    async render(container, context) {
      if (!container) return;
      const gsRef = context?.gs || gsInstance || (typeof window !== "undefined" ? window.GS : null);
      const esc = (s) => (gsRef?.esc ? gsRef.esc(s) : defaultEsc(s));

      container.innerHTML = `<div class="pm-tc-t85-e289">${tx("loading")}</div>`;

      // 1. Lettura cache locale di riproduzione
      let cached = [];
      try {
        cached = typeof loadContinueCache === "function" ? loadContinueCache() : [];
      } catch {}

      let targetItem = null;
      if (Array.isArray(cached) && cached.length > 0) {
        targetItem = cached.find((it) => it && !isSeen(it) && (resumeOf(it) > 0 || Number(it.resume_pos || 0) > 0));
      }

      // 2. Lettura live da backend se disponibile
      const api = gsRef?.api || context?.api || (typeof window !== "undefined" ? window.api : null);
      if (api) {
        try {
          let apiItems = null;
          try {
            const res = await federatedList({ api }, { kind: "", query: "" });
            apiItems = res?.items || null;
          } catch {}

          if (Array.isArray(apiItems) && apiItems.length > 0) {
            if (typeof mergeContinueWatching === "function") {
              const merged = mergeContinueWatching(apiItems, cached);
              if (merged && merged.length > 0) {
                targetItem = merged[0];
              }
            } else {
              const liveActive = apiItems.find((it) => it && !isSeen(it) && (resumeOf(it) > 0 || Number(it.resume_pos || 0) > 0));
              if (liveActive) targetItem = liveActive;
            }
          }
        } catch {}
      }

      // 3. Render HTML
      container.innerHTML = renderMediaWidgetHtml(targetItem, esc);

      // 4. Navigazione verso Media locale
      const openMedia = () => {
        const tid = sidebarId || "media";
        if (typeof context?.setView === "function") {
          context.setView({ type: "plugin", id: tid });
        } else if (typeof window !== "undefined" && typeof window.setView === "function") {
          window.setView({ type: "plugin", id: tid });
        } else if (typeof document !== "undefined") {
          const btn = document.querySelector(`[data-plugin-item="${tid}"]`)
            || document.querySelector('[data-plugin-item="media"]')
            || document.querySelector('[data-plugin-item="media-locale"]');
          if (btn) btn.click();
        }
      };

      container.querySelectorAll(".gs-media-open-btn").forEach((btn) => {
        btn.addEventListener("click", (e) => {
          e.stopPropagation();
          openMedia();
        });
      });

      // 5. Avvio riproduzione
      const playBtn = container.querySelector(".gs-media-play-btn");
      if (playBtn && targetItem) {
        playBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          const onDone = () => {
            widgetDef.render(container, context);
          };
          const playItem = normalizePlayItem(targetItem);
          if (typeof window !== "undefined" && typeof window.__pmPlay === "function") {
            window.__pmPlay(playItem, onDone);
          } else if (typeof play === "function") {
            try {
              play(gsRef, playItem, onDone);
            } catch {
              play(playItem, gsRef, onDone);
            }
          } else if (typeof gsRef?.toast === "function") {
            gsRef.toast(tr("player.notReady"));
          }
        });
      }
    }
  };

  return widgetDef;
}

const safeCall = (fn, fb) => { try { return fn() ?? fb; } catch { return fb; } };
const widgetEmpty = (msg) => `<div class="gs-empty-widget pm-widget-empty">${defaultEsc(msg)}</div>`;
const widgetLane = (items, esc, isFav = false) => `<div class="pm-widget-lane">${items.map((it) => renderCardHtml(it, isFav, esc)).join("")}</div>`;

/** Definizioni dei widget extra (spotlight, watchlist, prossimo episodio, preferiti). Render sincroni: ritornano HTML. */
export function createExtraMediaWidgetDefs(gsInstance) {
  const ctxOf = (context) => {
    const gs = context?.gs || gsInstance || (typeof window !== "undefined" ? window.GS : null);
    return { gs, esc: (s) => (gs?.esc ? gs.esc(s) : defaultEsc(s)), known: safeCall(() => loadContinueCache(), []) };
  };
  const def = (id, title, description, defaultSpan, build) => ({
    id, title, description, category: "media", defaultSpan,
    render(arg1, arg2) {
      const isContainer = Boolean(arg1 && ("innerHTML" in arg1 || arg1.nodeType === 1));
      const container = isContainer ? arg1 : null;
      const ctx = isContainer ? arg2 : arg1;
      const c = ctxOf(ctx);
      const html = safeCall(() => build(c), widgetEmpty(tr("empty.content")));
      if (container) container.innerHTML = html;
      return html;
    },
  });
  return [
    def("media:spotlight", tr("w.spot"), tr("w.spot.d"), 2, ({ esc, known }) => {
      const it = pickHeroItem(known, []);
      if (!it) return widgetEmpty(tr("w.spot.empty"));
      const img = safeMediaUrl(it.backdrop || it.poster);
      const badges = [badgeText(sourceBadge?.(it.source)) || it.source, it.year, it.kind].filter(Boolean)
        .map((b) => `<span class="pm-source-badge">${esc(b)}</span>`).join("");
      return `<div class="pm-widget-spotlight">${img ? `<img class="pm-poster-img" src="${esc(img)}" alt="" loading="lazy">` : ""}
        <div class="pm-widget-spotlight-body"><h3>${esc(it.title || tr("untitled"))}</h3><div>${badges}</div>
        <button type="button" class="btn primary gs-media-play-btn" data-play-key="${esc(compositeKey(it))}" data-play-id="${esc(it.id ?? "")}">▶ ${tx("play")}</button></div></div>`;
    }),
    def("media:watchlist", tr("w.wl"), tr("w.wl.d"), 2, ({ gs, esc }) => {
      const list = sortAndFilterWatchlist(safeCall(() => loadWatchlistLocal(gs), []), { status: "all" }).slice(0, 12);
      return list.length ? widgetLane(list, esc) : widgetEmpty(tr("w.wl.empty"));
    }),
    def("media:next_episode", tr("w.next"), tr("w.next.d"), 1, ({ esc, known }) => {
      const last = known.find((it) => it && (it.series || it.kind === "episodio"));
      const eps = last ? Object.values(groupEpisodes(known)[String(last.series || last.show || last.title || "Varie").trim()] || {}).flat() : [];
      const next = last && nextEpisode(eps, last.id);
      return next ? widgetLane([next], esc) : widgetEmpty(tr("w.next.empty"));
    }),
    def("media:favorites", tr("w.favs"), tr("w.favs.d"), 2, ({ gs, esc, known }) => {
      const favs = loadFavs(gs);
      // shortcut: only favorites present in the continue cache are shown, upgrade if the widget gets a library fetch
      const list = known.filter((it) => it && (favs.has(compositeKey(it)) || favs.has(String(it.id)))).slice(0, 12);
      return list.length ? widgetLane(list, esc, true) : widgetEmpty(tr("w.favs.empty"));
    }),
  ];
}

/** Registra il widget "media:continue" nel registro della Dashboard modulare. */
export function registerMediaWidget(gsInstance, ctxInstance) {
  const widgetDef = createMediaWidgetDef(gsInstance, ctxInstance);
  const reg = gsInstance?.ui?.registerWidget
    || (typeof window !== "undefined" ? window.GS?.ui?.registerWidget : null);
  if (typeof reg === "function") {
    createExtraMediaWidgetDefs(gsInstance).forEach((w) => reg(w));
    reg(widgetDef);
    return true;
  }
  if (typeof window !== "undefined") {
    window.__gs_pending_widgets = window.__gs_pending_widgets || [];
    window.__gs_pending_widgets.push(...createExtraMediaWidgetDefs(gsInstance), widgetDef);
    if (gsInstance?.on) {
      gsInstance.on("dashboardReady", () => {
        const r = gsInstance?.ui?.registerWidget || window.GS?.ui?.registerWidget;
        if (typeof r === "function") [...createExtraMediaWidgetDefs(gsInstance), widgetDef].forEach((w) => r(w));
      });
    }
  }
  return false;
}

const TAB_KINDS = { tutti: "", film: "film", serie: "episodio", anime: "episodio", musica: "brano", stream4me: "web", web: "web", watchlist: "watchlist" };

const WATCHLIST_STORAGE_KEY = "pm_watchlist";

function loadWatchlistLocal(gs) {
  try {
    const k = pkey(WATCHLIST_STORAGE_KEY);
    const raw = gs?.store?.get
      ? gs.store.get(k, null)
      : JSON.parse(localStorage.getItem("gs." + k) || "[]");
    if (Array.isArray(raw) && raw.length) return raw.map((x) => normalizeWatchlistEntry(x));
    const ls = JSON.parse(localStorage.getItem("gs." + k) || "[]");
    return Array.isArray(ls) ? ls.map((x) => normalizeWatchlistEntry(x)) : [];
  } catch {
    return [];
  }
}

function saveWatchlistLocal(gs, entries) {
  const arr = Array.isArray(entries) ? entries.map((x) => normalizeWatchlistEntry(x)) : [];
  const k = pkey(WATCHLIST_STORAGE_KEY);
  try { if (gs?.store?.set) gs.store.set(k, arr); } catch {}
  try { localStorage.setItem("gs." + k, JSON.stringify(arr)); } catch {}
}

export default function (gs, ctx) {
  if (ctx?.t) { setT(ctx.t, ctx.lang); setPlayerT(ctx.t, ctx.lang); }
  const pluginId = ctx?.id || "media-locale";
  const apiBase = `/plugin-api/${pluginId}`;
  const esc = (s) => (gs?.esc ? gs.esc(s) : defaultEsc(s));
  const favs = loadFavs(gs);
  attachPlay(gs);
  try { import("./remote.js").then((m) => m.startRemote?.(gs)).catch(() => {}); } catch { /* telefono non disponibile */ }

  const sidebarId = ctx?.id || "media";
  gs.addSidebarItem({ id: sidebarId, label: tr("nav"), icon: "🎬", view: sidebarId });
  gs.addTutorial?.({
    id: pluginId, view: sidebarId,
    steps: [
      { title: tr("tut.1.t"), text: tr("tut.1.x"), sel: ".pm-main-tabs" },
      { title: tr("tut.2.t"), text: tr("tut.2.x"), sel: ".pm-view-mode-tabs" },
      { title: tr("tut.3.t"), text: tr("tut.3.x"), sel: ".pm-settings-btn" },
    ],
  });
  registerMediaWidget(gs, ctx);
  if (typeof gs?.on === "function") {
    gs.on("dashboardReady", () => registerMediaWidget(gs, ctx));
  }

  if (typeof gs?.addSettingsTab === "function") {
    gs.addSettingsTab({
      id: "media-stream4me",
      label: tr("set.tab"),
      category: "streaming",
      async render(el) {
        if (!el) return;
        let provs = [];
        let inactive = [];
        const refreshGlobalSettings = async () => {
          try {
            const pRes = await gs.api("/plugin-api/ricette-web/stream4me/providers");
            provs = Array.isArray(pRes?.providers) ? pRes.providers : (Array.isArray(pRes) ? pRes : []);
            inactive = Array.isArray(pRes?.availableInactiveProviders) ? pRes.availableInactiveProviders : [];
          } catch {}
          el.innerHTML = `
            <div class="pm-settings-section">
              <strong class="pm-t95">${tx("prov.manage")}</strong>
              <p class="muted pm-m0-t82">${tx("prov.manageHint")}</p>
              <div class="pm-flex-wrap-g6">
                <input type="text" id="pm-prov-name" placeholder="${tx("prov.namePh")}" class="pm-f1-t84-b179">
                <input type="text" id="pm-prov-host" placeholder="${tx("prov.hostPh")}" class="pm-f1-t84-8999">
                <select id="pm-prov-cat" class="pm-source-select">
                  <option value="movie,tvshow">${tx("prov.cat.both")}</option>
                  <option value="anime">Anime</option>
                  <option value="movie">${tx("prov.cat.movie")}</option>
                  <option value="tvshow">${tx("prov.cat.tv")}</option>
                  <option value="live">${tx("prov.cat.live")}</option>
                </select>
                <button type="button" class="pm-player-btn pm-primary" data-add-provider>＋ ${tx("prov.add")}</button>
              </div>
              ${inactive.length ? `
                <div class="pm-flex-g6-ac-mt4">
                  <select id="pm-prov-enable" class="pm-source-select pm-f1">
                    ${inactive.map((ip) => `<option value="${esc(ip.id || ip.channel || ip.name)}">${esc(ip.name || ip.title || ip.id)}</option>`).join("")}
                  </select>
                  <button type="button" class="pm-player-btn" data-enable-provider>${tx("prov.enable")}</button>
                </div>
              ` : ""}
              <div class="pm-flex-col-g5-mt8">
                ${provs.map((p) => {
                  const pid = p.id || p.channel || p.name || "";
                  const pname = p.name || p.title || pid;
                  return `
                    <div class="pm-flex-ac-jsb-5ba9">
                      <span>🧩 <strong>${esc(pname)}</strong> ${p.host ? `<span class="muted">(${esc(p.host)})</span>` : ""}</span>
                      <button type="button" class="pm-player-btn" data-remove-provider="${esc(pid)}" style="padding: 2px 8px; font-size: 0.74rem;">🗑 ${tx("remove")}</button>
                    </div>
                  `;
                }).join("")}
              </div>
            </div>
          `;
        };
        el.onclick = async (ev) => {
          const addBtn = ev.target.closest("[data-add-provider]");
          if (addBtn) {
            const name = el.querySelector("#pm-prov-name")?.value?.trim() || "";
            const host = el.querySelector("#pm-prov-host")?.value?.trim() || "";
            const cat = el.querySelector("#pm-prov-cat")?.value || "movie,tvshow";
            if (!name) return;
            try {
              await gs.api("/plugin-api/ricette-web/stream4me/providers", {
                method: "POST",
                body: { name, host, categories: cat.split(",").map((s) => s.trim()).filter(Boolean) },
              });
              gs?.toast?.(tr("prov.added"));
            } catch {}
            await refreshGlobalSettings();
            return;
          }
          const enBtn = ev.target.closest("[data-enable-provider]");
          if (enBtn) {
            const pid = el.querySelector("#pm-prov-enable")?.value || "";
            if (!pid) return;
            try {
              await gs.api("/plugin-api/ricette-web/stream4me/providers", { method: "POST", body: { id: pid, enable: true } });
              gs?.toast?.(tr("prov.enabled"));
            } catch {}
            await refreshGlobalSettings();
            return;
          }
          const remBtn = ev.target.closest("[data-remove-provider]");
          if (remBtn) {
            const pid = remBtn.dataset.removeProvider;
            if (!pid) return;
            try {
              await gs.api("/plugin-api/ricette-web/stream4me/providers/remove", { method: "POST", body: { id: pid } });
              gs?.toast?.(tr("prov.removed"));
            } catch {}
            await refreshGlobalSettings();
          }
        };
        await refreshGlobalSettings();
      },
    });
  }

  /** `siblings`: episodi della stessa serie, per i pulsanti precedente/successivo e l'elenco nel lettore. */
  function executePlay(item, onClose, siblings, extra = {}) {
    const playItem = normalizePlayItem(item);
    const opts = { ...(Array.isArray(siblings) && siblings.length > 1 ? { episodes: siblings.map(normalizePlayItem) } : {}), ...extra };
    if (typeof window !== "undefined" && typeof window.__pmPlay === "function") {
      window.__pmPlay(playItem, onClose, opts);
    } else if (typeof play === "function") {
      try {
        play(gs, playItem, onClose, opts);
      } catch {
        play(playItem, gs, onClose);
      }
    } else if (typeof gs?.toast === "function") {
      gs.toast(tr("player.notReady"));
    }
  }

  let pmActiveKeyDown = null;
  let pmStorageHandler = null;

  const viewDef = {
    title: tr("nav"),
    async render(root) {
      if (!root) return;
      let currentTab = "tutti";
      let currentSource = "all";
      let currentQuery = "";
      let filterOnlyFavs = false;
      let showSettings = false;
      let srcStates = {};
      let catalogStatus = null;
      let serverConfigured = [];
      let sourceChips = [];
      let catalogPoll = null;
      let selectedDetailTarget = null;
      let selectedDetailSeason = null;
      let viewMode = (typeof localStorage !== "undefined" && localStorage.getItem("gs.pm_view_mode")) || "netflix";
      let roots = [];
      let scanning = false;
      let items = [];
      let catalogItems = [];
      let pinnedItems = [];
      const pinnedIds = new Set();
      let watchlistEntries = loadWatchlistLocal(gs);
      const watchlistMap = new Map();
      let wlFilterStatus = "all";
      let wlFilterPriority = "all";
      let wlSortBy = "priority";
      let wlFilterCategory = "all";
      let wlImp = null;
      let s4mInstalled = false;
      let s4mProviders = [];
      let s4mInactiveProviders = [];
      let activeS4mProvider = null;
      let activeS4mPath = "";
      let s4mBrowsedItems = [];
      let s4mSearchSeq = 0;      // numero dell'ultima ricerca: una risposta vecchia non deve sovrascrivere quella nuova
      let s4mSearchQuery = "";   // testo a cui si riferiscono i risultati di s4mBrowsedItems
      let s4mSearchMeta = null;  // {searched, failed, pending} dell'ultima ricerca generale
      let s4mLoading = false;
      let s4mError = "";
      let detailEpisodes = [];
      let detailLoading = false;
      let installedAddons = [];
      let activeRecipes = [];
      const itemsByKey = new Map();
      const itemsById = new Map();

      function syncWatchlistMap() {
        watchlistMap.clear();
        for (const raw of watchlistEntries) {
          if (!raw) continue;
          const e = normalizeWatchlistEntry(raw);
          if (e.item_key) watchlistMap.set(e.item_key, e);
          if (e.item_id) watchlistMap.set(String(e.item_id), e);
          if (e.series) watchlistMap.set(`series:${e.series}`, e);
        }
      }
      syncWatchlistMap();

      root.innerHTML = "";
      root.classList.add("pm-view");

      const toolbar = document.createElement("div");
      toolbar.className = "pm-toolbar";
      toolbar.style.cssText = "display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 20px;";
      toolbar.innerHTML = `
        <div class="pm-season-tabs pm-main-tabs" role="tablist">
          <button type="button" role="tab" class="pm-season-tab pm-active" data-tab="tutti">✨ ${tx("all")}</button>
          <button type="button" role="tab" class="pm-season-tab" data-tab="film">🎬 ${tx("cat.film")}</button>
          <button type="button" role="tab" class="pm-season-tab" data-tab="serie">📺 ${tx("cat.serie")}</button>
          <button type="button" role="tab" class="pm-season-tab" data-tab="anime">🇯🇵 ${tx("cat.anime")}</button>
          <button type="button" role="tab" class="pm-season-tab" data-tab="watchlist">📋 Watchlist</button>
          <button type="button" role="tab" class="pm-season-tab" data-tab="stream4me">🧩 Stream4me</button>
          <button type="button" role="tab" class="pm-season-tab" data-tab="musica">🎵 ${tx("cat.music")}</button>
        </div>
        <select class="pm-source-select" aria-label="${tx("filter.source")}">
          <option value="all">🌐 ${tx("filter.all")}</option>
          <option value="locale">📁 ${tx("filter.local")}</option>
          <option value="server">🖥️ ${tx("set.server")}</option>
          <option value="web">📡 Web & Stream4me</option>
        </select>
        <div class="pm-view-mode-tabs" role="group" aria-label="${tx("view.mode")}">
          <button type="button" class="pm-view-mode-btn ${viewMode === 'netflix' ? 'pm-active' : ''}" data-view-mode="netflix" title="${tx("view.netflix.t")}">🍿 ${tx("view.netflix")}</button>
          <button type="button" class="pm-view-mode-btn ${viewMode === 'grid' ? 'pm-active' : ''}" data-view-mode="grid" title="${tx("view.grid.t")}">⊞ ${tx("view.grid")}</button>
          <button type="button" class="pm-view-mode-btn ${viewMode === 'list' ? 'pm-active' : ''}" data-view-mode="list" title="${tx("view.list.t")}">☰ ${tx("view.list")}</button>
        </div>
        <div class="pm-f1-4ad8">
          <input type="search" class="pm-search pm-w100-t84-aadf" placeholder="${tx("search.ph")}" aria-label="${tx("search")}">
        </div>
        <div class="pm-flex-g8-ac">
          <button type="button" class="pm-season-tab pm-primary" data-open-add-dialog title="${tx("add.title")}">＋ ${tx("add")}</button>
          <button type="button" class="pm-season-tab pm-favs-toggle" data-toggle-favs>☆ ${tx("favs.only")}</button>
          <button type="button" class="pm-season-tab" data-quick-enrich title="${tx("enrich.q.title")}">🔍 ${tx("enrich.q")}</button>
          ${typeof document !== "undefined" && document.body?.classList.contains("media-window") ? "" : `<button type="button" class="pm-season-tab" data-open-media-window title="${tx("window.title")}">⧉ ${tx("window")}</button>`}
          <button type="button" class="pm-season-tab pm-settings-btn" data-open-settings>⚙ ${tx("settings.btn")}</button>
        </div>
      `;

      const content = document.createElement("div");
      content.className = "pm-content";

      const modalHost = document.createElement("div");
      modalHost.className = "pm-modal-host";

      const ctxMenuHost = document.createElement("div");
      ctxMenuHost.className = "pm-ctx-menu-host";

      const chipsHost = document.createElement("div");
      chipsHost.className = "pm-src-chips";

      root.append(toolbar, chipsHost, content, modalHost, ctxMenuHost);

      const searchInput = toolbar.querySelector(".pm-search");
      const favsToggle = toolbar.querySelector(".pm-favs-toggle");
      const sourceSelect = toolbar.querySelector(".pm-source-select");
      const tabBtns = toolbar.querySelectorAll("[data-tab]");

      function closeCtxMenu() {
        ctxMenuHost.innerHTML = "";
      }

      function attachWheelListeners() {
        const rows = content.querySelectorAll("[data-carousel-row]");
        rows.forEach((row) => {
          row.addEventListener("wheel", (e) => {
            if (e.shiftKey && e.deltaY !== 0) {
              e.preventDefault();
              row.scrollLeft += e.deltaY;
            }
          }, { passive: false });
        });
      }

      function enrichStream4meItemForLibrary(itemObj) {
        if (!itemObj) return null;
        const copy = { ...itemObj, source: itemObj.source || "stream4me", source_label: itemObj.source_label || itemObj.channel_name || activeS4mProvider?.name || "Stream4me" };
        const provCats = Array.isArray(activeS4mProvider?.categories) ? activeS4mProvider.categories : [];
        const isAnimeProv = provCats.some((c) => String(c).toLowerCase().includes("anime")) || String(activeS4mPath).toLowerCase().includes("anime") || isAnimeItem(copy);
        const isTvProv = provCats.some((c) => String(c).toLowerCase().includes("tv") || String(c).toLowerCase().includes("serie")) || String(activeS4mPath).toLowerCase().includes("serie") || copy.kind === "serie" || copy.kind === "episodio" || Boolean(copy.series);

        if (isAnimeProv) {
          copy.kind = "episodio";
          copy.series = copy.series || copy.title;
          if (!copy.genre || !String(copy.genre).toLowerCase().includes("anime")) {
            copy.genre = copy.genre ? `${copy.genre}, Anime` : "Anime";
          }
        } else if (isTvProv) {
          copy.kind = "episodio";
          copy.series = copy.series || copy.title;
        } else if (!copy.kind) {
          copy.kind = "film";
        }
        return copy;
      }

      async function pinStream4meItem(itemObj, pid) {
        const targetId = String(pid || itemObj?.id || "");
        if (!targetId) return null;
        const enriched = enrichStream4meItemForLibrary(itemObj || { id: targetId, title: targetId, source: "stream4me" });
        try {
          await gs.api("/plugin-api/ricette-web/stream4me/pin", { method: "POST", body: { item: enriched, id: targetId } });
        } catch {}
        pinnedIds.add(targetId);
        const existingIdx = pinnedItems.findIndex((x) => String(x.id) === targetId);
        if (existingIdx >= 0) {
          pinnedItems[existingIdx] = { ...pinnedItems[existingIdx], ...enriched };
        } else if (enriched) {
          pinnedItems.unshift(enriched);
        }
        syncItemsIndex();
        return enriched;
      }

      async function loadWatchlist() {
        try {
          const res = await gs.api(`/plugin-api/media-locale/watchlist`);
          const arr = Array.isArray(res?.entries) ? res.entries : (Array.isArray(res?.items) ? res.items : (Array.isArray(res) ? res : null));
          if (Array.isArray(arr)) {
            // unione, mai sostituzione: un server vuoto (salvataggi falliti, database nuovo) non deve cancellare la copia locale
            const { entries, localOnly } = mergeWatchlists(arr.map((x) => normalizeWatchlistEntry(x)), loadWatchlistLocal(gs));
            watchlistEntries = entries;
            saveWatchlistLocal(gs, watchlistEntries);
            for (const e of localOnly) {  // le voci che il server non ha si rimandano: restano anche dopo un aggiornamento dell'app
              try { await gs.api("/plugin-api/media-locale/watchlist", { method: "POST", body: e }); } catch { break; }
            }
          }
        } catch {
          watchlistEntries = loadWatchlistLocal(gs);
        }
        syncWatchlistMap();
      }

      async function upsertWatchlistEntry(itemKey, patch = {}, itemFallback = null) {
        const existing = watchlistMap.get(itemKey) || null;
        const fb = itemFallback || itemsByKey.get(itemKey) || itemsById.get(itemKey) || (itemKey.startsWith("series:") ? { id: itemKey, title: itemKey.slice(7), series: itemKey.slice(7), kind: "episodio", source: "locale" } : { id: itemKey, item_key: itemKey });
        const now = Math.floor(Date.now() / 1000);
        const merged = normalizeWatchlistEntry({
          ...(existing || {}),
          ...patch,
          item_key: itemKey,
          added_at: existing?.added_at || now,
          updated_at: now,
        }, fb);

        const idx = watchlistEntries.findIndex((e) => e.item_key === merged.item_key || (e.item_id && e.item_id === merged.item_id));
        if (idx >= 0) {
          watchlistEntries[idx] = merged;
        } else {
          watchlistEntries.unshift(merged);
        }
        syncWatchlistMap();
        saveWatchlistLocal(gs, watchlistEntries);

        try {
          await gs.api("/plugin-api/media-locale/watchlist", { method: "POST", body: merged });
        } catch (err) {
          // la copia locale c'è, ma sul disco non è arrivata: lo si dice invece di tacere, e verrà rimandata al prossimo avvio
          gs?.toast?.(tr("wl.saveFail", { err: err?.message || "" }), true);
        }

        // If Stream4me item not in library yet, pin it so the user never loses it
        if (fb && isStream4meItem(fb) && fb.id != null && !pinnedIds.has(String(fb.id))) {
          await pinStream4meItem(fb, fb.id);
        }
        return merged;
      }

      async function removeWatchlistEntry(itemKey) {
        const gone = watchlistEntries.find((e) => e.item_key === itemKey || String(e.item_id) === itemKey);
        watchlistEntries = watchlistEntries.filter((e) => e.item_key !== itemKey && String(e.item_id) !== itemKey && `series:${e.series}` !== itemKey);
        syncWatchlistMap();
        saveWatchlistLocal(gs, watchlistEntries);
        try {
          await gs.api("/plugin-api/media-locale/watchlist/remove", { method: "POST", body: { item_key: itemKey } });
        } catch (err) {
          gs?.toast?.(tr("wl.removeFail", { err: err?.message || "" }), true);
        }
        // senza il pulsante «Libreria», i titoli Stream4me salvati seguono la watchlist: tolti da una, escono dall'altra
        const pid = gone?.item_id != null ? String(gone.item_id) : "";
        if (pid && pinnedIds.has(pid)) {
          try { await gs.api("/plugin-api/ricette-web/stream4me/unpin", { method: "POST", body: { id: pid } }); } catch {}
          pinnedIds.delete(pid);
          pinnedItems = pinnedItems.filter((x) => String(x.id) !== pid);
        }
      }

      /** Salva via bulk le voci (con linked_key) e le fonde nell'elenco locale. Ritorna il riepilogo del backend. */
      async function bulkSaveWatchlist(entries) {
        return gs.api("/plugin-api/media-locale/watchlist/bulk", { method: "POST", body: { entries } });
      }

      /** Associa al catalogo le voci senza linked_key; salva solo le nuove associazioni. Ritorna il numero associato. */
      async function autoLinkWatchlist() {
        const changed = [];
        watchlistEntries = watchlistEntries.map((raw) => {
          const e = normalizeWatchlistEntry(raw);
          if (e.linked_key) return e;
          const m = matchLibraryItem(e, items);
          if (!m) return e;
          const ne = { ...e, linked_key: compositeKey(m.item), updated_at: Math.floor(Date.now() / 1000) };
          changed.push(ne);
          return ne;
        });
        if (!changed.length) return 0;
        syncWatchlistMap();
        saveWatchlistLocal(gs, watchlistEntries);
        await bulkSaveWatchlist(changed);
        return changed.length;
      }

      /** Applica categoria predefinita e matching col catalogo alle voci grezze dell'anteprima. */
      function prepareImport() {
        const def = WATCHLIST_CATEGORIES[wlImp.defaultCat] ? wlImp.defaultCat : "serie";
        wlImp.prepared = (wlImp.raw || []).map((r) => {
          const e = normalizeWatchlistEntry({ ...r, category: r.category || def });
          const m = matchLibraryItem(e, items);
          return { ...r, category: e.category, status: e.status, linked_key: m ? compositeKey(m.item) : "" };
        });
      }

      function renderWlImport() {
        modalHost.innerHTML = renderWatchlistImportDialogHtml(wlImp, esc);
      }

      async function loadRoots() {
        try {
          const res = await gs.api(`${apiBase}/roots`);
          roots = Array.isArray(res?.roots) ? res.roots : [];
        } catch {
          roots = [];
        }
      }

      async function loadAddonsAndRecipes() {
        try {
          const res = await gs.api("/plugin-api/ricette-web/kodi_addons");
          installedAddons = Array.isArray(res?.addons) ? res.addons : (Array.isArray(res) ? res : []);
        } catch {}
        try {
          const res = await gs.api("/plugin-api/ricette-web/recipes");
          activeRecipes = Array.isArray(res?.recipes) ? res.recipes : (Array.isArray(res) ? res : []);
        } catch {}
      }

      function syncItemsIndex() {
        const merged = [];
        const seen = new Set();
        for (const it of [...catalogItems, ...pinnedItems, ...detailEpisodes]) {
          if (!it) continue;
          const k = compositeKey ? compositeKey(it) : `${it.source || "locale"}:${it.id ?? ""}`;
          if (k && seen.has(k)) continue;
          if (k) seen.add(k);
          merged.push(it);
        }
        items = merged;

        itemsByKey.clear();
        itemsById.clear();
        for (const it of [...items, ...s4mBrowsedItems, ...watchlistEntries]) {
          if (it) {
            const k = it.item_key || (compositeKey ? compositeKey(it) : `${it.source || "locale"}:${it.id ?? ""}`);
            if (k) itemsByKey.set(k, it);
            if (it.id != null) itemsById.set(String(it.id), it);
          }
        }
      }

      async function loadStream4meMeta() {
        try {
          const pRes = await gs.api("/plugin-api/ricette-web/stream4me/providers");
          const pArr = Array.isArray(pRes?.providers) ? pRes.providers : (Array.isArray(pRes) ? pRes : []);
          s4mProviders = pArr;
          s4mInactiveProviders = Array.isArray(pRes?.availableInactiveProviders) ? pRes.availableInactiveProviders : [];
          s4mInstalled = Boolean(pRes?.installed ?? pArr.length > 0);
        } catch {
          s4mProviders = [];
        }
        try {
          const pinRes = await gs.api("/plugin-api/ricette-web/stream4me/pinned");
          const pinArr = Array.isArray(pinRes?.items) ? pinRes.items : (Array.isArray(pinRes) ? pinRes : []);
          pinnedItems = pinArr.map((x) => ({
            ...x,
            source: x.source || "stream4me",
            source_label: x.source_label || x.channel_name || "Stream4me",
          }));
          pinnedIds.clear();
          for (const p of pinnedItems) {
            if (p && p.id != null) pinnedIds.add(String(p.id));
          }
        } catch {
          pinnedItems = [];
        }
      }

      async function browseStream4meProvider(providerObj, pathStr = "", queryStr = "") {
        activeS4mProvider = providerObj || null;
        activeS4mPath = pathStr || "";
        s4mLoading = true;
        s4mError = "";
        renderContent();
        try {
          const chId = providerObj?.id || providerObj?.channel || "all";
          const qp = new URLSearchParams();
          qp.set("channel", chId);
          if (pathStr) qp.set("path", pathStr);
          if (queryStr) qp.set("query", queryStr);
          const res = await gs.api(`/plugin-api/ricette-web/stream4me/browse?${qp.toString()}`);
          const arr = Array.isArray(res?.items) ? res.items : (Array.isArray(res) ? res : []);
          s4mBrowsedItems = arr.map((x) => ({
            ...x,
            source: x.source || "stream4me",
            source_label: x.source_label || providerObj?.name || "Stream4me",
          }));
          if (res?.error) s4mError = String(res.error);
        } catch (err) {
          s4mError = err?.message || tr("s4m.browseFail");
          s4mBrowsedItems = [];
        } finally {
          s4mLoading = false;
          syncItemsIndex();
          renderContent();
        }
      }

      async function searchStream4meOnline(q) {
        if (!q || q.length < 2) return;
        const seq = ++s4mSearchSeq;
        s4mSearchQuery = q;
        s4mSearchMeta = null;
        s4mLoading = true;
        s4mError = "";
        renderContent();
        try {
          // dentro la pagina di un provider si cerca solo lì; ovunque altrove, in TUTTI i provider
          const chId = activeS4mProvider?.id || activeS4mProvider?.channel || "all";
          const res = await gs.api(`/plugin-api/ricette-web/stream4me/browse?channel=${encodeURIComponent(chId)}&query=${encodeURIComponent(q)}`);
          if (seq !== s4mSearchSeq) return; // nel frattempo la ricerca è cambiata
          const arr = Array.isArray(res?.items) ? res.items : (Array.isArray(res) ? res : []);
          s4mBrowsedItems = arr.map((x) => ({
            ...x,
            source: x.source || "stream4me",
            source_label: x.source_label || activeS4mProvider?.name || "Stream4me",
          }));
          s4mSearchMeta = res && res.searched != null ? { searched: res.searched, failed: res.failed || [], pending: res.pending || [] } : null;
        } catch (err) {
          if (seq !== s4mSearchSeq) return;
          s4mError = err?.message || tr("s4m.searchFailShort");
        } finally {
          if (seq === s4mSearchSeq) {
            s4mLoading = false;
            syncItemsIndex();
            renderContent();
          }
        }
      }

      /** Risultati della ricerca generale su Stream4me, mostrati in ogni pagina (tranne quella di un provider): stato, esiti, schede. */
      function renderStreamSearchSection() {
        const q = currentQuery;
        if (activeS4mProvider || q.length < 2 || currentTab === "musica" || currentTab === "watchlist" || currentTab === "stream4me") return "";
        if (s4mSearchQuery !== q) return `<div class="pm-search-status" role="status"><span class="pm-loading-spin pm-inline" aria-hidden="true"></span>${tx("s4m.searchingQ", { q })}</div>`;
        if (s4mLoading) return `<div class="pm-search-status" role="status"><span class="pm-loading-spin pm-inline" aria-hidden="true"></span>${tx("s4m.searchingQ", { q })}</div>`;
        if (s4mError) return `<p class="pm-search-status muted">${tx("s4m.searchFail", { err: s4mError })}</p>`;
        const lost = s4mSearchMeta ? (s4mSearchMeta.failed.length + s4mSearchMeta.pending.length) : 0;
        const note = s4mSearchMeta
          ? `<span class="muted"> · ${tx("s4m.queried", { n: s4mSearchMeta.searched })}${lost ? `, ${tx("s4m.late", { n: lost })}` : ""}</span>`
          : "";
        if (!s4mBrowsedItems.length) return `<p class="pm-search-status muted">${tx("s4m.noResults", { q })}${note ? ` (${tx("s4m.queried", { n: s4mSearchMeta.searched })}${lost ? `, ${tx("s4m.noAnswer", { n: lost })}` : ""})` : ""}</p>`;
        return `<section class="pm-search-s4me"><h3 class="pm-search-title">🔎 ${tx("s4m.on", { n: s4mBrowsedItems.length })}${note}</h3>
          <div class="pm-grid">${s4mBrowsedItems.map((it) => {
            const key = compositeKey ? compositeKey(it) : String(it.id);
            return renderCardHtml(it, favs.has(key) || favs.has(String(it.id)), esc, { pinnedIds, watchlistMap, showPin: true });
          }).join("")}</div></section>`;
      }

      async function loadData() {
        if (!catalogItems.length) {
          // apertura istantanea: l'ultimo catalogo noto, poi le sorgenti lo aggiornano (anche se poi cambia qualcosa)
          const snap = loadCatalogSnapshot();
          if (snap.length) {
            catalogItems = collapseSingleEpisodeSeries(snap);
            syncItemsIndex();
            renderContent();
          } else {
            content.innerHTML = `<p class="muted pm-tc-75fc" role="status"><span class="pm-loading-spin pm-inline" aria-hidden="true"></span>${tx("loading.catalog")}</p>`;
            animateSpinners(content);
          }
        }
        const wl = loadWatchlist(); // locale e leggera
        let side = null;
        // I risultati arrivano a ondate: ogni sorgente completata ridisegna subito (senza bloccare le altre).
        const apply = (its, st) => {
          catalogItems = collapseSingleEpisodeSeries(Array.isArray(its) ? its : []);
          sourceChips = Array.isArray(st) ? st : sourceChips;
          syncItemsIndex();
          renderContent();
        };
        try {
          const res = await federatedList(gs, { kind: "", query: "", onPartial: apply });
          apply(res?.items, res?.sourcesStatus);
          if (res?.items?.length) saveCatalogSnapshot(res.items);
        } catch {
          // sorgenti non raggiungibili: resta l'ultimo catalogo noto invece di svuotare la pagina
          if (!catalogItems.length) apply([], []);
        }
        // Stream4me (provider e preferiti) dopo il catalogo: non compete con la prima visualizzazione
        side = Promise.all([loadStream4meMeta(), wl]);
        await side;
        syncItemsIndex();
        renderContent();
      }

      function getVisibleItems() {
        const base = typeof filterHubItems === "function"
          ? filterHubItems(items, {
              tab: currentTab === "anime" ? "serie" : (currentTab === "stream4me" ? "web" : (currentTab === "watchlist" ? "tutti" : currentTab)),
              sourceFilter: currentSource,
              query: currentQuery,
              onlyFavs: filterOnlyFavs,
              favs,
            })
          : items.filter((it) => {
              if (filterOnlyFavs) {
                const k = compositeKey ? compositeKey(it) : String(it.id);
                if (!favs.has(k) && !favs.has(String(it.id))) return false;
              }
              if (currentSource !== "all") {
                const s = String(it.source || "").toLowerCase();
                if (currentSource === "locale" && s !== "locale" && s !== "media-locale") return false;
                if (currentSource === "server" && s !== "jellyfin" && s !== "plex" && s !== "server") return false;
                if (currentSource === "web" && (it.provider === "stream4me" || (s !== "web" && s !== "ricette-web" && s !== "kodi"))) return false;
              }
              return true;
            });

        if (currentTab === "anime") {
          return items.filter((it) => {
            if (!isAnimeItem(it)) return false;
            if (currentQuery) {
              const q = currentQuery.toLowerCase();
              const match = String(it.title || "").toLowerCase().includes(q) || String(it.series || "").toLowerCase().includes(q);
              if (!match) return false;
            }
            if (filterOnlyFavs) {
              const k = compositeKey ? compositeKey(it) : String(it.id);
              if (!favs.has(k) && !favs.has(String(it.id)) && !(it.series && favs.has("series:" + it.series))) return false;
            }
            return true;
          });
        }
        return base;
      }

      async function loadSourcesState() {
        const probe = async (url) => {
          try { return { ok: true, v: await gs.api(url) }; } catch (err) { return { ok: false, state: stateFromError(err) }; }
        };
        const [cfg, cat, adds] = await Promise.all([
          probe("/plugin-api/media-server/config"),
          probe("/plugin-api/ricette-web/catalog/status"),
          probe("/plugin-api/ricette-web/kodi_addons"),
        ]);
        serverConfigured = cfg.ok ? Object.entries(cfg.v?.servers || {}).filter(([, v]) => v?.base_url).map(([k]) => k) : [];
        catalogStatus = cat.ok ? cat.v : null;
        srcStates = {
          locale: { state: "ok" },
          server: cfg.ok ? { state: serverConfigured.length ? "ok" : "unknown", text: tr(serverConfigured.length ? "src.ok" : "src.notConfigured") } : { state: cfg.state },
          ricette: cat.ok ? { state: cat.v?.last_error ? "error" : "ok" } : { state: cat.state },
          kodi: adds.ok ? { state: "ok" } : { state: adds.state },
        };
      }

      function pollCatalog() {
        clearTimeout(catalogPoll);
        if (!root.isConnected || !showSettings) return;
        catalogPoll = setTimeout(async () => {
          const was = catalogStatus?.refreshing;
          try { catalogStatus = await gs.api("/plugin-api/ricette-web/catalog/status"); } catch { return; }
          if (showSettings) renderSettings();
          if (catalogStatus?.refreshing) pollCatalog();
          else if (was) loadData();
        }, 2000);
      }

      function renderSettings() {
        modalHost.innerHTML = renderSettingsModal({
          srcStates,
          catalog: catalogStatus,
          serverConfigured,
          roots,
          scanning,
          installedAddons,
          activeRecipes,
          providers: s4mProviders,
          availableInactiveProviders: s4mInactiveProviders,
          stream4meStatus: s4mInstalled || s4mProviders.length > 0,
          playerPrefs: loadPlayerPrefsCompat(),
        }, esc);
      }

      function resolveStream4meTarget(target) {
        if (typeof target === "object" && target !== null) {
          if (isStream4meItem(target) || target.channel_id || String(target.source || "").includes("ricette")) {
            return target;
          }
          return null;
        }
        if (typeof target === "string") {
          const allGrouped = groupEpisodes(items);
          const sGroup = allGrouped[target];
          const sEps = sGroup ? Object.values(sGroup).flat() : [];
          return sEps.find((e) => isStream4meItem(e) || String(e.id || "").startsWith("s4me:") || String(e.id || "").startsWith("stream4me:") || String(e.id || "").startsWith("s4m:")) || null;
        }
        return null;
      }

      /** Episodi della serie di `item`: quelli del dettaglio (provider) se lo contengono, altrimenti quelli già in elenco. */
      function episodesOf(item) {
        if (!item || !(item.series || item.kind === "episodio")) return [];
        if (detailEpisodes.some((e) => String(e.id) === String(item.id))) return detailEpisodes;
        const s = String(item.series || "").trim().toLowerCase();
        return [...itemsById.values()].filter((e) => e && String(e.series || "").trim().toLowerCase() === s && (e.kind === "episodio" || e.episode != null));
      }

      async function openItemDetail(target, selectedSeason = null) {
        selectedDetailTarget = target;
        selectedDetailSeason = selectedSeason;
        detailEpisodes = [];
        detailLoading = false;

        const s4mTarget = resolveStream4meTarget(target);

        if (s4mTarget && s4mTarget.id != null) {
          detailLoading = true;
          renderDetail(target, selectedSeason);
          try {
            const res = await gs.api(`/plugin-api/ricette-web/detail?id=${encodeURIComponent(s4mTarget.id)}`);
            if (res && typeof res === "object") {
              if (res.overview && !s4mTarget.overview) s4mTarget.overview = res.overview;
              if (res.poster && !s4mTarget.poster) s4mTarget.poster = res.poster;
              if (res.backdrop && !s4mTarget.backdrop) s4mTarget.backdrop = res.backdrop;
              const eps = Array.isArray(res.episodes) ? res.episodes : (Array.isArray(res.items) ? res.items : []);
              const seriesTitle = typeof target === "string" ? target : (s4mTarget.series || s4mTarget.title || "");
              detailEpisodes = deduplicateStream4meEpisodes(eps, s4mTarget, seriesTitle);
              if (detailEpisodes.length === 1) {
                // un solo episodio = un film («Snatch - Lo strappo» catalogato come serie): scheda e riquadro cambiano subito
                detailEpisodes = [];
                const film = { kind: "film", series: "", episode_count: 1, season_count: 1 };
                Object.assign(s4mTarget, film);
                const row = s4mTarget.id != null ? itemsById.get(String(s4mTarget.id)) : null;
                if (row && row !== s4mTarget) Object.assign(row, film);
                const cat = catalogItems.find((x) => x && String(x.id) === String(s4mTarget.id));
                if (cat) Object.assign(cat, film);
              } else if (detailEpisodes.length > 1) {
                // numeri reali: il riepilogo «N stagioni · M episodi» non conta più le righe del catalogo
                const seasonsN = new Set(detailEpisodes.map((e) => e.season ?? 1)).size;
                const info = { episode_count: detailEpisodes.length, season_count: seasonsN };
                Object.assign(s4mTarget, info);
                for (const x of catalogItems) if (x && String(x.id) === String(s4mTarget.id)) Object.assign(x, info);
              }
              renderContent();
            }
          } catch {}
          detailLoading = false;
          for (const ep of detailEpisodes) {
            const k = compositeKey ? compositeKey(ep) : `${ep.source || "stream4me"}:${ep.id ?? ""}`;
            if (k) itemsByKey.set(k, ep);
            if (ep.id != null) itemsById.set(String(ep.id), ep);
          }
          syncItemsIndex();
          if (detailEpisodes.length === 0) {
            selectedDetailTarget = s4mTarget;
          }
        }
        renderDetail(selectedDetailTarget, selectedDetailSeason);
      }

      function renderDetail(target, selectedSeason = null) {
        const s4mTarget = resolveStream4meTarget(target);
        let groups;
        let modalTarget = target;
        if (s4mTarget) {
          if (detailEpisodes.length > 0) {
            groups = groupEpisodes(detailEpisodes);
          } else {
            groups = {};
            modalTarget = s4mTarget;
          }
        } else {
          const vis = getVisibleItems();
          groups = groupEpisodes([...items, ...vis]);
        }
        modalHost.innerHTML = renderDetailModal(modalTarget, groups, {
          favs,
          pinnedIds,
          watchlistMap,
          selectedSeason,
          episodes: detailEpisodes,
          loadingDetail: detailLoading,
        }, esc);
        animateSpinners(modalHost);
      }

      let curProfile = activeProfile();
      function renderContent() {
        if (activeProfile() !== curProfile) {  // profilo cambiato a vista aperta: niente mescolanze
          curProfile = activeProfile();
          catalogItems = []; items = [];
          watchlistEntries = loadWatchlistLocal(gs);
          syncWatchlistMap();
          favs.clear(); loadFavs(gs).forEach((x) => favs.add(x));
          Promise.resolve().then(() => loadData()).catch(() => {});
        }
        chipsHost.innerHTML = renderSourceChips(sourceChips);
        tabBtns.forEach((b) => b.classList.toggle("pm-active", b.dataset.tab === currentTab));
        favsToggle.classList.toggle("pm-active", filterOnlyFavs);
        favsToggle.textContent = (filterOnlyFavs ? "★ " : "☆ ") + tr("favs.only");
        sourceSelect.value = currentSource;

        if (currentTab === "watchlist") {
          content.innerHTML = renderWatchlistViewHtml(watchlistEntries, {
            status: wlFilterStatus,
            priority: wlFilterPriority,
            sortBy: wlSortBy,
            query: currentQuery,
            category: wlFilterCategory,
          }, esc);
          return;
        }

        if (currentTab === "stream4me" || currentTab === "web") {
          const pinnedCarousel = !activeS4mProvider && !currentQuery && pinnedItems.length
            ? renderCarouselHtml("📌 " + tr("car.pinned"), pinnedItems, { favs, pinnedIds, watchlistMap }, esc)
            : "";
          const browserHtml = renderStream4meBrowserHtml({
            installed: s4mInstalled || installedAddons.some((a) => (a.name || a.id || "").toLowerCase().includes("stream4me")),
            providers: s4mProviders,
            activeProvider: activeS4mProvider,
            activePath: activeS4mPath,
            query: currentQuery,
            browsedItems: s4mBrowsedItems,
            pinnedIds,
            favs,
            watchlistMap,
            loading: s4mLoading,
            error: s4mError,
          }, esc);
          content.innerHTML = `
            <div class="pm-netflix-home">
              ${pinnedCarousel}
              ${browserHtml}
            </div>
          `;
          attachWheelListeners();
          return;
        }

        const vis = getVisibleItems();

        if (filterOnlyFavs || currentQuery) {
          const onlineSearchBanner = renderStreamSearchSection(); // ricerca generale: parte da sola su tutti i provider

          if (!vis.length) {
            content.innerHTML = `
              ${onlineSearchBanner}
              <p class="muted pm-tc-ce59">${tx("empty.filter")}</p>
            `;
            return;
          }
          if (viewMode === "list") {
            content.innerHTML = `${onlineSearchBanner}${renderListHtml(vis, { favs, watchlistMap }, esc)}`;
          } else {
            content.innerHTML = `
              ${onlineSearchBanner}
              <div class="pm-grid pm-mt10">
                ${vis.map((it) => {
                  const key = compositeKey ? compositeKey(it) : String(it.id);
                  const isFav = favs.has(key) || favs.has(String(it.id));
                  return renderCardHtml(it, isFav, esc, { pinnedIds, watchlistMap });
                }).join("")}
              </div>
            `;
          }
          return;
        }

        const cached = typeof loadContinueCache === "function" ? loadContinueCache() : [];
        const continueItems = typeof mergeContinueWatching === "function"
          ? mergeContinueWatching(items, cached)
          : items.filter((it) => { const p = resumeOf(it); return p > 0 && !isSeen(it); });

        const heroItem = typeof pickHeroItem === "function"
          ? pickHeroItem(vis, continueItems)
          : (continueItems[0] || vis[0] || null);

        const heroHtml = heroItem ? renderHeroHtml(heroItem, esc) : "";

        if (viewMode === "list") {
          content.innerHTML = `
            <div class="pm-list-view">
              ${heroHtml}
              ${renderListHtml(vis, { favs, watchlistMap }, esc)}
            </div>
          `;
          return;
        }

        if (viewMode === "grid") {
          content.innerHTML = `
            <div class="pm-grid-view">
              ${heroHtml}
              ${vis.length ? `<div class="pm-grid pm-mt14">${vis.map((it) => {
                const key = compositeKey ? compositeKey(it) : String(it.id);
                const isFav = favs.has(key) || favs.has(String(it.id));
                return renderCardHtml(it, isFav, esc, { pinnedIds, watchlistMap });
              }).join("")}</div>` : `<p class="muted pm-tc-c083">${tx("empty.content")}</p>`}
            </div>
          `;
          return;
        }

        // 1. Continua a guardare
        const resumeHtml = continueItems.length
          ? renderCarouselHtml("🍿 " + tr("car.continue"), continueItems, { type: "resume", favs, pinnedIds, watchlistMap }, esc)
          : "";

        // 1b. Watchlist Carousel (Active items: plan_to_watch or watching, sorted by Priority Alta first)
        const activeWatchlist = sortAndFilterWatchlist(watchlistEntries, { status: "active", sortBy: "priority" })
          .filter((e) => e.status === "plan_to_watch" || e.status === "watching");
        const watchlistCarouselHtml = activeWatchlist.length
          ? renderCarouselHtml("📋 " + tr("car.wl"), activeWatchlist, { favs, pinnedIds, watchlistMap }, esc)
          : "";

        // 2. Stream4me (Pinned + eventuali web items)
        const stream4mePool = pinnedItems.length
          ? pinnedItems
          : vis.filter(isStream4meItem);
        const stream4meHtml = stream4mePool.length
          ? renderCarouselHtml("🧩 " + tr("car.s4m"), stream4mePool, { favs, pinnedIds, watchlistMap }, esc)
          : "";

        // 3. Film
        const filmItems = vis.filter((it) => it.kind === "film" || (!it.series && it.kind !== "episodio" && it.kind !== "brano" && !isAnimeItem(it)));
        const filmHtml = filmItems.length
          ? renderCarouselHtml("🎬 " + tr("cat.film"), filmItems, { favs, pinnedIds, watchlistMap }, esc)
          : "";

        // 4. Serie TV (non anime)
        const tvAll = vis.filter((it) => (it.kind === "episodio" || it.kind === "serie" || it.series) && !isAnimeItem(it));
        const tvEpisodes = tvAll.filter((it) => it.series || it.kind === "episodio");
        const tvGroups = groupEpisodes(tvEpisodes);
        const tvSummaries = Object.keys(tvGroups).map((name) => {
          const seasons = tvGroups[name];
          const sKeys = Object.keys(seasons);
          const eps = sKeys.flatMap((k) => seasons[k]);
          return {
            name,
            ...seriesSummary(eps),
            label: tr("cat.serie"),
            repItem: eps.find((e) => e.poster) || eps[0],
            allSeen: eps.length > 0 && eps.every(isSeen),
            isFav: favs.has("series:" + name),
          };
        });
        const tvStandalone = tvAll.filter((it) => !it.series && it.kind === "serie");
        const tvHtml = tvSummaries.length
          ? renderCarouselHtml("📺 " + tr("cat.serie"), tvSummaries, { type: "series", favs, pinnedIds, watchlistMap }, esc)
          : (tvStandalone.length ? renderCarouselHtml("📺 " + tr("cat.serie"), tvStandalone, { favs, pinnedIds, watchlistMap }, esc) : "");

        // 5. Anime
        const animeAll = vis.filter((it) => isAnimeItem(it));
        const animeSeries = animeAll.filter((it) => it.series || it.kind === "episodio");
        const animeGroups = groupEpisodes(animeSeries);
        const animeSummaries = Object.keys(animeGroups).map((name) => {
          const seasons = animeGroups[name];
          const sKeys = Object.keys(seasons);
          const eps = sKeys.flatMap((k) => seasons[k]);
          return {
            name,
            ...seriesSummary(eps),
            label: tr("cat.anime"),
            repItem: eps.find((e) => e.poster) || eps[0],
            allSeen: eps.length > 0 && eps.every(isSeen),
            isFav: favs.has("series:" + name),
          };
        });
        const animeStandalone = animeAll.filter((it) => !it.series && it.kind !== "episodio");
        const animePool = animeSummaries.length ? animeSummaries : animeStandalone;
        const animeHtml = animePool.length
          ? renderCarouselHtml("🇯🇵 " + tr("cat.anime"), animePool, { type: animeSummaries.length ? "series" : "card", favs, pinnedIds, watchlistMap }, esc)
          : "";

        // 6. Musica
        const musicItems = vis.filter((it) => it.kind === "brano");
        const musicHtml = musicItems.length
          ? renderCarouselHtml("🎵 " + tr("cat.music"), musicItems, { favs, pinnedIds, watchlistMap }, esc)
          : "";

        if (currentTab === "film") {
          content.innerHTML = `
            <div class="pm-netflix-home">
              ${heroHtml}
              ${filmHtml}
              ${filmItems.length ? `<div class="pm-grid pm-mt14">${filmItems.map((it) => renderCardHtml(it, favs.has(compositeKey ? compositeKey(it) : String(it.id)), esc, { pinnedIds, watchlistMap })).join("")}</div>` : ""}
            </div>
          `;
        } else if (currentTab === "serie") {
          content.innerHTML = `
            <div class="pm-netflix-home">
              ${heroHtml}
              ${tvHtml}
            </div>
          `;
        } else if (currentTab === "anime") {
          content.innerHTML = `
            <div class="pm-netflix-home">
              ${heroHtml}
              ${animeHtml}
            </div>
          `;
        } else if (currentTab === "musica") {
          content.innerHTML = `
            <div class="pm-netflix-home">
              ${musicHtml}
              ${musicItems.length ? `<div class="pm-grid pm-mt14">${musicItems.map((it) => renderCardHtml(it, favs.has(compositeKey ? compositeKey(it) : String(it.id)), esc, { pinnedIds, watchlistMap })).join("")}</div>` : ""}
            </div>
          `;
        } else {
          // Home Netflix completa
          content.innerHTML = `
            <div class="pm-netflix-home">
              ${heroHtml}
              ${resumeHtml}
              ${watchlistCarouselHtml}
              ${stream4meHtml}
              ${filmHtml}
              ${tvHtml}
              ${animeHtml}
              ${musicHtml}
              ${!resumeHtml && !watchlistCarouselHtml && !stream4meHtml && !filmHtml && !tvHtml && !animeHtml && !musicHtml ? `<p class="muted pm-tc-c083">${tx("empty.home")}</p>` : ""}
            </div>
          `;
        }

        attachWheelListeners();
      }

      root.oncontextmenu = (e) => {
        // 1. Caso provider Stream4me
        const provCard = e.target.closest(".pm-provider-card[data-open-provider]");
        if (provCard) {
          e.preventDefault();
          e.stopPropagation();
          const pid = provCard.dataset.openProvider || "";
          if (!pid) return;
          const x = Math.min(Number(e.clientX || 120), (window?.innerWidth || 1000) - 200);
          const y = Math.min(Number(e.clientY || 120), (window?.innerHeight || 800) - 150);
          ctxMenuHost.innerHTML = `
            <div class="pm-ctx-menu" style="position: fixed; left: ${x}px; top: ${y}px; z-index: 10000;">
              <button type="button" class="pm-ctx-item" data-open-provider="${esc(pid)}">📂 ${tx("prov.open")}</button>
              <button type="button" class="pm-ctx-item" data-remove-provider="${esc(pid)}">🗑 ${tx("prov.remove")}</button>
            </div>
          `;
          return;
        }

        // 2. Caso Media Card (locandina, continua a guardare, riga, watchlist, hero)
        const mediaCard = e.target.closest(".pm-card, .pm-resume-card, .pm-list-row, .pm-wl-card, .pm-hero, [data-play-key], [data-detail-key]");
        if (!mediaCard) {
          closeCtxMenu();
          return;
        }

        e.preventDefault();
        e.stopPropagation();

        const k = mediaCard.dataset.detailKey || mediaCard.dataset.playKey || mediaCard.dataset.wlCard || "";
        const id = mediaCard.dataset.detailId || mediaCard.dataset.playId || "";
        const item = (k ? itemsByKey.get(k) : null) || (id ? itemsById.get(id) : null) || { id, title: mediaCard.querySelector(".pm-title, .pm-list-title, .pm-hero-title")?.textContent || "Media", key: k };

        const isContinueItem = Boolean(mediaCard.closest(".pm-resume-card") || (item && (item.resume_pos > 0 || (typeof loadContinueCache === "function" && loadContinueCache().some((c) => (k && compositeKey(c) === k) || (id && String(c.id) === String(id)))))));
        const isS4me = Boolean(isStream4meItem(item) || (id && String(id).startsWith("s4me:")) || (item?.source === "stream4me"));
        const isPinnedS4me = Boolean(isS4me && id && pinnedIds.has(String(id)));
        const isFav = favs.has(k) || (id && favs.has(String(id)));

        const x = Math.min(Number(e.clientX || 120), (window?.innerWidth || 1000) - 240);
        const y = Math.min(Number(e.clientY || 120), (window?.innerHeight || 800) - 200);

        ctxMenuHost.innerHTML = `
          <div class="pm-ctx-menu" style="position: fixed; left: ${x}px; top: ${y}px; z-index: 10000;">
            ${renderMediaContextMenuHtml(item, { key: k, id, isContinueItem, isS4me, isPinnedS4me, isFav, isInWatchlist: watchlistMap.has(k) }, esc)}
          </div>
        `;
      };

      root.onchange = async (e) => {
        if (e.target.closest?.("[data-pref-autonext]")) { savePlayerPrefsCompat({ autonext: e.target.checked }); return; }
        if (e.target.closest?.("[data-pref-skipintro]")) { savePlayerPrefsCompat({ skipIntro: e.target.checked }); renderSettings(); return; }
        if (e.target.closest?.("[data-pref-skipsecs]")) { savePlayerPrefsCompat({ skipSecs: e.target.value }); renderSettings(); return; }
        if (wlImp && e.target.closest("[data-wli-provider]")) {
          wlImp = { ...wlImp, provider: e.target.value, content: "", filename: "", raw: null, prepared: null, error: "" };
          renderWlImport();
          return;
        }
        if (wlImp && e.target.closest("[data-wli-defcat]")) {
          wlImp.defaultCat = e.target.value;
          prepareImport();
          renderWlImport();
          return;
        }
        if (wlImp && e.target.closest("[data-wli-file]")) {
          const f = e.target.files && e.target.files[0];
          if (!f) return;
          try {
            wlImp.content = await new Promise((resolve, reject) => {
              const fr = new FileReader();
              fr.onload = () => resolve(String(fr.result || ""));
              fr.onerror = () => reject(new Error(tr("file.readFail")));
              fr.readAsText(f);
            });
            wlImp.filename = f.name;
            wlImp.error = "";
          } catch (err) {
            wlImp.error = err?.message || tr("file.readFail");
          }
          renderWlImport();
          return;
        }
        const wlStatusSel = e.target.closest("[data-wl-status]");
        if (wlStatusSel) {
          const itemKey = wlStatusSel.dataset.wlStatus;
          await upsertWatchlistEntry(itemKey, { status: wlStatusSel.value });
          if (modalHost.innerHTML && selectedDetailTarget) renderDetail(selectedDetailTarget, selectedDetailSeason);
          renderContent();
          return;
        }
        const wlPrioSel = e.target.closest("[data-wl-priority]");
        if (wlPrioSel) {
          const itemKey = wlPrioSel.dataset.wlPriority;
          await upsertWatchlistEntry(itemKey, { priority: wlPrioSel.value });
          if (modalHost.innerHTML && selectedDetailTarget) renderDetail(selectedDetailTarget, selectedDetailSeason);
          renderContent();
          return;
        }
        const wlRatingSel = e.target.closest("[data-wl-rating]");
        if (wlRatingSel) {
          const itemKey = wlRatingSel.dataset.wlRating;
          await upsertWatchlistEntry(itemKey, { rating: Number(wlRatingSel.value || 0) });
          if (modalHost.innerHTML && selectedDetailTarget) renderDetail(selectedDetailTarget, selectedDetailSeason);
          renderContent();
          return;
        }
        const wlFilterPrioSel = e.target.closest("[data-wl-filter-priority]");
        if (wlFilterPrioSel) {
          wlFilterPriority = wlFilterPrioSel.value || "all";
          renderContent();
          return;
        }
        const wlSortSel = e.target.closest("[data-wl-sort]");
        if (wlSortSel) {
          wlSortBy = wlSortSel.value || "priority";
          renderContent();
          return;
        }
      };

      root.onclick = async (e) => {
        if (!e.target.closest(".pm-ctx-menu")) {
          closeCtxMenu();
        }

        // 1. Azioni del menu contestuale
        const remContBtn = e.target.closest("[data-ctx-remove-continue]");
        if (remContBtn) {
          e.stopPropagation();
          closeCtxMenu();
          const k = remContBtn.dataset.ctxRemoveContinue;
          const id = remContBtn.dataset.ctxItemId;
          removeFromContinueCache(k || id);
          if (id) {
            try { await gs.api(`${apiBase}/pos`, { method: "POST", body: { id, pos: 0, seen: true } }); } catch {}
          }
          gs?.toast?.(tr("continue.removed"));
          renderContent();
          return;
        }

        const unpinS4meBtn = e.target.closest("[data-ctx-unpin-s4me]");
        if (unpinS4meBtn) {
          e.stopPropagation();
          closeCtxMenu();
          const pid = String(unpinS4meBtn.dataset.ctxUnpinS4me || "");
          if (pid) {
            try { await gs.api("/plugin-api/ricette-web/stream4me/unpin", { method: "POST", body: { id: pid } }); } catch {}
            pinnedIds.delete(pid);
            pinnedItems = pinnedItems.filter((x) => String(x.id) !== pid);
            syncItemsIndex();
            gs?.toast?.(tr("lib.removed"));
            renderContent();
          }
          return;
        }

        const pinS4meBtn = e.target.closest("[data-ctx-pin-s4me]");
        if (pinS4meBtn) {
          e.stopPropagation();
          closeCtxMenu();
          const pid = String(pinS4meBtn.dataset.ctxPinS4me || "");
          if (pid) {
            const itemObj = itemsById.get(pid) || { id: pid };
            try { await pinStream4meItem(itemObj, pid); } catch {}
            syncItemsIndex();
            gs?.toast?.("✓ " + tr("lib.added"));
            renderContent();
          }
          return;
        }

        const ctxPlayBtn = e.target.closest("[data-ctx-play]");
        if (ctxPlayBtn) {
          e.stopPropagation();
          closeCtxMenu();
          const k = ctxPlayBtn.dataset.ctxPlay;
          const id = ctxPlayBtn.dataset.ctxId;
          const item = (k ? itemsByKey.get(k) : null) || (id ? itemsById.get(id) : null);
          if (item) {
            modalHost.innerHTML = "";
            executePlay(item, () => renderContent(), episodesOf(item));
          }
          return;
        }

        const ctxDetailBtn = e.target.closest("[data-ctx-detail]");
        if (ctxDetailBtn) {
          e.stopPropagation();
          closeCtxMenu();
          const k = ctxDetailBtn.dataset.ctxDetail;
          const id = ctxDetailBtn.dataset.ctxId;
          const item = (k ? itemsByKey.get(k) : null) || (id ? itemsById.get(id) : null);
          if (item) {
            const target = (item.series && !isStream4meItem(item)) ? item.series : item;
            const season = item.season != null ? String(item.season) : null;
            await openItemDetail(target, season);
          }
          return;
        }

        const ctxFavBtn = e.target.closest("[data-ctx-fav]");
        if (ctxFavBtn) {
          e.stopPropagation();
          closeCtxMenu();
          const k = ctxFavBtn.dataset.ctxFav;
          const id = ctxFavBtn.dataset.ctxId;
          const target = k || id;
          if (target) {
            if (favs.has(target)) favs.delete(target); else favs.add(target);
            if (id && target !== id) {
              if (favs.has(target)) favs.add(id); else favs.delete(id);
            }
            saveFavs(gs, favs);
            renderContent();
          }
          return;
        }

        // Scorrimento caroselli con pulsanti frecce ‹ ›
        const scrollBtn = e.target.closest("[data-carousel-scroll]");
        if (scrollBtn) {
          e.stopPropagation();
          const dir = Number(scrollBtn.dataset.carouselScroll) || 1;
          const car = scrollBtn.closest(".pm-carousel");
          const row = car?.querySelector("[data-carousel-row]");
          if (row && typeof row.scrollBy === "function") {
            row.scrollBy({ left: dir * 600, behavior: "smooth" });
          } else if (row) {
            row.scrollLeft += dir * 600;
          }
          return;
        }

        // Modalità di visualizzazione (Panoramica / Locandine / Elenco)
        const viewModeBtn = e.target.closest("[data-view-mode]");
        if (viewModeBtn) {
          e.stopPropagation();
          viewMode = viewModeBtn.dataset.viewMode;
          try { localStorage.setItem("gs.pm_view_mode", viewMode); } catch {}
          toolbar.querySelectorAll("[data-view-mode]").forEach((b) => {
            b.classList.toggle("pm-active", b.dataset.viewMode === viewMode);
          });
          renderContent();
          return;
        }

        // Watchlist: Quick toggle sulle card
        const wlToggleBtn = e.target.closest("[data-wl-toggle]");
        if (wlToggleBtn) {
          e.stopPropagation();
          e.preventDefault();
          const k = wlToggleBtn.dataset.wlToggle;
          const id = wlToggleBtn.dataset.wlId;
          if (!k) return;
          const itemObj = itemsByKey.get(k) || (id ? itemsById.get(id) : null);
          if (watchlistMap.has(k)) {
            await removeWatchlistEntry(k);
            gs?.toast?.(tr("wl.removed"));
          } else {
            await upsertWatchlistEntry(k, { status: "plan_to_watch", priority: "medium" }, itemObj);
            gs?.toast?.("📋 " + tr("wl.added"));
          }
          if (modalHost.innerHTML && selectedDetailTarget) renderDetail(selectedDetailTarget, selectedDetailSeason);
          renderContent();
          return;
        }

        // Watchlist: Aggiungi da modal dettaglio
        const wlAddBtn = e.target.closest("[data-wl-add]");
        if (wlAddBtn) {
          e.stopPropagation();
          const k = wlAddBtn.dataset.wlAdd;
          const prio = wlAddBtn.dataset.wlAddPriority || "medium";
          const itemObj = itemsByKey.get(k) || (typeof selectedDetailTarget === "object" ? selectedDetailTarget : null);
          await upsertWatchlistEntry(k, { status: "plan_to_watch", priority: prio }, itemObj);
          gs?.toast?.("📋 " + tr("wl.added"));
          if (modalHost.innerHTML && selectedDetailTarget) renderDetail(selectedDetailTarget, selectedDetailSeason);
          renderContent();
          return;
        }

        // Watchlist: Salva nota
        const wlSaveNoteBtn = e.target.closest("[data-wl-save-note]");
        if (wlSaveNoteBtn) {
          e.stopPropagation();
          const k = wlSaveNoteBtn.dataset.wlSaveNote;
          const scope = wlSaveNoteBtn.closest(".pm-wl-controls") || root;
          const inp = scope.querySelector(`[data-wl-note-input="${CSS?.escape ? CSS.escape(k) : k}"]`) || scope.querySelector("[data-wl-note-input]");
          const notes = inp ? inp.value.trim() : "";
          await upsertWatchlistEntry(k, { notes });
          gs?.toast?.(tr("wl.noteSaved") + " ✓");
          if (modalHost.innerHTML && selectedDetailTarget) renderDetail(selectedDetailTarget, selectedDetailSeason);
          renderContent();
          return;
        }

        // Watchlist: Rimuovi
        const wlRemoveBtn = e.target.closest("[data-wl-remove]");
        if (wlRemoveBtn) {
          e.stopPropagation();
          const k = wlRemoveBtn.dataset.wlRemove;
          await removeWatchlistEntry(k);
          gs?.toast?.(tr("wl.removed"));
          if (modalHost.innerHTML && selectedDetailTarget) renderDetail(selectedDetailTarget, selectedDetailSeason);
          renderContent();
          return;
        }

        // Watchlist: scheda categoria
        const wlCatBtn = e.target.closest("[data-wl-category]");
        if (wlCatBtn) {
          e.stopPropagation();
          wlFilterCategory = wlCatBtn.dataset.wlCategory || "all";
          renderContent();
          return;
        }

        // Watchlist: riproduci / apri il titolo associato in catalogo
        const wlPlayBtn = e.target.closest("[data-wl-play]");
        if (wlPlayBtn) {
          e.stopPropagation();
          const lk = wlPlayBtn.dataset.wlPlay;
          const linkedItem = itemsByKey.get(lk) || null;
          if (!linkedItem) {
            gs?.toast?.(tr("wl.unavailable"));
          } else if (linkedItem.series && !isStream4meItem(linkedItem)) {
            await openItemDetail(linkedItem.series, null);
          } else if (linkedItem.series || linkedItem.kind === "episodio") {
            await openItemDetail(linkedItem, linkedItem.season != null ? String(linkedItem.season) : null);
          } else {
            executePlay(linkedItem, () => renderContent(), episodesOf(linkedItem));
          }
          return;
        }

        // Watchlist: cerca nel catalogo il titolo non associato
        const wlSearchBtn = e.target.closest("[data-wl-search]");
        if (wlSearchBtn) {
          e.stopPropagation();
          currentQuery = wlSearchBtn.dataset.wlSearch || "";
          if (searchInput) searchInput.value = currentQuery;
          currentTab = { film: "film", serie: "serie", anime: "anime" }[wlSearchBtn.dataset.wlSearchCat] || "tutti";
          renderContent();
          searchStream4meOnline(currentQuery);
          return;
        }

        // Watchlist: associa ai titoli trovati
        const wlMatchBtn = e.target.closest("[data-wl-match]");
        if (wlMatchBtn) {
          e.stopPropagation();
          try {
            const n = await autoLinkWatchlist();
            gs?.toast?.(n ? "🔗 " + tr("wl.matched", { n }) : tr("wl.noMatch"));
          } catch (err) {
            gs?.toast?.(tr("wl.matchFail", { err: err?.message || err }));
          }
          renderContent();
          return;
        }

        // Watchlist: esporta backup (file creato qui nel browser, nessun invio a terzi)
        if (e.target.closest("[data-wl-export]")) {
          e.stopPropagation();
          try {
            const data = await gs.api("/plugin-api/media-locale/watchlist/export");
            if (data?.error) throw new Error(data.error);
            const prof = String(data?.profile || activeProfile()).replace(/[^\w.-]+/g, "_");
            const a = document.createElement("a");
            a.href = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
            a.download = `pozzo-watchlist-${prof}-${new Date().toISOString().slice(0, 10)}.json`;
            document.body.appendChild(a); a.click(); a.remove();
            setTimeout(() => URL.revokeObjectURL(a.href), 4000);
            gs?.toast?.(tr("wl.exported"));
          } catch (err) {
            gs?.toast?.(tr("wl.exportFail", { err: err?.message || err }), true);
          }
          return;
        }

        // Watchlist: dialogo Importa
        if (e.target.closest("[data-wl-import-open]")) {
          e.stopPropagation();
          const restore = Boolean(e.target.closest("[data-wl-restore]"));
          wlImp = { provider: restore ? "pozzo" : "anilist", username: "", content: "", filename: "", raw: null, prepared: null, skipped: 0, warnings: [], defaultCat: "serie", busy: "", error: "" };
          renderWlImport();
          return;
        }
        if (wlImp && e.target.closest("[data-wli-analyze]")) {
          e.stopPropagation();
          const u = modalHost.querySelector("[data-wli-username]");
          const t = modalHost.querySelector("[data-wli-text]");
          if (u) wlImp.username = u.value.trim();
          if (t) wlImp.content = t.value;
          const body = { provider: wlImp.provider };
          if (wlImp.provider === "anilist") body.username = wlImp.username;
          else body.content = wlImp.content;
          if (!(body.username || body.content)) {
            wlImp.error = tr(wlImp.provider === "anilist" ? "wli.needUser" : "wli.needFile");
            renderWlImport();
            return;
          }
          wlImp.busy = "analyze"; wlImp.error = "";
          renderWlImport();
          try {
            const res = await gs.api("/plugin-api/media-locale/watchlist/import", { method: "POST", body });
            if (res?.error) throw new Error(res.error);
            wlImp.raw = Array.isArray(res?.entries) ? res.entries : [];
            wlImp.skipped = res?.skipped || 0;
            wlImp.warnings = Array.isArray(res?.warnings) ? res.warnings : [];
            prepareImport();
            if (!wlImp.raw.length) wlImp.error = tr("wli.none");
          } catch (err) {
            wlImp.error = err?.message || String(err);
            wlImp.prepared = null;
          }
          wlImp.busy = "";
          renderWlImport();
          return;
        }
        if (wlImp && e.target.closest("[data-wli-commit]")) {
          e.stopPropagation();
          if (wlImp.provider === "pozzo" && typeof window !== "undefined" && typeof window.confirm === "function"
            && !window.confirm(tr("wli.restoreConfirm", { n: wlImp.prepared?.length || 0 }))) return;
          wlImp.busy = "commit"; wlImp.error = "";
          renderWlImport();
          try {
            const res = await bulkSaveWatchlist(wlImp.prepared);
            if (res?.error) throw new Error(res.error);
            wlImp = null;
            modalHost.innerHTML = "";
            await loadWatchlist();
            syncItemsIndex();
            renderContent();
            gs?.toast?.(tr("wli.done", { added: res?.added ?? 0, updated: res?.updated ?? 0, skipped: res?.skipped ?? 0 }));
          } catch (err) {
            wlImp.busy = "";
            wlImp.error = err?.message || String(err);
            renderWlImport();
          }
          return;
        }

        // Watchlist: Filtro Stato (pill o tab)
        const wlFilterStBtn = e.target.closest("[data-wl-filter-status]");
        if (wlFilterStBtn) {
          e.stopPropagation();
          wlFilterStatus = wlFilterStBtn.dataset.wlFilterStatus || "all";
          if (wlFilterStBtn.dataset.wlStatPriority) {
            wlFilterPriority = wlFilterPriority === wlFilterStBtn.dataset.wlStatPriority ? "all" : wlFilterStBtn.dataset.wlStatPriority;
          } else if (wlFilterStBtn.classList.contains("pm-wl-stat-pill") && wlFilterStatus === "all") {
            wlFilterPriority = "all";
          }
          renderContent();
          return;
        }

        // Pin / Unpin elemento Stream4me nella Libreria ("come se fosse mia")
        const pinBtn = e.target.closest("[data-pin-item]");
        if (pinBtn) {
          e.stopPropagation();
          e.preventDefault();
          const pid = String(pinBtn.dataset.pinItem || "");
          if (!pid) return;
          const itemObj = itemsById.get(pid) || (typeof selectedDetailTarget === "object" ? selectedDetailTarget : null);
          const alreadyPinned = pinnedIds.has(pid);
          try {
            if (alreadyPinned) {
              await gs.api("/plugin-api/ricette-web/stream4me/unpin", { method: "POST", body: { id: pid } });
              pinnedIds.delete(pid);
              pinnedItems = pinnedItems.filter((x) => String(x.id) !== pid);
              gs?.toast?.(tr("lib.removed"));
            } else {
              await pinStream4meItem(itemObj, pid);
              gs?.toast?.("✓ " + tr("lib.added"));
            }
          } catch {
            if (alreadyPinned) {
              pinnedIds.delete(pid);
              pinnedItems = pinnedItems.filter((x) => String(x.id) !== pid);
            } else {
              await pinStream4meItem(itemObj, pid);
            }
          }
          syncItemsIndex();
          if (modalHost.innerHTML && selectedDetailTarget) {
            renderDetail(selectedDetailTarget, selectedDetailSeason);
          }
          renderContent();
          return;
        }

        // Stream4me: Aggiungi Provider dalle Impostazioni
        const addProvBtn = e.target.closest("[data-add-provider]");
        if (addProvBtn) {
          e.stopPropagation();
          const nameInp = modalHost.querySelector("#pm-prov-name");
          const hostInp = modalHost.querySelector("#pm-prov-host");
          const catSel = modalHost.querySelector("#pm-prov-cat");
          const name = nameInp?.value?.trim() || "";
          const host = hostInp?.value?.trim() || "";
          const cats = (catSel?.value || "movie,tvshow").split(",").map((s) => s.trim()).filter(Boolean);
          if (!name) return;
          const newId = name.toLowerCase().replace(/[^a-z0-9_-]+/g, "");
          const newProv = { id: newId || name, name, host, categories: cats, menus: [{ label: "Catalogo", path: "main" }] };
          try {
            await gs.api("/plugin-api/ricette-web/stream4me/providers", { method: "POST", body: newProv });
          } catch {}
          if (!s4mProviders.some((p) => String(p.id || p.name) === String(newProv.id))) {
            s4mProviders.push(newProv);
          }
          gs?.toast?.(tr("prov.added"));
          if (showSettings) renderSettings();
          renderContent();
          return;
        }

        // Stream4me: Attiva Provider Inattivo
        const enableProvBtn = e.target.closest("[data-enable-provider]");
        if (enableProvBtn) {
          e.stopPropagation();
          const sel = modalHost.querySelector("#pm-prov-enable");
          const pid = sel?.value || "";
          if (!pid) return;
          try {
            await gs.api("/plugin-api/ricette-web/stream4me/providers", { method: "POST", body: { id: pid, enable: true } });
          } catch {}
          const found = s4mInactiveProviders.find((p) => String(p.id || p.channel || p.name) === pid);
          if (found) {
            s4mProviders.push(found);
            s4mInactiveProviders = s4mInactiveProviders.filter((p) => String(p.id || p.channel || p.name) !== pid);
          }
          gs?.toast?.(tr("prov.enabled"));
          if (showSettings) renderSettings();
          renderContent();
          return;
        }

        // Stream4me: Rimuovi Provider (da impostazioni o menu contestuale tasto destro)
        const remProvBtn = e.target.closest("[data-remove-provider]");
        if (remProvBtn) {
          e.stopPropagation();
          const pid = remProvBtn.dataset.removeProvider;
          closeCtxMenu();
          if (!pid) return;
          try {
            await gs.api("/plugin-api/ricette-web/stream4me/providers/remove", { method: "POST", body: { id: pid } });
          } catch {}
          s4mProviders = s4mProviders.filter((p) => String(p.id || p.channel || p.name) !== String(pid));
          if (activeS4mProvider && String(activeS4mProvider.id || activeS4mProvider.channel || activeS4mProvider.name) === String(pid)) {
            activeS4mProvider = null;
            activeS4mPath = "";
            s4mBrowsedItems = [];
          }
          gs?.toast?.(tr("prov.removed"));
          if (showSettings) renderSettings();
          await loadData();
          renderContent();
          return;
        }

        // Navigazione Stream4me: Apri Provider
        const openProvBtn = e.target.closest("[data-open-provider]");
        if (openProvBtn) {
          e.stopPropagation();
          closeCtxMenu();
          const provId = openProvBtn.dataset.openProvider;
          const prov = s4mProviders.find((p) => String(p.id || p.channel || p.name) === String(provId)) || { id: provId, name: provId, menus: [] };
          const defaultPath = Array.isArray(prov.menus) && prov.menus[0] ? (prov.menus[0].path ?? prov.menus[0].id ?? "") : "";
          await browseStream4meProvider(prov, defaultPath, "");
          return;
        }

        // Navigazione Stream4me: Torna a tutti i provider
        const closeProvBtn = e.target.closest("[data-close-provider]");
        if (closeProvBtn) {
          e.stopPropagation();
          activeS4mProvider = null;
          activeS4mPath = "";
          s4mBrowsedItems = [];
          s4mError = "";
          renderContent();
          return;
        }

        // Navigazione Stream4me: Cambia categoria/menu del provider
        const provPathBtn = e.target.closest("[data-provider-path]");
        if (provPathBtn && activeS4mProvider) {
          e.stopPropagation();
          const pathVal = provPathBtn.dataset.providerPath || "";
          await browseStream4meProvider(activeS4mProvider, pathVal, "");
          return;
        }

        // Navigazione Stream4me: Ricerca interna nel provider o globale
        const provSearchBtn = e.target.closest("[data-provider-search-btn]");
        if (provSearchBtn) {
          e.stopPropagation();
          const inp = content.querySelector("[data-provider-search-input]");
          const qVal = inp ? inp.value.trim() : currentQuery;
          currentQuery = qVal;
          if (searchInput) searchInput.value = qVal;
          if (activeS4mProvider) {
            await browseStream4meProvider(activeS4mProvider, "", qVal);
          } else {
            await searchStream4meOnline(qVal);
          }
          return;
        }

        // Navigazione Stream4me: Riprova
        const provRetryBtn = e.target.closest("[data-provider-retry]");
        if (provRetryBtn) {
          e.stopPropagation();
          if (activeS4mProvider) {
            await browseStream4meProvider(activeS4mProvider, activeS4mPath, currentQuery);
          } else if (currentQuery) {
            await searchStream4meOnline(currentQuery);
          } else {
            await loadData();
          }
          return;
        }

        // Bottone "Cerca anche in streaming su Stream4me" dai risultati di ricerca
        const searchS4meOnlineBtn = e.target.closest("[data-search-s4me-online]");
        if (searchS4meOnlineBtn) {
          e.stopPropagation();
          const q = searchS4meOnlineBtn.dataset.searchS4meOnline || currentQuery;
          currentTab = "stream4me";
          currentQuery = q;
          if (searchInput) searchInput.value = q;
          await searchStream4meOnline(q);
          return;
        }

        // Tasto Apri Dialogo Aggiungi (Cartelle / Stream4me / Server)
        const addDialogBtn = e.target.closest("[data-open-add-dialog]");
        if (addDialogBtn) {
          e.stopPropagation();
          showSettings = true;
          await loadRoots();
          await Promise.all([loadAddonsAndRecipes(), loadSourcesState()]);
          renderSettings();
          return;
        }

        // Preferiti
        const favBtn = e.target.closest("[data-fav-key], [data-fav-id]");
        if (favBtn) {
          e.stopPropagation();
          e.preventDefault();
          const fkey = favBtn.dataset.favKey;
          const fid = favBtn.dataset.favId;
          const target = fkey || fid;
          if (target) {
            if (favs.has(target)) favs.delete(target); else favs.add(target);
            if (fid && target !== fid) {
              if (favs.has(target)) favs.add(fid); else favs.delete(fid);
            }
            saveFavs(gs, favs);
            if (modalHost.innerHTML) {
              if (selectedDetailTarget) renderDetail(selectedDetailTarget, selectedDetailSeason);
            }
            renderContent();
          }
          return;
        }

        // Tasto Apri Impostazioni Media
        if (e.target.closest("[data-open-media-window]")) {
          e.stopPropagation();
          // finestra nativa se c'è pywebview (open_media), altrimenti una finestra del browser
          try {
            if (window.pywebview?.api?.open_media) await window.pywebview.api.open_media();
            else window.open("/#media-window", "pozzo-media", "popup,width=1280,height=820");
          } catch (err) {
            gs?.toast?.(tr("window.fail", { err: err?.message || "" }), true);
          }
          return;
        }

        const openSettingsBtn = e.target.closest("[data-open-settings]");
        if (openSettingsBtn) {
          e.stopPropagation();
          showSettings = true;
          await loadRoots();
          await loadAddonsAndRecipes();
          renderSettings();
          return;
        }

        // Tasti Chiudi Modal o Impostazioni
        const closeSettingsBtn = e.target.closest("[data-close-settings]");
        if (closeSettingsBtn) {
          e.stopPropagation();
          showSettings = false;
          modalHost.innerHTML = "";
          return;
        }

        const closeModalBtn = e.target.closest("[data-close-modal]");
        if (closeModalBtn) {
          e.stopPropagation();
          selectedDetailTarget = null;
          selectedDetailSeason = null;
          modalHost.innerHTML = "";
          return;
        }

        // Click su backdrop overlay per chiudere
        if (e.target.hasAttribute("data-close-modal-backdrop")) {
          e.stopPropagation();
          selectedDetailTarget = null;
          selectedDetailSeason = null;
          modalHost.innerHTML = "";
          return;
        }
        if (e.target.hasAttribute("data-close-settings-backdrop")) {
          e.stopPropagation();
          showSettings = false;
          modalHost.innerHTML = "";
          return;
        }

        // Switch Tab Impostazioni
        const refreshCatBtn = e.target.closest("[data-refresh-catalog]");
        if (refreshCatBtn) {
          e.stopPropagation();
          try {
            catalogStatus = await gs.api("/plugin-api/ricette-web/catalog/refresh", { body: {} });
          } catch (err) {
            gs?.toast?.(tr("refresh.fail", { err: err?.message || err }), true);
            return;
          }
          renderSettings();
          pollCatalog();
          return;
        }

        // Quick Enrich dalla toolbar o dal pannello impostazioni
        const quickEnrichBtn = e.target.closest("[data-quick-enrich]");
        const enrichMetaBtn = e.target.closest("[data-enrich-metadata]");
        if (quickEnrichBtn || enrichMetaBtn) {
          e.stopPropagation();
          const stEl = modalHost.querySelector(".pm-enrich-status");
          if (stEl) stEl.textContent = tr("enrich.running");
          gs?.toast?.(tr("enrich.started"));
          try {
            const res = await gs.api(`${apiBase}/enrich`, { method: "POST", body: {} });
            gs?.toast?.(res?.message || tr("enrich.done", { n: res?.enriched ?? 0 }));
            if (stEl) stEl.textContent = tr("done") + " ✓";
            await loadData();
          } catch (err) {
            if (stEl) stEl.textContent = tr("enrich.bg") + " ✓";
            gs?.toast?.(tr("enrich.bgToast"));
          }
          return;
        }

        // Cartelle: Sfoglia con pywebview
        const pickBtn = e.target.closest("[data-pick-root]");
        if (pickBtn) {
          e.stopPropagation();
          try {
            const p = await window.pywebview?.api?.pick_folder?.();
            const inp = modalHost.querySelector(".pm-root-input");
            if (p && inp) inp.value = p;
          } catch {}
          return;
        }

        // Cartelle: Aggiungi
        const addRootBtn = e.target.closest("[data-add-root]");
        if (addRootBtn) {
          e.stopPropagation();
          const inp = modalHost.querySelector(".pm-root-input");
          const raw = inp ? inp.value.trim() : "";
          if (!raw) return;
          scanning = true;
          renderSettings();
          try {
            await gs.api(`${apiBase}/roots`, { body: { add: raw } });
            const res = await gs.api(`${apiBase}/scan`, { body: {} });
            roots = Array.isArray(res?.roots) ? res.roots : roots;
            gs?.toast?.(tr("scan.done", { n: res?.items ?? 0 }));
            await loadData();
          } catch (err) {
            gs?.toast?.(err?.message || tr("folder.addFail"), true);
          } finally {
            scanning = false;
            renderSettings();
          }
          return;
        }

        // Cartelle: Rimuovi
        const remRootBtn = e.target.closest("[data-remove-root]");
        if (remRootBtn) {
          e.stopPropagation();
          const rem = remRootBtn.dataset.removeRoot;
          if (!rem) return;
          try {
            const res = await gs.api(`${apiBase}/roots`, { body: { remove: rem } });
            roots = Array.isArray(res?.roots) ? res.roots : [];
            renderSettings();
            await loadData();
          } catch (err) {
            gs?.toast?.(err?.message || tr("folder.removeFail"), true);
          }
          return;
        }

        // Cartelle: Scansiona ora
        const scanNowBtn = e.target.closest("[data-scan-now]");
        if (scanNowBtn) {
          e.stopPropagation();
          if (scanning) return;
          scanning = true;
          renderSettings();
          try {
            const res = await gs.api(`${apiBase}/scan`, { body: {} });
            roots = Array.isArray(res?.roots) ? res.roots : roots;
            gs?.toast?.(tr("scan.done", { n: res?.items ?? 0 }));
            await loadData();
          } catch (err) {
            gs?.toast?.(err?.message || tr("scan.fail"), true);
          } finally {
            scanning = false;
            renderSettings();
          }
          return;
        }

        // Server: Salva
        const saveServerBtn = e.target.closest("[data-save-server]");
        if (saveServerBtn) {
          e.stopPropagation();
          const urlInp = modalHost.querySelector("#pm-server-url");
          const tokenInp = modalHost.querySelector("#pm-server-token");
          const typeSel = modalHost.querySelector("#pm-server-type");
          const stEl = modalHost.querySelector(".pm-server-status");
          try {
            const payload = buildServerPayload({
              type: typeSel?.value, url: urlInp?.value, key: tokenInp?.value,
              user: modalHost.querySelector("#pm-server-user")?.value, password: modalHost.querySelector("#pm-server-pass")?.value,
            });
            await gs.api("/plugin-api/media-server/config", { body: payload });
            if (stEl) stEl.textContent = tr("saved") + " ✓";
            gs?.toast?.(tr("server.saved"));
            await loadData();
          } catch (err) {
            if (stEl) stEl.textContent = tr("src.error");
            gs?.toast?.(err?.message || tr("server.saveFail"), true);
          }
          return;
        }

        // Server: Test
        const testServerBtn = e.target.closest("[data-test-server]");
        if (testServerBtn) {
          e.stopPropagation();
          const stEl = modalHost.querySelector(".pm-server-status");
          if (stEl) stEl.textContent = tr("src.unknown");
          try {
            const res = await gs.api(`/plugin-api/media-server/test?source=${encodeURIComponent(modalHost.querySelector("#pm-server-type")?.value || "jellyfin")}`);
            if (stEl) stEl.textContent = res?.ok ? "Online ✓" : (res?.error || tr("unreachable"));
            gs?.toast?.(tr(res?.ok ? "server.ok" : "server.down"), !res?.ok);
          } catch (err) {
            if (stEl) stEl.textContent = "Offline ✕";
            gs?.toast?.(err?.message || tr("server.testFail"), true);
          }
          return;
        }

        // Stream4me: pulisce i provider eliminati e riscansiona quelli attivi
        const cleanS4mBtn = e.target.closest("[data-cleanup-stream4me]");
        if (cleanS4mBtn) {
          e.stopPropagation();
          cleanS4mBtn.disabled = true;
          gs?.toast?.(tr("s4m.cleaning"));
          try {
            const r = await gs.api("/plugin-api/ricette-web/stream4me/cleanup", { method: "POST", body: {} });
            gs?.toast?.(tr("s4m.cleaned", { removed: r?.removed ?? 0, refreshed: r?.refreshed ?? 0 }));
            await loadData();
            if (showSettings) renderSettings();
          } catch (err) {
            gs?.toast?.(err?.message || tr("s4m.cleanFail"), true);
            cleanS4mBtn.disabled = false;
          }
          return;
        }

        // Stream4me: Installa / Aggiorna
        const installS4mBtn = e.target.closest("[data-install-stream4me]");
        if (installS4mBtn) {
          e.stopPropagation();
          gs?.toast?.(tr("s4m.installing"));
          try {
            try {
              await gs.api("/plugin-api/ricette-web/stream4me/install", { method: "POST", body: {} });
            } catch {
              await gs.api("/plugin-api/ricette-web/kodi_addons", {
                body: { url: "https://github.com/stream4me/stream4me" }
              });
            }
            gs?.toast?.("Stream4me pronto all'uso!");
            await loadAddonsAndRecipes();
            if (showSettings) renderSettings();
            await loadData();
          } catch (err) {
            gs?.toast?.(err?.message || tr("s4m.installFail"), true);
          }
          return;
        }

        // Addon: Installa da custom url / zip
        const installAddonBtn = e.target.closest("[data-install-addon]");
        if (installAddonBtn) {
          e.stopPropagation();
          const inp = modalHost.querySelector("#pm-addon-input");
          const val = inp?.value?.trim() || "";
          if (!val) return;
          try {
            const payload = val.startsWith("http") ? { url: val } : { path: val };
            await gs.api("/plugin-api/ricette-web/kodi_addons", { body: payload });
            gs?.toast?.(tr("addon.installed"));
            if (inp) inp.value = "";
            await loadAddonsAndRecipes();
            renderSettings();
            await loadData();
          } catch (err) {
            gs?.toast?.(err?.message || tr("addon.installFail"), true);
          }
          return;
        }

        // Cambio Stagione dentro Modal Dettagli
        const modalSeasonBtn = e.target.closest("[data-modal-season]");
        if (modalSeasonBtn) {
          e.stopPropagation();
          selectedDetailSeason = modalSeasonBtn.dataset.modalSeason;
          if (selectedDetailTarget) renderDetail(selectedDetailTarget, selectedDetailSeason);
          return;
        }

        // Clic su serie o anime -> Apre Modal Dettagli Netflix (e carica episodi Stream4me se serie Stream4me)
        const seriesCard = e.target.closest("[data-series-name]");
        if (seriesCard) {
          e.stopPropagation();
          const sName = seriesCard.dataset.seriesName;
          await openItemDetail(sName, null);
          return;
        }

        // Clic su "ℹ ${tx("moreInfo")}" o card generica
        const detailBtn = e.target.closest("[data-detail-key], [data-detail-id], [data-s4me-open]");
        const playBtn = e.target.closest("[data-play-key], [data-play-id]");

        // Se clicca direttamente su Riproduci (o un episodio nella modale)
        if (playBtn && (!detailBtn || e.target.closest(".pm-player-btn.pm-primary") || e.target.closest(".pm-episode-card"))) {
          e.stopPropagation();
          const key = playBtn.dataset.playKey;
          const id = playBtn.dataset.playId;
          const item = (key ? itemsByKey.get(key) : null) || (id ? itemsById.get(id) : null);
          if (item) {
            modalHost.innerHTML = "";
            executePlay(item, () => renderContent(), episodesOf(item));
          }
          return;
        }

        if (detailBtn) {
          e.stopPropagation();
          const key = detailBtn.dataset.detailKey;
          const id = detailBtn.dataset.detailId || detailBtn.dataset.s4meOpen;
          const item = (key ? itemsByKey.get(key) : null) || (id ? itemsById.get(id) : null);
          if (item) {
            const target = (item.series && !isStream4meItem(item)) ? item.series : item;
            const season = item.season != null ? String(item.season) : null;
            await openItemDetail(target, season);
          } else if (key && key.startsWith("series:")) {
            await openItemDetail(key.slice(7), null);
          }
          return;
        }

        // Switch Tab Barra Principale (0ms istantaneo in memoria!)
        const tabBtn = e.target.closest("[data-tab]");
        if (tabBtn) {
          e.stopPropagation();
          currentTab = tabBtn.dataset.tab;
          selectedDetailTarget = null;
          selectedDetailSeason = null;
          renderContent();
          if (currentTab === "stream4me" && currentQuery.length >= 2) {
            searchStream4meOnline(currentQuery);
          }
          return;
        }

        // Toggle Solo Preferiti
        const favToggleBtn = e.target.closest("[data-toggle-favs]");
        if (favToggleBtn) {
          e.stopPropagation();
          filterOnlyFavs = !filterOnlyFavs;
          renderContent();
          return;
        }
      };

      sourceSelect.onchange = () => {
        currentSource = sourceSelect.value;
        renderContent();
      };

      let searchTimer;
      let s4mSearchTimer;
      searchInput.oninput = () => {
        clearTimeout(searchTimer);
        clearTimeout(s4mSearchTimer);
        searchTimer = setTimeout(() => {
          currentQuery = searchInput.value.trim();
          renderContent();
        }, 120);
        s4mSearchTimer = setTimeout(() => {
          const q = searchInput.value.trim();
          if (activeS4mProvider) return; // dentro un provider la ricerca è la sua (Invio nel suo campo)
          if (q.length >= 2 && currentTab !== "watchlist" && currentTab !== "musica") {
            searchStream4meOnline(q);
          } else if (!q && s4mSearchQuery) {
            s4mSearchSeq++; s4mSearchQuery = ""; s4mSearchMeta = null; s4mBrowsedItems = []; s4mLoading = false; s4mError = "";
            renderContent();
          }
        }, 400);
      };

      root.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && e.target.matches("[data-provider-search-input]")) {
          e.preventDefault();
          const qVal = e.target.value.trim();
          currentQuery = qVal;
          if (searchInput) searchInput.value = qVal;
          if (activeS4mProvider) {
            browseStream4meProvider(activeS4mProvider, "", qVal);
          } else {
            searchStream4meOnline(qVal);
          }
        }
      });

      let activeHoverCard = null;
      root.addEventListener("mouseover", (e) => {
        const card = e.target.closest(".pm-card, .pm-resume-card, .pm-list-row, .pm-wl-card, [data-play-key], [data-detail-key]");
        if (card) activeHoverCard = card;
      });

      if (pmActiveKeyDown && typeof document !== "undefined") {
        document.removeEventListener("keydown", pmActiveKeyDown);
      }

      const onKeyDown = async (e) => {
        if (e.key === "Escape") {
          modalHost.innerHTML = "";
          closeCtxMenu();
          showSettings = false;
          selectedDetailTarget = null;
          selectedDetailSeason = null;
          return;
        }

        const activeTag = document.activeElement?.tagName?.toLowerCase();
        if (activeTag === "input" || activeTag === "textarea" || activeTag === "select" || document.activeElement?.isContentEditable) {
          return;
        }

        const targetCard = activeHoverCard || document.activeElement?.closest?.(".pm-card, .pm-resume-card, .pm-list-row, .pm-wl-card, [data-play-key], [data-detail-key]");
        if (!targetCard) return;

        const k = targetCard.dataset.detailKey || targetCard.dataset.playKey || targetCard.dataset.wlCard || "";
        const id = targetCard.dataset.detailId || targetCard.dataset.playId || "";
        const item = (k ? itemsByKey.get(k) : null) || (id ? itemsById.get(id) : null);

        if (e.key === "Delete" || e.key === "Backspace") {
          const isContinue = Boolean(targetCard.closest(".pm-resume-card") || (item && item.resume_pos > 0));
          const isPinned = Boolean(id && pinnedIds.has(String(id)));
          if (isContinue) {
            e.preventDefault();
            removeFromContinueCache(k || id);
            if (id) {
              try { await gs.api(`${apiBase}/pos`, { method: "POST", body: { id, pos: 0, seen: true } }); } catch {}
            }
            gs?.toast?.(tr("continue.removed"));
            renderContent();
          } else if (isPinned) {
            e.preventDefault();
            try { await gs.api("/plugin-api/ricette-web/stream4me/unpin", { method: "POST", body: { id } }); } catch {}
            pinnedIds.delete(String(id));
            pinnedItems = pinnedItems.filter((x) => String(x.id) !== String(id));
            syncItemsIndex();
            gs?.toast?.(tr("lib.removed"));
            renderContent();
          }
        } else if (e.key === "f" || e.key === "F") {
          const target = k || id;
          if (target) {
            e.preventDefault();
            if (favs.has(target)) favs.delete(target); else favs.add(target);
            if (id && target !== id) {
              if (favs.has(target)) favs.add(id); else favs.delete(id);
            }
            saveFavs(gs, favs);
            renderContent();
          }
        }
      };
      pmActiveKeyDown = onKeyDown;
      if (typeof document !== "undefined") {
        document.addEventListener("keydown", onKeyDown);
      }

      // finestra Media separata: riprende l'episodio che il lettore dell'altra finestra ha lasciato in consegna
      // (subito all'apertura, oppure più tardi se la finestra c'era già: lo dice l'evento «storage»)
      const consumeHandoff = () => {
        if (typeof document === "undefined" || !document.body.classList.contains("media-window")) return;
        const h = takeHandoff();
        if (!h) return;
        modalHost.innerHTML = "";
        executePlay(h.item, () => renderContent(), h.episodes, { resumeAt: h.pos });
      };
      if (typeof window !== "undefined") {
        if (pmStorageHandler) window.removeEventListener("storage", pmStorageHandler);
        pmStorageHandler = (e) => { if (e.key === HANDOFF_KEY && e.newValue) consumeHandoff(); };
        window.addEventListener("storage", pmStorageHandler);
      }
      consumeHandoff();

      await loadRoots();
      await loadData();
    },
  };

  gs.registerView(sidebarId, viewDef);
  if (sidebarId !== "media") gs.registerView("media", viewDef);
  if (sidebarId !== "media-locale") gs.registerView("media-locale", viewDef);
}

// Auto-registrazione nel dashboard globale se GS.ui.registerWidget e' gia' definito
if (typeof window !== "undefined" && typeof window.GS?.ui?.registerWidget === "function") {
  registerMediaWidget(window.GS);
}
