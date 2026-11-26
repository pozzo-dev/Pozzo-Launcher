"""Correzioni 0.21.0 del download manager: ingest di cartelle, coda del browser, annullo durante lo spostamento,
.torrent troppo grande, niente condivisione, attesa dello stesso info-hash, `part` dei completati. Nessuna rete."""
import asyncio
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pozzo import net, platforms as P, storelinks as SL  # noqa: E402
from pozzo.downloads import finish, ingest as IN, manager as M, task as T  # noqa: E402


def _mgr(tmp, **dl):
    cfg = SimpleNamespace(cache=tmp / "cache", app={"downloads": {"dir": str(tmp / "out"), **dl}})
    return M.Manager(cfg, client_factory=net.make_client, save=lambda new: None)


# 1: una cartella condivisa con file estranei non si sposta intera
def test_folder_root_solo_cartelle_estratte(tmp):
    dl = tmp / "dl"
    dl.mkdir()
    exe = dl / "GAME.EXE"
    exe.write_bytes(b"mz")
    (dl / "altro.txt").write_text("mio")
    dos, dest = P.get("dos"), tmp / "roms"
    assert IN._folder_root(dos, exe, dest, None) is None  # file sciolto: mai la cartella
    assert IN._folder_root(dos, exe, dest, None, [tmp / "altrove"]) is None
    assert IN._folder_root(dos, exe, dest, None, [dl]) == dl  # cartella estratta da questo download


def test_place_file_sciolto_lascia_gli_estranei(tmp):
    dl, dest = tmp / "dl", tmp / "roms"
    dl.mkdir()
    dest.mkdir()
    (dl / "GAME.EXE").write_bytes(b"mz")
    (dl / "altro.txt").write_text("mio")
    IN._place(P.get("dos"), [dl / "GAME.EXE"], dest, None)
    assert (dl / "altro.txt").is_file() and not (dl / "GAME.EXE").exists()


# 5: riferimenti fuori dalla cartella del cue
def test_refs_fuori_cartella_ignorati(tmp):
    d = tmp / "g"
    d.mkdir()
    (d / "a.bin").write_bytes(b"1")
    out = tmp / "fuori.bin"
    out.write_bytes(b"2")
    cue = d / "a.cue"
    cue.write_text(f'FILE "a.bin" BINARY\nFILE "../fuori.bin" BINARY\nFILE "{out}" BINARY\n', "utf-8")
    assert IN._refs(cue) == [d / "a.bin"]


# 6: i .sub di altri nomi (sottotitoli) non seguono il gioco
def test_sidecars_solo_stesso_nome(tmp):
    d = tmp / "g"
    d.mkdir()
    cue = d / "FF9.cue"
    for n in ("FF9.cue", "FF9.sbi", "movie.sub"):
        (d / n).write_bytes(b"x")
    assert IN._sidecars(P.get("psx"), cue, [cue]) == [d / "FF9.sbi"]
    (d / "FF9.sbi").unlink()
    assert IN._sidecars(P.get("psx"), cue, [cue]) == []


# 2: la coda del browser ha un tetto
def test_with_browser_coda_con_tetto(monkeypatch):
    monkeypatch.setattr(SL, "BROWSER_TIMEOUT", 0.05)
    release = threading.Event()
    monkeypatch.setitem(SL.RESOLVER, "fn", lambda u: release.wait(5) and "")
    started = threading.Thread(target=lambda: SL.with_browser("https://x.test/1", timeout=3), daemon=True)
    started.start()
    while not SL._LOCK.locked():
        pass
    assert SL.with_browser("https://x.test/2", timeout=1) == ""  # non resta in coda per sempre
    release.set()
    started.join(5)


# 3: annullato durante lo spostamento finale: non risorge
def test_move_final_dopo_annullo_non_salva(tmp):
    m = _mgr(tmp, incomplete_dir=str(tmp / "inc"))
    t = m.add("https://x.example/a.zip")
    inc = Path(t.save_path)
    inc.mkdir(parents=True, exist_ok=True)
    (inc / "a.zip").write_bytes(b"1")
    m.tasks.pop(t.id)  # cancel() lo ha tolto mentre si spostava
    m.store.delete(t.id)
    m._move_final(t)
    assert t.id not in {x.id for x in m.store.load()}


# 4: .torrent da link troppo grande
def test_torrent_da_link_troppo_grande(tmp):
    pytest.importorskip("libtorrent")
    from pozzo.downloads.engines import torrent as TOR

    class R:
        def raise_for_status(self): pass
        async def aiter_bytes(self):
            for _ in range(3):
                yield b"x" * (TOR.MAX_TORRENT // 2)

        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    client = SimpleNamespace(stream=lambda *a, **k: R())
    t = T.DownloadTask(source="https://x.example/a.torrent", save_path=str(tmp), type="torrent")
    eng = SimpleNamespace(resume_file=lambda tid: tmp / "nessuno", dead_trackers={})
    with pytest.raises(ValueError, match="troppo grande"):
        asyncio.run(TOR._params(t, eng, client))


# 7: niente condivisione: il motore esce a fine scarico, il manager completa e lancia il post-download
def test_torrent_finito_va_in_post_senza_seeding(tmp, monkeypatch):
    got = []

    async def fake_tor(task, eng, client, gate=None, space=None):
        task.name, task.size, task.done = "Gioco.zip", 100, 100

    monkeypatch.setattr(M.TOR, "run", fake_tor)
    monkeypatch.setattr(M.TOR, "available", lambda: True)
    m = _mgr(tmp, seed_ratio=2.0)  # vecchia impostazione: ignorata
    m._torrent = SimpleNamespace(configure=lambda s: None, handles={}, close=lambda: None, ip_error="")
    m.on_completed = got.append
    m.start()
    t = m.add("magnet:?xt=urn:btih:" + "d" * 40)
    import time
    end = time.time() + 10
    while time.time() < end and not (t.options.get("post_done") and got):
        time.sleep(0.05)
    assert t.status == T.COMPLETED and "seeding" not in t.options and len(got) == 1
    assert "seed_ratio" not in M.DEFAULTS
    m.stop()


# 8: stesso info-hash gia' attivo: l'attesa non occupa un posto, poi lo richiede
def test_stesso_info_hash_attesa_senza_posto(tmp, monkeypatch):
    pytest.importorskip("libtorrent")
    from pozzo.downloads.engines import torrent as TOR
    ih = SimpleNamespace(get_best=lambda: "ab" * 20, has_v1=lambda: True, has_v2=lambda: False)

    async def params(task, eng, client):
        return SimpleNamespace(flags=0, ti=None, info_hashes=ih, save_path="")

    monkeypatch.setattr(TOR, "_params", params)
    monkeypatch.setattr(TOR, "POLL", 0.01)
    ses = SimpleNamespace(add_torrent=lambda p: (_ for _ in ()).throw(RuntimeError("stop")))
    eng = SimpleNamespace(resume_file=lambda tid: tmp / "nessuno", session=lambda: ses, _ih={"ab" * 20: "altro"})
    t = T.DownloadTask(source="magnet:?xt=urn:btih:" + "a" * 40, save_path=str(tmp), type="torrent")
    seen = []

    async def gate():
        seen.append("gate")

    async def go():
        job = asyncio.ensure_future(TOR.run(t, eng, None, gate=gate))
        await asyncio.sleep(0.1)
        seen.append(t.options.get("metadata"))  # False = posto non contato
        eng._ih.clear()
        with pytest.raises(ValueError, match="non aggiunto"):
            await job

    asyncio.run(go())
    assert seen == [False, "gate"]


# 9: un completato salvato con `part` non lo conserva dopo il caricamento
def test_load_toglie_part_dai_completati(tmp):
    m = _mgr(tmp)
    t = m.add("https://x.example/a.zip")
    t.status = T.COMPLETED
    t.options["part"] = str(tmp / "out" / "a.zip.part")
    m.store.save([t])
    m2 = _mgr(tmp)
    m2.start()
    t2 = m2.tasks[t.id]
    assert "part" not in t2.options
    m2.stop()


# 12: eboot.bin senza marcatore PS5 (Vita, PS4, PSP) non e' PS5
def test_guess_ps5_solo_con_param_json(tmp):
    ctx = SimpleNamespace(lib=SimpleNamespace(lock=threading.RLock(), games=[]))
    t = SimpleNamespace(name="")
    vita = tmp / "PCSE00000"
    (vita / "sce_sys").mkdir(parents=True)
    (vita / "eboot.bin").write_bytes(b"x")
    assert finish._guess(ctx, t, [vita / "eboot.bin"], [vita])[0] is None
    (vita / "sce_sys" / "param.json").write_text("{}")
    assert finish._guess(ctx, t, [vita / "eboot.bin"], [vita])[0].id == "ps5"


# 16: uno .zip che contiene solo un altro archivio non e' la ROM
def test_zip_che_avvolge_un_archivio(tmp):
    import zipfile
    a, b = tmp / "Metal Slug.zip", tmp / "mslug.zip"
    with zipfile.ZipFile(a, "w") as z:
        z.writestr("mslug.zip", b"x")
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("rom.bin", b"x")
    assert finish._wraps_archive(a) and not finish._wraps_archive(b)


# 15: collegamenti relativi innocui si saltano, assoluti o con .. no
def test_link_ok():
    from pozzo.downloads import extract as E
    assert E._link_ok("A") and E._link_ok("Versions/A/lib.so")
    assert not any(E._link_ok(x) for x in ("/etc/passwd", "../x", "a/../../b", "C:/x", "", None))


# 18: un risultato in cache che oggi punta a una rete locale si scarta
def test_resolve_cache_non_pubblica_scartata(monkeypatch):
    import httpx
    store = {}
    cache = SimpleNamespace(kv_get=lambda k, ttl=None: store.get(k), kv_set=lambda k, v: store.__setitem__(k, v))
    url = "https://ouo.io/abc"
    monkeypatch.setattr(SL, "is_shortener", lambda u: u == url)
    store[SL.RESOLVED_PREFIX + url] = "http://127.0.0.1/file.zip"
    monkeypatch.setitem(SL.RESOLVER, "fn", None)
    monkeypatch.setattr(SL.httpx, "Client", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("no")))
    assert SL.resolve(cache, url) == url
    assert store[SL.RESOLVED_PREFIX + url] == ""


# 11: tipi sbagliati nel corpo dell'aggiunta -> 400, non 500
def test_aggiunta_con_tipi_sbagliati_da_400(tmp):
    from fastapi.testclient import TestClient
    from pozzo import config
    from pozzo.app.server import create_app
    (tmp / "roms").mkdir()
    (tmp / "config.toml").write_text('[paths]\nroms = "roms"\ncache = "cache"\n[scrape]\nsources = []\n', encoding="utf-8")
    cfg = config.load(tmp / "config.toml")
    cfg.app["downloads"] = {"dir": str(tmp / "out")}
    with TestClient(create_app(cfg), raise_server_exceptions=False) as c:
        for body in ({"links": -1}, {"links": ["https://x.example/a.zip"], "save_path": [1]},
                     {"links": ["https://x.example/a.zip"], "mirrors": 5}):
            assert c.post("/api/downloads", json=body).status_code == 400, body
