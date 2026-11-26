// Calendario uscite: logica pura (provata in tests/test_extensions_nuove.py).

const pad = (n) => String(n).padStart(2, "0");

/** Nomi brevi dei giorni, da lunedi' a domenica, nella lingua dell'interfaccia. */
export function settimane(lang) {
  return [...Array(7)].map((_, i) => new Date(2024, 0, 1 + i).toLocaleDateString(lang, { weekday: "short" }));  // 1/1/2024 = lunedi'
}

/** Uscite (con data AAAA-MM-GG) raggruppate per mese, con le celle del calendario: null prima del giorno 1. */
export function perMese(uscite, oggi = new Date()) {
  const oggiS = `${oggi.getFullYear()}-${pad(oggi.getMonth() + 1)}-${pad(oggi.getDate())}`;
  const mesi = new Map();
  for (const v of uscite || []) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(v.data || "")) continue;
    const k = v.data.slice(0, 7);
    if (!mesi.has(k)) mesi.set(k, []);
    mesi.get(k).push(v);
  }
  return [...mesi].sort(([a], [b]) => a.localeCompare(b)).map(([chiave, lista]) => {
    const [y, m] = chiave.split("-").map(Number);
    const giorni = new Date(y, m, 0).getDate();
    const vuote = (new Date(y, m - 1, 1).getDay() + 6) % 7;  // lunedi' = 0
    const celle = [...Array(vuote)].map(() => null);
    for (let g = 1; g <= giorni; g++) {
      const data = `${chiave}-${pad(g)}`;
      celle.push({ giorno: g, data, oggi: data === oggiS, uscite: lista.filter((v) => v.data === data) });
    }
    return { chiave, celle, uscite: [...lista].sort((a, b) => a.data.localeCompare(b.data)) };
  });
}
