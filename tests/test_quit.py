"""Uscita dall'app: File > Esci e l'aggiornamento passano dallo spegnimento ordinato (stato dei download salvato), anche
quando dura qualche secondo. Processo vero con run(); finte solo la finestra e la durata di Manager.stop.

Esegui: python tests/test_quit.py
"""
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from pozzo import net  # noqa: E402
from pozzo.downloads import manager as M  # noqa: E402

CHILD = r"""
import sys, threading, time, types
from pathlib import Path
root, tmp, port, mode = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
sys.path[:0] = [root, root + "/tests"]
from pozzo import notify, onexit, updates
from pozzo.app import browserdl, server
from pozzo.downloads.manager import Manager
from test_apiv1 import make_library, tmp_cfg
import webbrowser

webbrowser.open = lambda *a, **k: None
notify.start_tray = lambda *a, **k: None
notify.remove = lambda: None
browserdl.install = lambda: None
updates.install = lambda c, quit: quit()
real = Manager.stop
def slow(self):
    time.sleep(4)  # un torrent che salva i dati di ripresa: piu' di 3 s, meno dei 6 che stop() aspetta
    real(self)
    (tmp / "stopped").write_text("ok")
Manager.stop = slow
onexit.register(lambda: (tmp / "restored").write_text("ok"))  # gioco sospeso, controller nascosto

class Event(list):
    def __iadd__(self, f):
        self.append(f)
        return self

class Window:
    def __init__(self):
        self.events = types.SimpleNamespace(closing=Event(), closed=Event(), loaded=Event(), shown=Event())
        self.x = self.y = 0
        self.width = self.height = 100
    def destroy(self):
        for f in [*self.events.closing]:
            f()
        web.windows.remove(self)
        done.set()
        for f in [*self.events.closed]:
            f()
    def show(self):
        pass

done = threading.Event()
web = types.ModuleType("webview")
web.windows = []
def create_window(*a, **k):
    web.windows.append(Window())
    return web.windows[-1]
def start(*a, **k):
    if mode == "broken":
        raise RuntimeError("WebView2 assente")
    done.wait()
web.create_window, web.start = create_window, start
sys.modules["webview"] = web
rom = tmp / "game.gba"
rom.write_bytes(b"x" * 100)
make_library(tmp, rom)
server.run(tmp_cfg(tmp, rom), port=port, browser=mode == "browser")
"""


def _post(port: int, path: str):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=b"{}", method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())


def _quit(tmp: Path, mode: str, path: str):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    script = tmp / "child.py"
    script.write_text(CHILD, encoding="utf-8")
    out = open(tmp / "out.txt", "w+", encoding="utf-8", errors="replace")
    p = subprocess.Popen([sys.executable, str(script), str(ROOT), str(tmp), str(port), mode], stdout=out, stderr=out,
                         env={**os.environ, "PYTHONUTF8": "1", "POZZO_NO_SAMPLE": "1"})
    try:
        end = time.time() + 60
        while True:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=2).read()
                break
            except OSError:
                assert p.poll() is None and time.time() < end, (tmp / "out.txt").read_text("utf-8", "replace")
                time.sleep(0.2)
        time.sleep(1)  # la finestra nasce dopo il server
        # flusso aperto come nella pagina vera: non deve tenere appesa la chiusura
        stream = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/downloads/events", timeout=20)
        _post(port, path)
        p.wait(25)
        stream.close()
        assert (tmp / "stopped").exists(), f"{mode} {path}: uscito senza aspettare Manager.stop\n" \
            + (tmp / "out.txt").read_text("utf-8", "replace")
        assert (tmp / "restored").exists(), f"{mode} {path}: ripristini di uscita saltati"
    finally:
        p.kill()
        p.wait()
        out.close()


def test_esci_con_la_finestra(tmp):
    _quit(tmp, "window", "/api/app/quit")


def test_esci_nel_browser(tmp):
    _quit(tmp, "browser", "/api/app/quit")


def test_esci_se_la_finestra_non_parte(tmp):
    _quit(tmp, "broken", "/api/app/quit")


def test_aggiornamento(tmp):
    _quit(tmp, "window", "/api/update/install")


def _stop(tmp, guasto=False) -> list[str]:
    cfg = SimpleNamespace(cache=tmp / "cache", app={"downloads": {"dir": str(tmp / "out")}})
    m = M.Manager(cfg, client_factory=net.make_client, save=lambda new: None)
    m.start()
    end = time.time() + 20
    while not m._loop and time.time() < end:
        time.sleep(0.05)
    log = []

    async def lento():
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            await asyncio.sleep(1)
            log.append("job finito")
            raise

    async def avvia():
        job = asyncio.ensure_future(lento())
        await asyncio.sleep(0.1)  # partito: la cancellazione arriva dentro il try
        return job
    m._jobs["x"] = asyncio.run_coroutine_threadsafe(avvia(), m._loop).result(5)
    real, me = m.store.save, threading.get_ident()

    def save(ts):
        if threading.get_ident() == me:  # solo quelli di stop(): il ciclo salva per conto suo
            log.append("salvato")
            if guasto and len(log) == 1:
                raise OSError("disco pieno")
        real(ts)
    m.store.save = save
    m.stop()
    return log


def test_lo_stato_si_salva_prima_di_aspettare(tmp):
    """Se il processo viene chiuso durante l'attesa dei torrent, lo stato dei download e' gia' su disco."""
    log = _stop(tmp)
    assert log == ["salvato", "job finito", "salvato"], log


def test_salvataggio_fallito_non_salta_l_attesa(tmp):
    """Disco pieno al primo salvataggio: i job si fermano in ordine lo stesso e si riprova alla fine."""
    log = _stop(tmp, guasto=True)
    assert log == ["salvato", "job finito", "salvato"], log


def test_tempo_di_gioco_registrato_alla_chiusura(tmp):
    """Gioco ancora aperto quando Pozzo si chiude: il tempo si conta, una volta sola."""
    from pozzo import config
    from pozzo.library import launcher as L
    cfg = config.Config(cache=tmp / "cache", output=tmp / "out")
    got = []
    user = SimpleNamespace(mark_started=lambda k: None, record_play=lambda k, s: got.append((k, s)))
    ln = L.Launcher(cfg, user)
    ln.close_session()
    assert got == [], "nessun gioco aperto"
    ln.state = {"key": "pc/1", "status": "starting", "started": time.time()}
    ln._fg = ln._hotkey = ln._pause_hotkey = None
    ln._start_capture = lambda: None
    ln._set(status="running")
    ln._t0 -= 3600
    ln.close_session()
    ln.close_session()
    ln._record("pc/1", 5)  # il thread della partita che finisce un attimo dopo
    ln._set(status="finished")
    assert len(got) == 1 and got[0][0] == "pc/1" and 3600 <= got[0][1] < 3610, got


def test_niente_aggiornamento_con_un_gioco_aperto(tmp):
    from fastapi.testclient import TestClient
    from pozzo import updates
    from pozzo.app.server import create_app
    from test_apiv1 import make_library, tmp_cfg
    rom = tmp / "game.gba"
    rom.write_bytes(b"x" * 100)
    make_library(tmp, rom)
    app = create_app(tmp_cfg(tmp, rom))
    real, calls = updates.install, []
    updates.install = lambda c, quit: calls.append(1)
    try:
        app.state.launcher.state = {"key": "k", "status": "running", "title": "G"}
        r = TestClient(app).post("/api/update/install", json={})
        time.sleep(0.2)
        assert r.status_code == 409 and not calls, (r.status_code, calls)
    finally:
        updates.install, updates.STATE["status"] = real, "idle"


if __name__ == "__main__":
    for f in [v for k, v in list(globals().items()) if k.startswith("test_")]:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            f(Path(d))
        print("ok ", f.__name__)
