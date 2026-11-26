"""launcher 0.21c: se qualcosa dopo la fine del gioco esplode, la partita si registra lo stesso."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from pozzo import config as C
from pozzo.library import launcher as L


class FakeUser:
    def __init__(self):
        self.plays = []

    def record_play(self, key, secs):
        self.plays.append((key, secs))

    def mark_started(self, key):
        pass


@pytest.mark.parametrize("rotto", ["_scripts", "_auto_end"])
def test_errore_dopo_la_fine_registra_una_volta(tmp_path, monkeypatch, rotto):
    cfg = C.Config(cache=tmp_path / "cache")
    u = FakeUser()
    ln = L.Launcher(cfg, u)
    rom = tmp_path / "g.bin"
    rom.write_text("x")
    monkeypatch.setattr(L, "resolve_target", lambda p, s: s)
    monkeypatch.setattr(L, "_needs_extract", lambda *a: False)
    monkeypatch.setattr(L.Launcher, "_apply_preset", lambda *a: None)
    ln.prelaunch = lambda st: []
    orig = getattr(L.Launcher, rotto)
    volte = []

    def boom(self, *a, **k):
        if (rotto == "_scripts" and a[1:] != ("after",)) or volte:  # _auto_end: salta solo la prima chiamata (il finally la ripete)
            return orig(self, *a, **k)
        volte.append(1)
        raise RuntimeError("after rotto")

    monkeypatch.setattr(L.Launcher, rotto, boom)
    pl = {"emulator": "emu", "core": "", "exe": sys.executable, "args": ["-c", "pass"]}
    ln._run_emu("k", SimpleNamespace(id="ps1"), rom, pl, rom, {"dir": None})
    assert len(u.plays) == 1, u.plays


def test_plan_che_esplode_dopo_crash_registra(tmp_path, monkeypatch):
    cfg = C.Config(cache=tmp_path / "cache")
    cfg.app = {"crash_fallback": "apply"}
    u = FakeUser()
    ln = L.Launcher(cfg, u)
    rom = tmp_path / "g.bin"
    rom.write_text("x")
    monkeypatch.setattr(L, "resolve_target", lambda p, s: s)
    monkeypatch.setattr(L, "_needs_extract", lambda *a: False)
    monkeypatch.setattr(L.Launcher, "_apply_preset", lambda *a: None)
    ln.prelaunch = lambda st: []

    def no_plan(*a, **k):
        raise L.LaunchError("exe del profilo mancante")

    monkeypatch.setattr(L, "plan", no_plan)
    L._crash_update(cfg, "k", lambda e: e["runs"].append({"time": 1, "code": 3, "duration": 1, "log": ""}))
    pl = {"emulator": "emu", "core": "", "exe": sys.executable, "args": ["-c", "import sys; sys.exit(3)"]}
    ln._run_emu("k", SimpleNamespace(id="ps1"), rom, pl, rom, {"dir": None})
    assert len(u.plays) == 1, u.plays


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
