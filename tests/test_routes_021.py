"""Fix 0.21.0 delle rotte system / scan / library. Esegui: python tests/test_routes_021.py"""
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pozzo.app.routes import system  # noqa: E402


def test_rebuild_concorrenti_non_si_perdono():
    running, peak, calls = [0], [0], []
    first_in, release = threading.Event(), threading.Event()

    def fake_build(cfg, log=print, progress=None):
        running[0] += 1
        peak[0] = max(peak[0], running[0])
        calls.append(1)
        if len(calls) == 1:
            first_in.set()
            release.wait(10)
        running[0] -= 1
        return {}

    real = system.build
    system.build = fake_build
    try:
        state = {"building": False, "build_log": [], "build_stats": None}
        ctx = SimpleNamespace(SUN=None, _emu_row=None, _pregen_thumbs=lambda: None, cfg=SimpleNamespace(config_path=None),
                              job={"current": SimpleNamespace(status="idle")}, launcher=None,
                              lib=SimpleNamespace(load=lambda: None), state=state, user=None)
        system.build_router(ctx)
        t1 = threading.Thread(target=ctx._rebuild)
        t1.start()
        assert first_in.wait(5)
        t2 = threading.Thread(target=ctx._rebuild)  # arriva a meta' della prima
        t2.start()
        t2.join(2)
        assert not t2.is_alive(), "la seconda richiesta non deve aspettare dentro la costruzione"
        assert state["building"]
        release.set()
        t1.join(10)
    finally:
        system.build = real
    assert len(calls) == 2, "la richiesta arrivata durante la costruzione va rifatta dopo"
    assert peak[0] == 1, "mai due costruzioni insieme (library.tmp)"
    assert state["building"] is False


def _claim_like_server(job):
    lock = threading.Lock()

    def claim(name, j):
        with lock:
            if name in job and job[name].status == "running":
                return False
            j.status = "running"
            job[name] = j
            return True
    return claim


def test_scan_start_due_volte_di_fila_409():
    from fastapi import HTTPException
    from pozzo.app import jobs as J
    from pozzo.app.routes import scan
    idle = lambda: SimpleNamespace(status="idle")  # noqa: E731
    job = {"current": idle(), "stores": idle(), "store_refresh": idle()}
    ctx = SimpleNamespace(_missing=None, _pregen_thumbs=None, _rebuild=None, _refresh_manual=None,
                          cfg=SimpleNamespace(config_path=None), events=None, job=job, lib=None,
                          state={"building": False}, user=None, _claim=_claim_like_server(job))
    real_run = J.ScrapeJob.run
    J.ScrapeJob.run = lambda self, *a, **k: None  # il thread parte ma lo stato non cambia da solo
    try:
        scan.build_router(ctx)
        ctx.api_scan_start({})
        try:
            ctx.api_scan_start({})
        except HTTPException as e:
            assert e.status_code == 409
        else:
            raise AssertionError("il secondo avvio doveva dare 409")
    finally:
        J.ScrapeJob.run = real_run


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
