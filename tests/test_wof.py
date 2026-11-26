"""Compressione WOF: stima dal database CompactGUI, comando, DirectStorage, avanzamento. Esegui: pytest -q tests/test_wof.py"""
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pozzo.library import wof as W

DB = [
    {"GameName": "Counter-Strike", "FolderName": "Half-Life", "CompressionResults": [
        {"CompType": 0, "BeforeBytes": 1000, "AfterBytes": 700},
        {"CompType": 1, "BeforeBytes": 1000, "AfterBytes": 650},
        {"CompType": 3, "BeforeBytes": 1000, "AfterBytes": 400}]},
    {"GameName": "Vuoto", "CompressionResults": []},
]

def test_db_matching():
    idx = W.build_index(DB)
    assert "vuoto" not in idx
    for title in ("Counter-Strike", "counter strike", "Half-Life"):
        e = W.estimate(title, 10_000, idx)
        assert e["name"] == "Counter-Strike" and e["best"] == "lzx"
        assert e["savings"] == {"xpress4k": 3000, "xpress8k": 3500, "lzx": 6000}
    assert W.estimate("Gioco Sconosciuto Mai Visto", 10_000, idx) is None


def test_build_cmd():
    assert W.build_cmd("lzx", files=["a b.iso"]) == ["compact", "/c", "/i", "/exe:lzx", "a b.iso"]
    assert W.build_cmd(files=["a"]) == ["compact", "/c", "/i", "/exe:xpress8k", "a"]
    assert W.build_cmd(uncompress=True, files=["a.iso"]) == ["compact", "/u", "/i", "/exe", "a.iso"]
    with pytest.raises(ValueError):
        W.build_cmd("zip")


def test_dstorage(tmp_path):
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "a.dll").write_bytes(b"x")
    assert not W.has_dstorage(tmp_path)
    (tmp_path / "bin" / "DStorage.DLL").write_bytes(b"x")
    assert W.has_dstorage(tmp_path) and len(W.tree_files(tmp_path)) == 2


def test_rom_files(tmp_path):
    (tmp_path / "d").mkdir()
    for n in ("a.bin", "b.iso", "d/x.dat"):
        (tmp_path / n).write_bytes(b"x")
    (tmp_path / "a.cue").write_text('FILE "a.bin" BINARY\n')
    (tmp_path / "g.m3u").write_text("# dischi\na.cue\nb.iso\nmanca.iso\ng.m3u\n")  # anche se cita se stessa
    got = W.rom_files([str(tmp_path / n) for n in ("g.m3u", "a.cue", "d", "manca.iso")])
    assert sorted(os.path.basename(f) for f in got) == ["a.bin", "a.cue", "b.iso", "g.m3u", "x.dat"]


def test_batches_and_sample(tmp_path):
    files = []
    for i in range(45):
        (tmp_path / f"{i}").write_bytes(b"" if i == 3 else b"ciao" * 100)
        files.append(str(tmp_path / f"{i}"))
    assert [len(g) for g in W.batches(files)] == [20, 20, 5]
    assert [len(g) for g in W.batches(files[10:13], max_bytes=500)] == [1, 1, 1]
    assert W.sample_ratio(files) < 0.2
    (tmp_path / "r").write_bytes(os.urandom(1 << 20))
    assert W.sample_ratio([str(tmp_path / "r")]) > 0.95 and W.sample_ratio([]) == 1.0


@pytest.mark.skipif(sys.platform == "darwin", reason="su macOS non si usa compact")
def test_damage_detection(tmp_path, monkeypatch):
    f = tmp_path / "g.iso"
    f.write_bytes(os.urandom(3 << 20))
    a = W.fingerprint(f)
    assert a == W.fingerprint(f) and not W.damaged(a, a) and not W.damaged(None, a) and not W.damaged(a, None)
    assert W.damaged(a, (*a[:2], a[2] + 1)) and not W.damaged(a, (a[0], a[1] + 1, a[2] + 1))  # riscritto dal gioco: ok
    cmds = []

    def broken(self, cmd):  # compact che rovina il file: il lavoro si ferma, decomprime e lo dice
        cmds.append(cmd)
        st = os.stat(f)
        f.write_bytes(b"x" * st.st_size)
        os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns))
        return 0
    monkeypatch.setattr(W.Job, "_compact", broken)
    j = _wait(W.Job([str(f)]))
    assert j.status == "error" and "g.iso" in j.error and cmds[1][1] == "/u"


def _wait(j):
    for _ in range(300):
        if j.status != "running":
            return j
        time.sleep(0.1)
    raise AssertionError("lavoro mai finito")


@pytest.mark.skipif(sys.platform != "win32", reason="compact.exe c'e' solo su Windows")
def test_job_on_files(tmp_path):
    if W.filesystem(tmp_path) != "NTFS":
        pytest.skip("serve NTFS")
    f = tmp_path / "Gioco [x] & (Italy).iso"
    f.write_bytes(b"ciao mondo " * 200_000)
    st, data = f.stat(), f.read_bytes()
    j = _wait(W.Job([str(f)], "lzx"))
    assert j.status == "done" and j.done == j.total == 1 and j.saved > st.st_size * 0.8, j.state()
    assert f.read_bytes() == data and (f.stat().st_size, f.stat().st_mtime_ns) == (st.st_size, st.st_mtime_ns)
    j = _wait(W.Job([str(f)], uncompress=True))
    assert j.status == "done" and j.saved < 0 and W.sizes([str(f)])[1] >= st.st_size


@pytest.mark.skipif(sys.platform != "win32", reason="le ROM si comprimono solo su Windows")
def test_routes(tmp_path):
    """Il gioco installato si trova (install_dir non e' nella libreria in memoria) e le ROM si comprimono."""
    import sqlite3

    from fastapi.testclient import TestClient

    from pozzo import config
    from pozzo.app.server import create_app
    from pozzo.library import build
    roms, game = tmp_path / "roms" / "nds", tmp_path / "game"
    roms.mkdir(parents=True)
    game.mkdir()
    (game / "a.pak").write_bytes(b"dati " * 100_000)
    (roms / "Uno (Italy).nds").write_bytes(b"rom " * 100_000)
    cfg = config.Config(cache=tmp_path / "c", output=tmp_path / "out", roms=tmp_path / "roms")
    cfg.config_path = tmp_path / "config.toml"
    build.build(cfg)
    db = sqlite3.connect(tmp_path / "c" / "library.db")
    cols = [r[1] for r in db.execute("PRAGMA table_info(games)")]
    rom = dict(zip(cols, db.execute("SELECT * FROM games WHERE platform='nds'").fetchone()))
    pc = {**rom, "id": 9000, "key": "steam:1", "title": "Gioco PC", "platform": "windows", "store": "steam", "installed": 1,
          "install_dir": str(game), "files": "[]", "grp": "pc"}
    db.execute(f"INSERT INTO games({','.join(cols)}) VALUES({','.join('?' * len(cols))})", list(pc.values()))
    db.commit()
    db.close()
    W.load_index, old = (lambda c: {}), W.load_index  # niente rete
    try:
        with TestClient(create_app(cfg), base_url="http://127.0.0.1:8765") as c:
            for url in ("/api/wof/game/9000", f"/api/wof/game/{rom['id']}", "/api/wof/platform/nds"):
                r = c.get(url)
                assert r.status_code == 200 and r.json()["count"] == 1 and r.json()["sampled"] > 0, (url, r.text)
                assert r.json()["gain"] and not r.json()["undo"] and not r.json()["blocked"]
                assert c.get(url + "/check").json() == {"ok": True, "reason": ""}
            (roms / "Uno (Italy).nds").write_bytes(os.urandom(400_000))  # non si comprime: voce bloccata e avvio rifiutato
            build.build(cfg)  # libreria nuova: la misura si rifa'
            c2 = TestClient(create_app(cfg), base_url="http://127.0.0.1:8765")
            r = c2.get("/api/wof/platform/nds/check").json()
            assert not r["ok"] and r["reason"]
            assert c2.post("/api/wof/platform/nds", json={}).status_code == 400
            assert not c2.get("/api/wof/platform/snes/check").json()["ok"]
            assert c.get("/api/wof/platform/snes").status_code == 400
            assert c.get("/api/wof/altro/1").status_code == 404
            (roms / "Uno (Italy).nds").rename(roms / "Uno (Italy).zip")  # sparita: nessun file da comprimere
            assert c.post("/api/wof/platform/nds", json={}).status_code == 400
    finally:
        W.load_index = old
