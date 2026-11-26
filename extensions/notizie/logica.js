// Helper puri di Notizie (senza DOM): data relativa, normalizzazione, filtro «miei giochi».

// tipi di notizia (i nomi stanno nel locales.json dell'estensione: kind.<tipo>)
export const KINDS = ["annuncio", "patch", "dlc", "uscita", "notizia"];

export const fold = (s) => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
  .replace(/[^a-z0-9]+/g, " ").trim();

/** «5 minuti fa», «ieri»… nella lingua dell'interfaccia; oltre una settimana la data. */
export function relDate(iso, now = Date.now(), lang = "it") {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "";
  const s = Math.max(0, Math.round((now - t) / 1000));
  const rel = new Intl.RelativeTimeFormat(lang, { numeric: "auto" });
  if (s < 60) return rel.format(0, "second");
  if (s < 3600) return rel.format(-Math.floor(s / 60), "minute");
  if (s < 86400) return rel.format(-Math.floor(s / 3600), "hour");
  if (s < 86400 * 7) return rel.format(-Math.floor(s / 86400), "day");
  return new Date(t).toLocaleDateString(lang, { day: "numeric", month: "short", year: "numeric" });
}

export const safeUrl = (u) => (/^https?:\/\//i.test(String(u || "")) ? String(u) : "");

export const validUrl = (u) => { try { return /^https?:$/.test(new URL(u).protocol); } catch { return false; } };

// Insiemi normalizzati dalla libreria: titoli (>=4 caratteri) e nomi piattaforma.
export function buildSets(lib) {
  const titles = new Set(), plats = new Set();
  for (const g of lib?.games || []) { const f = fold(g.title); if (f.length >= 4) titles.add(f); }
  for (const p of lib?.plats?.values?.() || []) { const f = fold(p.name); if (f.length >= 3) plats.add(f); }
  return { titles, plats };
}

// shortcut: scansione lineare titoli x notizie, ok per librerie di migliaia di giochi; indicizzare se rallenta.
export function matcher(sets) {
  return (item) => {
    const h = ` ${fold(`${item.title} ${item.summary}`)} `;
    for (const t of sets.titles) if (h.includes(` ${t} `)) return true;
    for (const p of sets.plats) if (h.includes(` ${p} `)) return true;
    return false;
  };
}

export const filterMine = (items, match) => items.filter(match);
export const upcoming = (items) => items.filter((i) => i.kind === "annuncio" || i.kind === "uscita");
