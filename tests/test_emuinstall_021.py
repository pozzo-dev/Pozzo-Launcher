"""emuinstall: disinstallare Eglantine non cancella i dati di Eden."""

from __future__ import annotations

from pathlib import Path

from pozzo import config as C
from pozzo import emuinstall as EI
from pozzo import ports as PT


def _setup(tmp: Path, monkeypatch, emu: str):
    (tmp / "config.toml").write_text('[paths]\nroms = "roms"\ncache = "cache"\n', encoding="utf-8")
    cfg = C.load(tmp / "config.toml")
    d = tmp / "emus" / emu
    d.mkdir(parents=True)
    (d / f"{emu}.exe").write_text("x")
    C.save_settings(cfg, emulators={emu: str(d / f"{emu}.exe"), "eden": str(tmp / "eden.exe")},  # Eden: percorso scelto dall'utente
                    app={"emu_installed": {emu: {"version": "", "dir": str(d)}}})
    eden = tmp / "ad" / "eden"
    eden.mkdir(parents=True)
    (eden / "keys").write_text("k")
    monkeypatch.setattr(PT, "_running", lambda d: False)
    monkeypatch.setattr(EI, "_appdata", lambda e: tmp / "ad" / EI.APPDATA_DIRS[e] if EI.APPDATA_DIRS.get(e) else None)
    return cfg, eden


def test_eglantine_non_tocca_eden(tmp_path, monkeypatch):
    cfg, eden = _setup(tmp_path, monkeypatch, "eglantine")
    EI.uninstall(cfg, "eglantine", keep_data=False)
    assert (eden / "keys").exists()


def test_cartella_condivisa_con_emulatore_configurato(tmp_path, monkeypatch):
    monkeypatch.setitem(EI.APPDATA_DIRS, "forkx", "eden")  # un fork che usa la stessa cartella dati
    cfg, eden = _setup(tmp_path, monkeypatch, "forkx")
    EI.uninstall(cfg, "forkx", keep_data=False)
    assert (eden / "keys").exists()  # Eden e' solo in cfg.emulators, non installato da Pozzo


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
