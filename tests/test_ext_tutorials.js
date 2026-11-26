// Tutorial delle estensioni (exttutorials.js, solo logica). Esegui: node tests/test_ext_tutorials.js
const assert = require("node:assert/strict");
const { KEY, create } = require("../pozzo/app/static/exttutorials.js");

const mem = () => { const m = new Map(); return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => m.set(k, String(v)), m }; };
const make = (opts = {}) => {
  const started = [];
  const env = { store: mem(), blocked: () => false, start: (steps, tut) => { started.push({ steps, tut }); return opts.ok ?? true; }, ...opts.env };
  return { T: create(env), env, started };
};

{ // parte da solo una volta sola, solo per la sua vista o sezione
  const { T, env, started } = make();
  T.add({ id: "diario", view: "diario", section: "diario-sec", steps: [{ title: "Ciao", text: "Testo", sel: ".x" }, { title: "Fine" }] });
  assert.equal(T.auto("altro"), false);
  assert.equal(T.auto("diario-sec"), true);
  assert.equal(started.length, 1);
  const [a, b] = started[0].steps;
  assert.deepEqual({ id: a.id, title: a.title, text: a.text(), sel: a.sel }, { id: "diario-0", title: "Ciao", text: "Testo", sel: [".x"] });
  assert.equal(b.sel, undefined); // senza sel: scheda al centro
  assert.equal(T.auto("diario"), false); // gia' visto
  assert.deepEqual(JSON.parse(env.store.getItem(KEY)), { diario: true });
  assert.equal(T.show("diario"), true); // dal pulsante «?» si rivede sempre
  assert.equal(started.length, 2);
  T.reset();
  assert.equal(T.auto("diario"), true);
}
{ // tour bloccato (dialogo aperto) o non partito: non segna come visto
  const { T } = make({ env: { blocked: () => true } });
  T.add({ id: "a", view: "a", steps: [{ title: "x" }] });
  assert.equal(T.auto("a"), false);
  assert.deepEqual(T.seen(), {});
  const r = make({ ok: false });
  r.T.add({ id: "a", view: "a", steps: [{ title: "x" }] });
  assert.equal(r.T.auto("a"), false);
  assert.deepEqual(r.T.seen(), {});
}
{ // validazione, rimozione, storage rotto o assente
  const { T } = make();
  assert.throws(() => T.add({ id: "x", steps: [] }));
  assert.throws(() => T.add({ steps: [{ title: "x" }] }));
  T.add({ id: "x", view: "x", steps: [{ title: "x" }] });
  assert.equal(T.has("x"), true);
  T.remove("x");
  assert.equal(T.has("x"), false);
  assert.equal(T.show("x"), false);
  const bad = create({ store: { getItem: () => "{rotto", setItem: () => { throw new Error("pieno"); } }, blocked: () => false, start: () => true });
  bad.add({ id: "y", view: "y", steps: [{ title: "y" }] });
  assert.equal(bad.auto("y"), true); // niente eccezioni: si rivedra'
  const none = create({ store: null, blocked: () => false, start: () => true });
  none.add({ id: "z", view: "z", steps: [{ title: "z" }] });
  assert.equal(none.auto("z"), true);
}
console.log("test_ext_tutorials: ok");
