import json
from types import SimpleNamespace

from pozzo import emuinstall as E


def _setup(tmp_path, monkeypatch, files):
    dest = tmp_path / "emus" / "rpcs3"
    dest.mkdir(parents=True)
    (dest / "rpcs3.exe").write_text("old")
    (dest / "config.yml").write_text("mine")
    cfg = SimpleNamespace(app={"emulators_dir": str(tmp_path / "emus"),
                               "emu_installed": {"rpcs3": {"version": "v1", "dir": str(dest)}}},
                          emulators={"rpcs3": str(dest / "rpcs3.exe")}, launch={})

    def stage(cfg, asset, name, progress=None):
        w = tmp_path / "emus" / ".tmp" / name
        (w / "files").mkdir(parents=True)
        for f in files:
            (w / "files" / f).write_text("new")
        return w / "files"

    monkeypatch.setattr(E, "_latest", lambda cfg, src: ("v2", {"name": "x.zip", "url": "u"}))
    monkeypatch.setattr(E, "_stage", stage)
    monkeypatch.setattr(E.PT, "_running", lambda d: False)
    monkeypatch.setattr(E.C, "save_settings", lambda cfg, **s: None)
    return cfg, dest


def test_failed_update_restores_original(tmp_path, monkeypatch):
    cfg, dest = _setup(tmp_path, monkeypatch, ["junk.txt"])
    real = E.shutil.copytree

    def boom(src, dst, **kw):  # la sovrascrittura si interrompe a meta'
        if kw.get("dirs_exist_ok"):
            real(src, dst, **kw)
            raise OSError("disco pieno")
        return real(src, dst, **kw)

    monkeypatch.setattr(E.shutil, "copytree", boom)
    try:
        E.install(cfg, "rpcs3", say=lambda *_: None)
        assert False, "doveva fallire"
    except OSError:
        pass
    assert (dest / "rpcs3.exe").read_text() == "old" and (dest / "config.yml").read_text() == "mine"
    assert not (dest / "junk.txt").exists()


def test_update_keeps_bak_and_records_version(tmp_path, monkeypatch):
    cfg, dest = _setup(tmp_path, monkeypatch, ["rpcs3.exe"])
    E.install(cfg, "rpcs3", say=lambda *_: None)
    assert (dest / "rpcs3.exe").read_text() == "new" and (dest / "config.yml").read_text() == "mine"
    assert (tmp_path / "emus" / "rpcs3.bak" / "rpcs3.exe").read_text() == "old"
    assert json.loads((tmp_path / "emus" / "versions.json").read_text())["installed"] == {"rpcs3": "v2"}
    cfg.app["emu_installed"]["rpcs3"]["version"] = "v2"
    assert E.check_updates(cfg)[0]["update"] is False
    E.rollback("rpcs3", cfg)
    assert (dest / "rpcs3.exe").read_text() == "old" and not (tmp_path / "emus" / "rpcs3.bak").exists()


def test_rollback_tiene_i_salvataggi_fatti_dopo_l_aggiornamento(tmp_path, monkeypatch):
    cfg, dest = _setup(tmp_path, monkeypatch, ["rpcs3.exe"])
    sav = dest / "dev_hdd0" / "home" / "save.dat"
    sav.parent.mkdir(parents=True)
    sav.write_text("prima")
    (dest / "Sys").mkdir()  # file del programma (Dolphin): tornano quelli della versione vecchia
    (dest / "Sys" / "gc.txt").write_text("v1")
    E.install(cfg, "rpcs3", say=lambda *_: None)
    sav.write_text("dopo")
    sav.with_name("nuovo.dat").write_text("n")
    (dest / "Sys" / "gc.txt").write_text("v2")
    E.rollback("rpcs3", cfg)
    assert (dest / "rpcs3.exe").read_text() == "old" and (dest / "Sys" / "gc.txt").read_text() == "v1"
    assert sav.read_text() == "dopo" and sav.with_name("nuovo.dat").exists()
    assert [p.name for p in dest.parent.iterdir() if p.is_dir() and p.name.startswith("rpcs3")] == ["rpcs3"]


def test_copia_a_meta_non_resta_come_versione_precedente(tmp_path, monkeypatch):
    cfg, dest = _setup(tmp_path, monkeypatch, ["rpcs3.exe"])
    real = E.shutil.copytree

    def boom(src, dst, **kw):
        real(src, dst, **kw)
        raise OSError("disco pieno")

    monkeypatch.setattr(E.shutil, "copytree", boom)
    try:
        E.install(cfg, "rpcs3", say=lambda *_: None)
        assert False, "doveva fallire"
    except OSError:
        pass
    assert (dest / "rpcs3.exe").read_text() == "old" and not E._bak(dest).exists()
