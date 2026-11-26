"""Rotte che cambiano i dati dell'utente: correzione del match e aggiunta di una cartella di giochi PC. Nessuna rete."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient  # noqa: E402

from pozzo import config  # noqa: E402
from pozzo.app.server import create_app  # noqa: E402
from pozzo.cache import Cache  # noqa: E402
from test_frontend import make_library  # noqa: E402


def _app(tmp, monkeypatch):
    rom = tmp / "g.gba"
    rom.write_bytes(b"x")
    cfg = config.Config(cache=tmp, output=tmp / "out")
    cfg.config_path = tmp / "config.toml"
    make_library(tmp, rom)
    # niente ricostruzione ne' scraping in sottofondo: qui si guarda cosa salva la rotta
    from pozzo.app.routes import system
    monkeypatch.setattr(system, "build", lambda cfg, log=print, progress=None: {})
    monkeypatch.setattr("pozzo.app.jobs.ScrapeJob.run", lambda self, *a, **k: None)
    return cfg, create_app(cfg)


def test_correzione_del_match_e_annullo(tmp, monkeypatch):
    cfg, app = _app(tmp, monkeypatch)
    c = TestClient(app)
    gid = app.state.lib.by_key["gba/AAA"]["id"]
    cache = Cache(tmp)
    for k in ("gba/AAA", "gba/BBB", "gba/CCC"):
        cache.put(k, "igdb", "title", "vecchio")
    cache.close()

    assert c.post(f"/api/game/{gid}/match", json={"title": "  "}).status_code == 400
    assert c.post(f"/api/game/{gid}/match", json={"i": 0}).status_code == 409, "risultato di una ricerca mai fatta"
    assert c.get(f"/api/game/{gid}/match").json()["override"] is None
    r = c.post(f"/api/game/{gid}/match", json={"title": "Pokémon Rubino"})
    assert r.status_code == 200 and r.json()["override"]["fields"]["title"] == "Pokémon Rubino"
    assert c.get(f"/api/game/{gid}/match").json()["override"]["title"] == "Pokémon Rubino"
    other = app.state.lib.by_key["gba/BBB"]["id"]  # vale su tutte le versioni dello stesso gioco
    assert c.get(f"/api/game/{other}/match").json()["override"]["title"] == "Pokémon Rubino"
    cache = Cache(tmp)
    assert not cache.resources("gba/AAA").get("igdb") and not cache.resources("gba/BBB").get("igdb"), "dati vecchi tolti"
    assert cache.resources("gba/CCC")["igdb"]["title"] == "vecchio", "gli altri giochi non si toccano"
    cache.close()

    assert c.delete(f"/api/game/{gid}/match").status_code == 200
    assert c.get(f"/api/game/{gid}/match").json()["override"] is None
    assert c.get(f"/api/game/{other}/match").json()["override"] is None


def test_cartella_di_giochi_pc(tmp, monkeypatch):
    cfg, app = _app(tmp, monkeypatch)
    c = TestClient(app)
    root = tmp / "Giochi"
    for rel, size in (("Alfa/setup.exe", 900), ("Alfa/alfa.exe", 500), ("Alfa/piccolo.exe", 10),
                      ("SoloInstaller/unins000.exe", 50), ("Vuota/leggimi.txt", 5)):
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x" * size)
    assert c.post("/api/folders/add", json={"platform": "windows", "path": str(tmp / "manca")}).status_code == 400
    assert c.post("/api/folders/add", json={"platform": "nonesiste", "path": str(root)}).status_code == 400
    assert c.post("/api/folders/add", json={"platform": "windows", "path": str(root)}).json() == {"added": 1}
    from pozzo.library.userdata import UserData
    ud = UserData(tmp / "userdata.db")
    got = [(g["title"], Path(g["exe"]).name) for g in ud.manual_games()]
    ud.close()
    assert got == [("Alfa", "alfa.exe")], got
    assert c.post("/api/folders/add", json={"platform": "windows", "path": str(root)}).json() == {"added": 0}, "niente doppioni"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
