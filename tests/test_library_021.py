"""Fix 0.21.0 di library/build.py, library/incremental.py e app/library_service.py.
Esegui: python tests/test_library_021.py"""
import sqlite3
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pozzo import config  # noqa: E402
from pozzo.cache import Cache  # noqa: E402
from pozzo.library import build as B, incremental  # noqa: E402
from pozzo.app.library_service import Library  # noqa: E402


def _cfg(t: Path):
    cfg = config.Config(roms=t / "roms", cache=t / "cache", output=t / "out")
    cfg.config_path = t / "config.toml"
    cfg.cache.mkdir()
    (cfg.roms / "Game Boy Advance").mkdir(parents=True)
    (cfg.roms / "Game Boy Advance" / "Zelda (USA).gba").write_bytes(b"z" * 100)

    async def no_franchises(*a, **k):
        return None
    B._enrich_franchises = no_franchises
    return cfg


def test_schema_ha_indice_store():
    assert "games_store ON games(store)" in B.SCHEMA


def test_preload_kv_uguale_a_kv_get():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
        cache = Cache(Path(t))
        cache.kv_set("storemeta:a", {"x": 1})
        cache.kv_set("netmeta:u", {"data": {"y": 2}})
        cache.kv_set("hltb:gba:zelda", {"main": 3})
        cache.kv_set("downloaded", {"z": 1})
        cache.db.execute("UPDATE kv SET ts=? WHERE k='netmeta:u'", (time.time() - 1000,))
        cache.commit()
        real = cache.kv_get
        calls = []
        cache.kv_get = lambda k, max_age=None: (calls.append(k), real(k, max_age))[1]
        pre = B._KvPreload(cache)
        for k, age in [("storemeta:a", None), ("storemeta:b", None), ("netmeta:u", None), ("netmeta:u", 10),
                       ("hltb:gba:zelda", None), ("hltb:gba:no", None)]:
            assert pre.kv_get(k, age) == real(k, age), (k, age)
        assert not calls, f"i prefissi caricati non devono rileggere il db: {calls}"
        assert pre.kv_get("downloaded") == {"z": 1} and calls == ["downloaded"]  # il resto passa alla cache
        assert pre.all_resources([]) == {}  # il resto dell'API della cache passa
        cache.close()


def test_load_fallito_sblocca_full():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
        cfg = _cfg(Path(t))
        (cfg.cache / "library.db").write_bytes(b"non e' un database sqlite" * 100)
        lib = Library(cfg)
        try:
            lib.load(online=True)
        except sqlite3.DatabaseError:
            pass
        assert lib.full.is_set(), "se load fallisce /api/library non deve aspettare per sempre"


def test_add_games_durante_build_finisce_nel_db_nuovo():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
        cfg = _cfg(Path(t))
        B.build(cfg, log=lambda m: None)
        entered, release = threading.Event(), threading.Event()
        real = B._attach_hltb

        def slow(db, cache):
            entered.set()
            release.wait(10)
            return real(db, cache)
        B._attach_hltb = slow
        new = cfg.roms / "Game Boy Advance" / "Metroid Fusion (USA).gba"
        try:
            tb = threading.Thread(target=B.build, args=(cfg, lambda m: None))
            tb.start()
            assert entered.wait(10)
            new.write_bytes(b"m" * 100)  # arriva dopo la scansione di build
            out = {}
            ta = threading.Thread(target=lambda: out.update(k=incremental.add_games(cfg, "gba", [new])))
            ta.start()
            time.sleep(0.5)
            release.set()
            tb.join(20)
            ta.join(20)
        finally:
            B._attach_hltb = real
        assert out.get("k"), out
        db = sqlite3.connect(cfg.cache / "library.db")
        n = db.execute("SELECT COUNT(*) FROM games WHERE key=?", (out["k"][0],)).fetchone()[0]
        db.close()
        assert n == 1, "il gioco aggiunto durante la ricostruzione e' andato perso"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
