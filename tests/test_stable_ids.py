"""Il numero di un gioco non cambia ricostruendo la libreria, e quello di un gioco tolto non passa a un altro:
una pagina aperta prima della ricostruzione non deve aprire (o avviare) il gioco sbagliato. Nessuna rete."""

import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pozzo import config  # noqa: E402
from pozzo.library import build as B  # noqa: E402


async def _no_franchises(*a, **k):
    return None


def _ids(cfg) -> dict:
    with closing(sqlite3.connect(cfg.cache / "library.db")) as db:
        return {t: i for t, i in db.execute("SELECT title, id FROM games")}


def _cfg(t: Path):
    cfg = config.Config(roms=t / "roms", cache=t / "cache", output=t / "out")
    cfg.config_path = t / "config.toml"
    cfg.cache.mkdir()
    (cfg.roms / "Game Boy Advance").mkdir(parents=True)
    return cfg


def _rom(cfg, name: str) -> Path:
    f = cfg.roms / "Game Boy Advance" / f"{name} (USA).gba"
    f.write_bytes(name.encode() * 50)
    return f


def _build(cfg):
    orig, B._enrich_franchises = B._enrich_franchises, _no_franchises
    try:
        B.build(cfg, log=lambda m: None)
    finally:
        B._enrich_franchises = orig


def test_ids_survive_rebuild():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cfg(Path(tmp))
        roms = {n: _rom(cfg, n) for n in ("Mario", "Tetris", "Zelda")}
        _build(cfg)
        first = _ids(cfg)
        assert len(first) == 3, first

        roms["Mario"].unlink()  # tolto il primo, aggiunto uno che viene prima in ordine alfabetico
        _rom(cfg, "Advance Wars")
        _build(cfg)
        second = _ids(cfg)
        assert second["Tetris"] == first["Tetris"] and second["Zelda"] == first["Zelda"], (first, second)
        assert second["Advance Wars"] not in first.values(), (first, second)

        # il numero piu' alto e' di un gioco tolto: nemmeno due ricostruzioni dopo passa a un altro
        (cfg.roms / "Game Boy Advance" / "Advance Wars (USA).gba").unlink()
        _build(cfg)
        for f in (cfg.roms / "Game Boy Advance").iterdir():  # libreria svuotata (disco scollegato): vale lo stesso
            f.unlink()
        _build(cfg)
        assert not _ids(cfg)
        _rom(cfg, "Boktai")
        _build(cfg)
        assert _ids(cfg)["Boktai"] > second["Advance Wars"], (second, _ids(cfg))


def test_old_or_broken_library_does_not_stop_the_build():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cfg(Path(tmp))
        _rom(cfg, "Zelda")
        (cfg.cache / "library.db").write_bytes(b"non e' un database")
        _build(cfg)
        assert list(_ids(cfg)) == ["Zelda"]

        # libreria di una versione precedente: senza AUTOINCREMENT, i numeri si conservano lo stesso
        db = sqlite3.connect(cfg.cache / "library.db")
        row = db.execute("SELECT key, title FROM games").fetchone()
        db.execute("DROP TABLE games")
        db.execute("CREATE TABLE games(id INTEGER PRIMARY KEY, key TEXT UNIQUE, title TEXT)")
        db.execute("INSERT INTO games VALUES(77, ?, ?)", row)
        db.commit()
        db.close()
        _build(cfg)
        assert _ids(cfg) == {"Zelda": 77}


def test_manual_games_keep_their_id():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cfg(Path(tmp))
        _rom(cfg, "Zelda")
        _build(cfg)

        def entry(n):
            return {"key": f"windows/manual:{n}", "title": f"Gioco {n}", "sort": f"gioco {n}", "year": None, "release_date": None,
                    "developer": None, "publisher": None, "genres": [], "ratings": {}, "description": None, "files": [], "media": {},
                    "store": "manual", "grp": f"windows/m{n}", "primary": 1, "installed": 1, "launch": {}, "install_uri": None,
                    "page": None, "store_playtime": 0, "install_dir": None, "size": None, "content": "game", "owners": []}
        orig = B._store_entries
        try:
            B._store_entries = lambda *a: [entry(1), entry(2)]
            assert B.update_manual(cfg)
            first = _ids(cfg)
            B._store_entries = lambda *a: [entry(2), entry(3)]  # il primo tolto, uno nuovo
            assert B.update_manual(cfg)
            second = _ids(cfg)
        finally:
            B._store_entries = orig
        assert second["Gioco 2"] == first["Gioco 2"] and second["Zelda"] == first["Zelda"], (first, second)
        assert second["Gioco 3"] not in first.values(), (first, second)


if __name__ == "__main__":
    test_ids_survive_rebuild()
    test_old_or_broken_library_does_not_stop_the_build()
    test_manual_games_keep_their_id()
    print("ok  numeri dei giochi stabili")
