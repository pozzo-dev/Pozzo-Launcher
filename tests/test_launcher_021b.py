"""launcher 0.21b: un gioco mai partito dal launcher non conta, il ritentativo dopo crash conta una partita sola."""

from __future__ import annotations

import sys
from types import SimpleNamespace

from pozzo import config as C
from pozzo.library import launcher as L


class FakeUser:
    def __init__(self):
        self.plays = []

    def record_play(self, key, secs):
        self.plays.append((key, secs))

    def mark_started(self, key):
        pass


def test_gioco_mai_partito_non_registra(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "LAUNCH_TRIES", 1)
    monkeypatch.setattr(L, "LAUNCH_CHECK", 0.1)
    monkeypatch.setattr(L, "open_uri", lambda u: None)
    monkeypatch.setattr(L.Launcher, "_game_procs", staticmethod(lambda folder: []))
    u = FakeUser()
    ln = L.Launcher(C.Config(), u)
    ln._run_pc_body("epic:1", {"type": "uri", "target": "x://y", "track_dir": str(tmp_path)}, str(tmp_path), "epic", {"dir": None})
    assert u.plays == []


def test_ritentativo_dopo_crash_conta_una_partita(tmp_path, monkeypatch):
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
    monkeypatch.setattr(L, "plan", lambda *a, **k: {"emulator": "alt", "core": "", "exe": sys.executable, "args": ["-c", "pass"]})
    # una crash gia' registrata: questo e' il secondo di fila, quindi parte l'alternativa
    L._crash_update(cfg, "k", lambda e: e["runs"].append({"time": 1, "code": 3, "duration": 1, "log": ""}))
    plat = SimpleNamespace(id="ps1")
    pl = {"emulator": "emu", "core": "", "exe": sys.executable, "args": ["-c", "import sys; sys.exit(3)"]}
    ln._run_emu("k", plat, rom, pl, rom, {"dir": None})
    assert len(u.plays) == 1, u.plays  # il tentativo fallito e poi ritentato non e' una partita


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
