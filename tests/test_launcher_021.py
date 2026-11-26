"""launcher 0.21: stop() solo sul gioco, contratto con l'overlay (pause/running/screenshot), estrazione sicura, Job chiuso."""

from __future__ import annotations

import sys
import time
import zipfile
from types import SimpleNamespace

from pozzo import config as C
from pozzo.library import launcher as L


class FakeUser:
    def __init__(self):
        self.plays = []

    def record_play(self, key, secs):
        self.plays.append(key)

    def mark_started(self, key):
        pass


def _wait(ln, status, secs=15):
    end = time.time() + secs
    while ln.state.get("status") != status and time.time() < end:
        time.sleep(0.05)
    return ln.state.get("status") == status


def test_stop_non_tocca_gli_altri_processi_della_cartella(tmp_path, monkeypatch):
    """Gioco manuale avviato direttamente: install_dir = cartella dell'exe, ma stop() chiude solo il gioco."""
    killed = []
    bystander = SimpleNamespace(terminate=lambda: killed.append("terminate"), kill=lambda: killed.append("kill"), pid=1)
    monkeypatch.setattr(L.Launcher, "_game_procs", staticmethod(lambda folder: [bystander]))
    ln = L.Launcher(C.Config(), FakeUser())
    ln.launch_pc("manual:1", "Lungo", {"type": "exe", "target": sys.executable, "args": ["-c", "import time; time.sleep(60)"]},
                 str(tmp_path), "manual")
    assert _wait(ln, "running"), ln.state
    assert ln._track is None
    assert ln._session_pids()  # il gioco si trova comunque (Job o processo)
    assert bystander.pid not in ln._session_pids()
    assert ln.stop() and _wait(ln, "finished")
    assert killed == []


def test_contratto_overlay(tmp_path, monkeypatch):
    ln = L.Launcher(C.Config(), FakeUser())
    st = ln.running()
    assert st["paused"] is False and st["paused_total"] == 0.0
    ln.state = {"status": "running", "key": "k"}
    monkeypatch.setattr(ln, "_session_pids", lambda: [123])
    monkeypatch.setattr(L, "_suspend", lambda pid, on: True)
    focused = []
    from pozzo.app import common
    monkeypatch.setitem(common.WINDOW_FOCUS, "fn", lambda: focused.append(1))
    assert ln.pause(focus_launcher=False) and focused == []
    time.sleep(0.05)
    r = ln.running()
    assert r["paused"] is True and r["paused_total"] > 0
    ln.resume()
    assert ln.running()["paused"] is False and ln.running()["paused_total"] > 0
    ln.state = {"status": "running", "key": "k"}
    assert ln.pause() and focused == [1]  # default: Pozzo davanti come prima
    ln.resume()


def test_screenshot_passa_il_pid(monkeypatch):
    from pozzo.library import screens
    got = []
    monkeypatch.setattr(screens, "capture_foreground", lambda pid=None: got.append(pid) or object())
    monkeypatch.setattr(screens, "beep", lambda: None)
    ln = L.Launcher(C.Config(), FakeUser(), shots=SimpleNamespace(add_image=lambda k, i: 7))
    ln.state = {"status": "running", "key": "k"}
    ln._proc = SimpleNamespace(pid=4242, poll=lambda: None)
    assert ln.screenshot() and got == [4242]
    ln._proc = None
    got.clear()
    monkeypatch.setattr(ln, "_session_pids", lambda: [])
    assert ln.screenshot() and got == [None]


def test_extract_zip_traversal(tmp_path):
    z = tmp_path / "g.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("Game/game.cue", "cue")
        f.writestr("Game/game.bin", "b" * 100)
        f.writestr("../evil.txt", "x")
        f.writestr("a/../../evil2.txt", "x")
    cfg = SimpleNamespace(cache=tmp_path / "cache")
    out = L._extract(cfg, z, "id", lambda m: None)
    assert out.name == "game.bin" and out.read_bytes() == b"b" * 100
    assert (out.parent / "game.cue").exists()
    assert not (tmp_path / "cache" / "evil.txt").exists() and not (tmp_path / "evil.txt").exists()
    assert not (tmp_path / "cache" / "extract" / "evil.txt").exists()
    assert not (tmp_path / "cache" / "evil2.txt").exists()


def test_job_si_chiude_dopo_errore(tmp_path, monkeypatch):
    closed = []

    class J:
        def add(self, p):
            return False

        def close(self):
            closed.append(1)

        def pids(self):
            return []

        def kill(self):
            pass

        def active(self):
            return 0

    monkeypatch.setattr(L._Job, "new", staticmethod(lambda: J()))
    ln = L.Launcher(C.Config(), FakeUser())
    ln.launch_pc("manual:2", "Rotto", {"type": "exe", "target": str(tmp_path / "manca.exe"), "args": []}, str(tmp_path), "manual")
    assert _wait(ln, "error")
    time.sleep(0.3)
    assert closed == [1]


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
