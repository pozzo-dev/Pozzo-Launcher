"""emuinstall 0.21b: DuckStation portatile, i dati accanto all'exe sopravvivono a disinstallazione (keep data)."""

from __future__ import annotations

from pozzo import config as C
from pozzo import emuinstall as EI
from pozzo import ports as PT


def test_duckstation_tiene_i_dati_portatili(tmp_path, monkeypatch):
    (tmp_path / "config.toml").write_text('[paths]\nroms = "roms"\ncache = "cache"\n', encoding="utf-8")
    cfg = C.load(tmp_path / "config.toml")
    d = tmp_path / "emus" / "duckstation"
    d.mkdir(parents=True)
    (d / "duckstation-qt-x64-ReleaseLTCG.exe").write_text("x")
    (d / "Qt6Core.dll").write_text("x")
    user = ["settings.ini", "gamesettings", "inputprofiles", "cheats", "textures", "covers", "screenshots", "memcards", "savestates"]
    for n in user:
        (d / n).mkdir() if "." not in n else (d / n).write_text("x")
    C.save_settings(cfg, emulators={"duckstation": str(d / "duckstation-qt-x64-ReleaseLTCG.exe")},
                    app={"emu_installed": {"duckstation": {"version": "", "dir": str(d)}}})
    monkeypatch.setattr(PT, "_running", lambda x: False)
    monkeypatch.setattr(EI, "_appdata", lambda e: None)
    EI.uninstall(cfg, "duckstation", keep_data=True)
    assert sorted(p.name for p in d.iterdir()) == sorted(user)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
