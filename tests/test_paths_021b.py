"""0.21.0 W3: copertine fuori dalla cache, Play ai PS1, extstore ufficiale, glob dei backup, ecc."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_libshare import env  # noqa: F401,E402
from pozzo.remote import phone as PH  # noqa: E402
from test_libshare import game  # noqa: E402


def _list(env_):
    app, hub, gate, token, cfg, code = env_
    return {g["id"]: g for g in gate.get("/api/lib-share/list", cookies={PH.COOKIE: token}).json()["games"]}


def test_libshare_cover_fuori_cache(env, tmp_path):
    app, hub, gate, token, cfg, code = env
    (Path(cfg.cache)).mkdir(parents=True, exist_ok=True)
    (Path(cfg.cache) / "ok.jpg").write_bytes(b"x")
    (tmp_path / "secret.jpg").write_bytes(b"s")
    lib = app.state.lib
    g = lib.by_id[1]
    for rel, expect in (("ok.jpg", True), ("../secret.jpg", False), (str(tmp_path / "secret.jpg"), False)):
        g["media"] = {"cover": rel}
        assert bool(_list(env)[1]["cover"]) is expect, rel


def test_libshare_play_psx_no(env, tmp_path, monkeypatch):
    app, hub, gate, token, cfg, code = env
    rom = tmp_path / "roms" / "g.cue"
    rom.write_bytes(b"x")
    g = game(9, "psx", [rom])
    app.state.lib.by_id[9] = g
    app.state.lib.games.append(g)
    cfg.app["libshare"]["games"].append("k9")
    from pozzo import webplay as W
    monkeypatch.setattr(W, "plan", lambda g_: {"kind": "ejs"})
    assert _list(env)[9]["play"] is False


def test_emusetup_backup_con_parentesi(tmp_path):
    from pozzo.remote import emusetup as E
    p = tmp_path / "Sonic [b1].cfg"
    p.write_text("a")
    b = tmp_path / ("Sonic [b1].cfg" + E.BACKUP_TAG + "1")
    b.write_text("b")
    assert E.latest_backup(p) == b


def test_extstore_ufficiale_giu_non_si_sostituisce(monkeypatch):
    from pozzo.app import extstore as S
    cfg = SimpleNamespace(app={})
    monkeypatch.setattr(S, "sources", lambda c: [{"link": "off", "official": True}, {"link": "terza", "official": False}])
    monkeypatch.setattr(S, "fetch_source", lambda link: ([], ["rete"]) if link == "off" else ([{"id": "x", "files": {}}], []))
    monkeypatch.setattr(S.X, "list_plugins", lambda c: [{"id": "x"}])
    try:
        S.install(cfg, "x")
    except ValueError as e:
        assert "ufficiale" in str(e) or "terzi" in str(e)
    else:
        raise AssertionError("doveva rifiutare")


def test_steamexport_file_fuori_cache(tmp_path):
    from pozzo.app.routes import steamexport as SE
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "ok.jpg").write_bytes(b"x")
    (tmp_path / "secret.jpg").write_bytes(b"s")
    assert SE.file_in_cache(cache, "ok.jpg") == cache / "ok.jpg"
    assert SE.file_in_cache(cache, "../secret.jpg") is None
    assert SE.file_in_cache(cache, str(tmp_path / "secret.jpg")) is None
