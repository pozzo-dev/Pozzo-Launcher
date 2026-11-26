// Tema attivo, tema utente e preferenza movimento (data-motion) per tutte le finestre overlay (CSP: script esterno).
(() => {
  const root = document.documentElement;
  const MOTIONS = new Set(["normal", "reduced", "off"]);
  const TOKENS = ["bg", "bg-2", "bg-3", "panel", "line", "text", "muted", "accent"];
  const HEX = /^#[0-9a-f]{6}$/i;

  let motion = null;
  try {
    const saved = JSON.parse(localStorage.getItem("gs.motion"));
    if (MOTIONS.has(saved)) motion = saved;
  } catch { /* storage non disponibile */ }
  if (!motion) {
    const reduced = typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
    motion = reduced ? "reduced" : "normal";
  }
  root.dataset.motion = motion;

  let userThemeCss = "";
  try {
    const ut = JSON.parse(localStorage.getItem("gs.userTheme"));
    if (ut && ut.enabled === true && ut.tokens && TOKENS.every((k) => typeof ut.tokens[k] === "string" && HEX.test(ut.tokens[k]))) {
      userThemeCss = `html:root{${TOKENS.map((k) => `--${k}:${ut.tokens[k].toLowerCase()}`).join(";")}}`;
    }
  } catch { /* nessun tema utente */ }
  if (userThemeCss) {
    const s = document.createElement("style");
    s.id = "gs-user-theme";
    s.textContent = userThemeCss;
    document.head.appendChild(s);
  }

  if (typeof fetch === "function") {
    fetch("/api/extensions").then((r) => (r.ok ? r.json() : null)).then((ext) => {
      if (!ext || !Array.isArray(ext.themes)) return;
      const th = ext.themes.find((x) => x.id === ext.active_theme);
      root.dataset.theme = ext.active_theme || "default";
      if (th && typeof th.desktop === "string" && th.desktop.startsWith("/") && !th.desktop.startsWith("//")) {
        const l = document.createElement("link");
        l.rel = "stylesheet";
        l.href = th.desktop;
        const userEl = document.getElementById("gs-user-theme");
        if (userEl && document.head.insertBefore) document.head.insertBefore(l, userEl);
        else document.head.appendChild(l);
      }
    }).catch(() => {});
  }
})();
