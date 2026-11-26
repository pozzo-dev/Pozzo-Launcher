// Tutorial delle estensioni: passi propri mostrati con il tour (GS.tour.start({steps})).
// Partono da soli la prima volta che si apre la pagina o la sezione dell'estensione; poi si rivedono dal pulsante «?».
// Logica pura in create(env), testata in tests/test_ext_tutorials.js.
(() => {
  const KEY = "gs.ext-tutorials";

  /** env: {store, start(steps, tut) -> bool, blocked() -> bool} */
  function create(env) {
    const reg = new Map();
    const read = () => {
      try { const v = JSON.parse(env.store?.getItem(KEY) || "{}"); return v && typeof v === "object" ? v : {}; } catch { return {}; }
    };
    const write = (st) => { try { env.store?.setItem(KEY, JSON.stringify(st)); } catch { /* storage bloccato: si rivedra' */ } };
    // il tour vuole text(k) e sel come elenco di selettori; senza sel la scheda sta al centro
    const toTour = (tut) => tut.steps.map((s, i) => ({
      id: `${tut.id}-${i}`, title: String(s.title || ""), text: () => String(s.text || ""),
      sel: s.sel ? [].concat(s.sel) : undefined,
    }));
    const keys = (tut) => [].concat(tut.view || [], tut.section || []);

    function add(tut) {
      if (!tut || !tut.id || !Array.isArray(tut.steps) || !tut.steps.length) throw new Error("addTutorial: servono id e steps");
      reg.set(tut.id, tut);
      return tut;
    }
    function show(id) {
      const tut = reg.get(id);
      if (!tut || !env.start(toTour(tut), tut)) return false;
      write({ ...read(), [id]: true });
      return true;
    }
    /** key: id della vista o della sezione appena mostrata. Al massimo un tutorial, mai due volte. */
    function auto(key) {
      const seen = read();
      const tut = [...reg.values()].find((x) => !seen[x.id] && keys(x).includes(key));
      return !!tut && !env.blocked() && show(tut.id);
    }
    return { add, show, auto, has: (id) => reg.has(id), remove: (id) => reg.delete(id), reset: () => write({}), seen: read };
  }

  if (typeof window === "undefined") { module.exports = { KEY, create }; return; }

  let store = null;
  try { store = window.localStorage; } catch { /* storage bloccato */ }
  window.GS = window.GS || {};
  window.GS.tutorials = create({
    store,
    // dallo store (o da un'altra pagina) si apre prima la pagina dell'estensione, cosi' i passi trovano i loro elementi
    start: (steps, tut) => {
      const go = () => !!window.GS.tour?.start({ steps });
      const view = [].concat(tut.view || [])[0];
      if (!view || typeof S === "undefined" || typeof setView !== "function" || (S.view.type === "plugin" && S.view.id === view)) return go();
      setView({ type: "plugin", id: view });
      setTimeout(go, 400);
      return true;
    },
    blocked: () => !!(window.GS.tour?.isActive() || document.querySelector("dialog[open], .onb, #settings-page:not([hidden])")),
  });
})();
