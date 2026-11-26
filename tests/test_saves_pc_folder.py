"""Salvataggi dentro la cartella del gioco PC (<base> di Ludusavi): install_dir non e' nella libreria in memoria."""
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from pozzo import config  # noqa: E402
from pozzo.app.server import create_app  # noqa: E402
from pozzo.library import build  # noqa: E402

tmp = Path(tempfile.mkdtemp())
try:
    game = tmp / "Gioco"
    (game / "players").mkdir(parents=True)
    (game / "players" / "a.sav").write_bytes(b"uno")
    (game / "gioco.exe").write_bytes(b"x")
    cfg = config.Config(cache=tmp / "c", output=tmp / "out", roms=tmp / "roms")
    cfg.config_path = tmp / "config.toml"
    (tmp / "roms").mkdir()
    build.build(cfg)
    db = sqlite3.connect(tmp / "c" / "library.db")
    row = {"id": 9000, "key": "steam:1", "title": "Gioco PC", "platform": "windows", "store": "steam", "installed": 1,
           "install_dir": str(game), "files": "[]", "media": "{}", "genres": "[]", "grp": "pc", "is_primary": 1}
    db.execute(f"INSERT INTO games({','.join(row)}) VALUES({','.join('?' * len(row))})", list(row.values()))
    db.commit()
    db.close()
    (tmp / "c" / "ludusavi-manifest.json").write_text(json.dumps(
        {"games": {"Gioco PC": {"files": [["<base>/players/*.sav", []]], "dirs": ["Gioco"]}}, "steam": {"1": "Gioco PC"}, "gog": {}}))
    with TestClient(create_app(cfg), base_url="http://127.0.0.1:8765") as c:
        r = c.get("/api/game/9000/saves").json()
        assert [Path(x).name for x in r["paths"]] == ["a.sav"], r
        name = c.post("/api/game/9000/saves").json()["name"]
        (game / "players" / "a.sav").write_bytes(b"due")
        r = c.post("/api/game/9000/saves/restore", json={"name": name})
        assert r.status_code == 200 and r.json()["written"] == 1 and r.json()["removed"] == 0, r.text
        assert (game / "players" / "a.sav").read_bytes() == b"uno" and (game / "gioco.exe").exists()
    print("ok")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
