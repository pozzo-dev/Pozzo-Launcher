"""Store delle estensioni: indice aggiornato, installazione verificata (sha256, nomi, versione minima), rimozione,
copia di sviluppo intoccabile, store sempre primo e sempre attivo.

Esegui: python tests/test_extstore.py
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from pozzo import config as C  # noqa: E402
from pozzo.app import extensions as X  # noqa: E402
from pozzo.app import extstore as S  # noqa: E402
import extensions as T  # noqa: E402  (tools/extensions.py)


def cfg_in(t: Path, index: Path) -> C.Config:
    cfg = C.Config(cache=t / "cache")
    cfg.config_path = t / "config.toml"
    cfg.app = {"extensions_index": str(index)}
    return cfg


def expect(fn, text: str):
    try:
        fn()
    except ValueError as e:
        assert text in str(e), e
        return
    raise AssertionError(f"doveva rifiutare: {text}")


def main():
    # l'indice nel repository corrisponde ai file: chi modifica un'estensione deve rigenerarlo (tools/extensions.py index)
    assert T.render(T.build_index()) == T.INDEX.read_text(encoding="utf-8"), "extensions/index.json non aggiornato"
    print("ok  extensions/index.json aggiornato")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
        t = Path(t)
        repo = t / "repo"
        shutil.copytree(T.EXT, repo)
        cfg = cfg_in(t, repo / "index.json")
        plugins = X.user_dir(cfg, "plugins")

        ids = [p["id"] for p in X.list_plugins(cfg)]
        assert ids == [S.STORE_ID], ids  # nell'app c'e' solo lo store
        cat = {x["id"]: x for x in S.catalog(cfg)["items"]}
        assert set(cat) == {d.name for d in T.EXT.iterdir() if (d / "plugin.toml").exists()}      # tutte quelle del repository
        assert {"linkstores", "minerva", "riepilogo-annuale"} <= set(cat) and cat["riepilogo-annuale"]["state"] == "available"

        r = S.install(cfg, "riepilogo-annuale")
        assert r["ok"] and (plugins / "riepilogo-annuale" / "backend.py").is_file()
        ps = X.list_plugins(cfg)
        assert [p["id"] for p in ps] == [S.STORE_ID, "riepilogo-annuale"] and ps[0]["locked"] and ps[1]["enabled"]
        cat = {x["id"]: x for x in S.catalog(cfg)["items"]}
        assert cat["riepilogo-annuale"]["state"] == "installed"
        assert cat["riepilogo-annuale"]["installed_permissions"] == ["libreria:lettura"] and cat["minerva"]["installed_permissions"] is None
        print("ok  installazione da indice locale, store per primo")

        # aggiornamento: versione piu' alta nell'indice -> «update», reinstallando si sostituisce la cartella
        idx = json.loads((repo / "index.json").read_text(encoding="utf-8"))
        st = next(e for e in idx["extensions"] if e["id"] == "riepilogo-annuale")
        st["version"] = "9.0"
        (repo / "index.json").write_text(json.dumps(idx), encoding="utf-8")
        assert {x["id"]: x for x in S.catalog(cfg)["items"]}["riepilogo-annuale"]["state"] == "update"
        (plugins / "riepilogo-annuale" / "vecchio.txt").write_text("x")
        S.install(cfg, "riepilogo-annuale")
        assert not (plugins / "riepilogo-annuale" / "vecchio.txt").exists()
        assert not [d for d in plugins.iterdir() if d.name.startswith(".")]  # niente .tmp/.old lasciati
        print("ok  aggiornamento")

        # contenuto diverso dall'indice: rifiutato e niente installato
        (repo / "minerva" / "backend.py").write_text("import os  # manomesso\n")
        expect(lambda: S.install(cfg, "minerva"), "sha256")
        assert not (plugins / "minerva").exists()
        # nomi di file con percorsi, versione minima, id sconosciuto, store stesso
        mv = next(e for e in idx["extensions"] if e["id"] == "minerva")
        mv["files"]["../fuori.py"] = mv["files"]["backend.py"]
        lk = next(e for e in idx["extensions"] if e["id"] == "linkstores")
        lk["min_app"] = "99.0.0"
        idx["extensions"].append({"id": S.STORE_ID, "files": {"plugin.toml": "0"}})
        (repo / "index.json").write_text(json.dumps(idx), encoding="utf-8")
        expect(lambda: S.install(cfg, "minerva"), "nomi di file")
        expect(lambda: S.install(cfg, "linkstores"), "richiede PozzoLauncher 99.0.0")
        assert {x["id"]: x for x in S.catalog(cfg)["items"]}["linkstores"]["state"] == "incompatible"
        expect(lambda: S.install(cfg, S.STORE_ID), "non trovata")
        expect(lambda: S.remove(cfg, S.STORE_ID), "non si puo' rimuovere")
        assert not (t / "fuori.py").exists() and not (plugins.parent / "fuori.py").exists()
        print("ok  rifiutati: sha256 sbagliato, percorsi nei nomi, versione minima, store")

        S.remove(cfg, "riepilogo-annuale")
        assert not (plugins / "riepilogo-annuale").exists()
        expect(lambda: S.remove(cfg, "riepilogo-annuale"), "non installata")

        # copia di sviluppo collegata: lo store non la aggiorna ne' la cancella (sarebbero i sorgenti)
        link = plugins / "linkstores"
        if sys.platform == "win32":
            subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(repo / "linkstores")], check=True, capture_output=True)
        else:
            link.symlink_to(repo / "linkstores", target_is_directory=True)
        assert {x["id"]: x for x in S.catalog(cfg)["items"]}["linkstores"]["dev"] is True
        expect(lambda: S.remove(cfg, "linkstores"), "sviluppo")
        lk["min_app"] = "0"
        (repo / "index.json").write_text(json.dumps(idx), encoding="utf-8")
        expect(lambda: S.install(cfg, "linkstores"), "sviluppo")
        assert (repo / "linkstores" / "backend.py").is_file()
        link.rmdir() if sys.platform == "win32" else link.unlink()
        print("ok  copia di sviluppo collegata intoccabile")

        # uno «estensioni» messo a mano nella cartella utente non sostituisce lo store incluso
        (plugins / S.STORE_ID).mkdir()
        (plugins / S.STORE_ID / "plugin.toml").write_text('[plugin]\nname = "finto"\n')
        assert X.list_plugins(cfg)[0]["name"] == "Store estensioni"
        # disattivato in impostazioni vecchie: resta attivo
        cfg.app["disabled_plugins"] = [S.STORE_ID]
        assert X.list_plugins(cfg)[0]["enabled"]
        print("ok  store sempre quello incluso e sempre attivo")

        # cartella di un'estensione non attraversabile (WinError 448, junction non attendibile): l'app parte lo stesso,
        # l'estensione compare disattivata con il motivo, le altre restano
        cfg.app["disabled_plugins"] = []
        (plugins / "buona").mkdir()
        (plugins / "buona" / "plugin.toml").write_text('[plugin]\nname = "Buona"\n')
        (plugins / "rotta").mkdir()
        real = X._manifest

        def broken(d):
            if d.name == "rotta":
                raise OSError(448, "Impossibile attraversare il percorso perche' contiene un punto di montaggio non attendibile")
            return real(d)
        X._manifest = broken
        try:
            by = {p["id"]: p for p in X.list_plugins(cfg)}
            assert by["buona"]["enabled"] and not by["buona"]["error"]
            assert not by["rotta"]["enabled"] and "illeggibile" in by["rotta"]["error"] and by["rotta"]["backend"] is None
            assert X.load_backends(None, cfg, X.Events(), log=lambda m: None) is not None     # l'avvio non si ferma
        finally:
            X._manifest = real
        print("ok  cartella plugin illeggibile: l'app parte, l'estensione e' disattivata con il motivo")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
        test_fonti(Path(t))
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
        test_auto_update(Path(t))

    # il backend dello store si carica e registra le sue route
    class GS:
        cfg, routes, log = None, {}, staticmethod(lambda m: None)

        def route(self, path, methods=("GET",)):
            return lambda fn: self.routes.setdefault(path, fn)
    import importlib.util
    spec = importlib.util.spec_from_file_location("gs_plugin_store_test", X.BUILTIN_PLUGINS / S.STORE_ID / "backend.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    gs = GS()
    mod.register(gs)
    assert set(gs.routes) == {"catalogo", "installa", "rimuovi", "fonti/aggiungi", "fonti/rimuovi"}
    print("ok  backend dello store")
    print("test_extstore: OK")


def test_fonti(t: Path):
    """Repository separati: export, store che rimanda ai repository, fonti aggiunte con un link, priorita' e errori."""
    # link -> index.json
    assert S.index_link("https://github.com/u/r") == "https://raw.githubusercontent.com/u/r/HEAD/index.json"
    assert S.index_link("https://github.com/u/r.git/") == "https://raw.githubusercontent.com/u/r/HEAD/index.json"
    assert S.index_link("https://github.com/u/r/tree/v1.2") == "https://raw.githubusercontent.com/u/r/v1.2/index.json"
    assert S.index_link(" https://esempio.it/store/index.json ") == "https://esempio.it/store/index.json"
    for bad in ("http://github.com/u/r", "https://github.com/u", "C:/store/index.json", "https://esempio.it/pagina", "ftp://x/i.json"):
        expect(lambda b=bad: S.index_link(b), "link non valido")
    assert S.sources(C.Config())[0] == {"link": S.OFFICIAL, "official": True}   # lo store ufficiale e' sempre il primo

    # export: un repository per estensione (index.json con base "./") e lo store con i riferimenti ai tag
    out = t / "out"
    T.cmd_export(str(out), "utente")
    store = json.loads((out / T.STORE / "index.json").read_text(encoding="utf-8"))
    ids = sorted(d.name for d in T.extension_dirs(T.EXT))
    assert [r["repo"] for r in store["repos"]] == [f"utente/{T.PREFIX}{i}" for i in ids]
    assert all(r["ref"].startswith("v") for r in store["repos"])
    for r in store["repos"]:  # lo store fissa il contenuto dell'indice di ogni repository, non solo il tag
        sub = out / r["repo"].split("/")[1] / "index.json"
        assert r["sha256"] == hashlib.sha256(sub.read_bytes()).hexdigest(), r
    one = out / f"{T.PREFIX}riepilogo-annuale"
    idx = json.loads((one / "index.json").read_text(encoding="utf-8"))["extensions"]
    assert len(idx) == 1 and idx[0]["id"] == "riepilogo-annuale" and idx[0]["base"] == "./"
    assert {"README.md", "LICENSE", "index.json"}.isdisjoint(idx[0]["files"])      # file del repository, non dell'estensione
    assert (one / "README.md").exists() and (one / ".gitattributes").exists()
    # index <cartella> rigenera lo stesso indice dal repository separato (la cartella si chiama pozzo-ext-<id>)
    before = (one / "index.json").read_text(encoding="utf-8")
    T.cmd_index(str(one))
    assert (one / "index.json").read_text(encoding="utf-8") == before

    # store locale che rimanda ai repository con "url" (al posto di repo+ref, che richiederebbe GitHub)
    local = {"version": 1, "repos": [{"url": str(out / f"{T.PREFIX}{i}" / "index.json")} for i in ("anniversari", "diario")]
             + [{"url": str(t / "manca" / "index.json")}, {"repo": "non valido!"}]}
    (t / "store.json").write_text(json.dumps(local), encoding="utf-8")
    cfg = cfg_in(t, t / "store.json")
    plugins = X.user_dir(cfg, "plugins")
    cat = S.catalog(cfg)
    assert sorted(x["id"] for x in cat["items"]) == ["anniversari", "diario"], cat["items"]
    src = cat["sources"][0]
    assert src["official"] and src["count"] == 2 and len(src["errors"]) == 2      # un repository irraggiungibile non toglie gli altri
    S.install(cfg, "anniversari")
    assert (plugins / "anniversari" / "frontend.js").is_file() and not (plugins / "anniversari" / "README.md").exists()
    # sha256 nella voce dello store: con quello giusto la voce e' "pinned" (puo' aggiornarsi da sola), con uno sbagliato
    # (tag spostato, url che ora serve altro) l'indice e' rifiutato; senza, si installa ma non e' pinned
    sub = out / f"{T.PREFIX}anniversari" / "index.json"
    good = hashlib.sha256(sub.read_bytes()).hexdigest()
    assert [e["pinned"] for e in S.fetch_source(str(t / "store.json"))[0]] == [False, False]
    (t / "pin.json").write_text(json.dumps({"repos": [{"url": str(sub), "sha256": good}]}), encoding="utf-8")
    assert [e["pinned"] for e in S.fetch_source(str(t / "pin.json"))[0]] == [True]
    (t / "pin.json").write_text(json.dumps({"repos": [{"url": str(sub), "sha256": "0" * 64}]}), encoding="utf-8")
    found, errors = S.fetch_source(str(t / "pin.json"))
    assert found == [] and "approvato" in errors[0], errors

    # seconda fonte (un altro store, letto da disco perche' l'utente non puo' aggiungere percorsi locali): stessa estensione
    # in entrambe -> vince lo store ufficiale; una nuova -> compare con la sua fonte
    other = {"version": 1, "repos": [{"url": str(out / f"{T.PREFIX}{i}" / "index.json")} for i in ("diario", "pulizia")]}
    (t / "altro.json").write_text(json.dumps(other), encoding="utf-8")
    cfg.app["extensions_sources"] = [str(t / "altro.json")]
    by = {x["id"]: x for x in S.catalog(cfg)["items"]}
    assert by["diario"]["official"] and not by["pulizia"]["official"] and by["pulizia"]["source"] == str(t / "altro.json")
    S.install(cfg, "pulizia", str(t / "altro.json"))
    assert (plugins / "pulizia" / "plugin.toml").is_file()
    expect(lambda: S.install(cfg, "pulizia", "https://github.com/sconosciuto/store"), "fonte sconosciuta")
    # sha256 manomesso nel repository di un'estensione: rifiutata anche se arriva da uno store
    (out / f"{T.PREFIX}diario" / "backend.py").write_text("import os\n", encoding="utf-8")
    expect(lambda: S.install(cfg, "diario"), "sha256")
    assert not (plugins / "diario").exists()

    # aggiungere e togliere fonti: solo link https validi e con estensioni; niente doppioni; l'ufficiale resta
    cfg.app["extensions_sources"] = []
    expect(lambda: S.add_source(cfg, "C:/store.json"), "link non valido")
    real_fetch = S.fetch_source
    S.fetch_source = lambda link: ([{"id": "x"}], []) if "buona" in link else ([], [])
    try:
        assert S.add_source(cfg, "https://github.com/utente/buona/") == ["https://github.com/utente/buona"]
        expect(lambda: S.add_source(cfg, "https://github.com/utente/buona"), "gia' presente")
        expect(lambda: S.add_source(cfg, "https://github.com/utente/vuota"), "non ci sono estensioni")
        saved = json.loads((t / "settings.json").read_text(encoding="utf-8"))
        assert saved["app"]["extensions_sources"] == ["https://github.com/utente/buona"]
        assert S.remove_source(cfg, "https://github.com/utente/buona") == []
        expect(lambda: S.remove_source(cfg, S.OFFICIAL), "non si rimuove")
    finally:
        S.fetch_source = real_fetch
    print("ok  repository separati: export, store con rimandi, fonti aggiunte da link, priorita' dello store ufficiale")


def test_auto_update(t: Path):
    """Aggiornamento automatico: la versione piu' nuova tra store e release dell'app, solo senza permessi nuovi."""
    out = t / "out"
    T.cmd_export(str(out), "utente")
    one = f"{T.PREFIX}riepilogo-annuale"
    store, rel = t / "store" / one, t / "rel" / one
    shutil.copytree(out / one, store)
    shutil.copytree(out / one, rel)

    def bump(folder: Path, version: str, perms: str | None = None):
        toml = folder / "plugin.toml"
        txt = re.sub(r'(?m)^version = ".*"$', f'version = "{version}"', toml.read_text(encoding="utf-8"))
        if perms:
            txt = re.sub(r"(?m)^permissions = \[.*\]$", f"permissions = {perms}", txt)
        toml.write_bytes(txt.encode("utf-8"))  # LF come nel repository: su Windows write_text scriverebbe CRLF
        T.cmd_index(str(folder))
    cfg = cfg_in(t, store / "index.json")
    plugins = X.user_dir(cfg, "plugins")
    S.install(cfg, "riepilogo-annuale")
    before = next(p for p in X.list_plugins(cfg) if p["id"] == "riepilogo-annuale")["version"]
    assert S.auto_update(cfg, log=lambda m: None) == [], "gia' all'ultima versione"

    bump(rel, "9.0")
    real = S.sources
    S.sources = lambda c: [{"link": str(store / "index.json"), "official": True},
                           {"link": str(rel / "index.json"), "official": True, "release": True}]
    try:
        by = {x["id"]: x for x in S.catalog(cfg)["items"]}
        assert by["riepilogo-annuale"]["state"] == "update" and by["riepilogo-annuale"]["version"] == "9.0", "vince la release piu' nuova"
        logs = []
        assert S.auto_update(cfg, log=logs.append) == ["riepilogo-annuale"], logs
        assert next(p for p in X.list_plugins(cfg) if p["id"] == "riepilogo-annuale")["version"] == "9.0" != before
        assert S.auto_update(cfg, log=logs.append) == [], "una volta sola"

        bump(rel, "9.1", '["libreria:lettura", "avvio"]')
        logs.clear()
        assert S.auto_update(cfg, log=logs.append) == [] and any("permessi" in m for m in logs), logs
        assert next(p for p in X.list_plugins(cfg) if p["id"] == "riepilogo-annuale")["version"] == "9.0"

        bump(rel, "9.2")
        cfg.app["extensions_auto_update"] = False
        assert S.auto_update(cfg) == []
        cfg.app["extensions_auto_update"] = True
        # una fonte di terzi con una versione piu' alta non aggiorna da sola un'estensione ufficiale
        S.sources = lambda c: [{"link": str(store / "index.json"), "official": True}, {"link": str(rel / "index.json"), "official": False}]
        assert S.auto_update(cfg) == [] and (plugins / "riepilogo-annuale").is_dir()
        # store ufficiale che rimanda a un repository senza sha256: l'autore puo' cambiarlo quando vuole -> niente da solo
        (t / "unpinned.json").write_text(json.dumps({"repos": [{"url": str(rel / "index.json")}]}), encoding="utf-8")
        S.sources = lambda c: [{"link": str(t / "unpinned.json"), "official": True}]
        logs.clear()
        assert S.auto_update(cfg, log=logs.append) == [], logs
        assert next(p for p in X.list_plugins(cfg) if p["id"] == "riepilogo-annuale")["version"] == "9.0"
    finally:
        S.sources = real
    # con lo store ufficiale vero c'e' anche l'indice della release di questa versione dell'app
    src = S.sources(C.Config())
    assert src[1]["release"] and src[1]["link"].endswith(f"/v{S.__version__}/extensions/index.json"), src
    print("ok  aggiornamento automatico: release piu' nuova dello store, niente permessi nuovi senza conferma")


def test_solo_https():
    """Indice e file delle estensioni (codice eseguito) solo in https, anche dopo un redirect."""
    import httpx
    expect(lambda: S._get("http://esempio.it/index.json"), "https")
    real = S.httpx.Client

    def handler(req):
        if req.url.scheme == "https":
            return httpx.Response(302, headers={"location": "http://esempio.it/index.json"})
        return httpx.Response(200, content=b"{}")
    S.httpx.Client = lambda **kw: real(transport=httpx.MockTransport(handler), **kw)
    try:
        expect(lambda: S._get("https://esempio.it/index.json"), "https")
    finally:
        S.httpx.Client = real
    print("ok  solo https per lo store delle estensioni")


if __name__ == "__main__":
    test_solo_https()
    main()
