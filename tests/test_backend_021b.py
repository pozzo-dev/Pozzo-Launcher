"""Fix 0.21.0 (W6): errors.log con tetto, avvio setup unico, rotte morte, int() sull'input -> 400, js_api di Big Picture.

Esegui: PYTHONUTF8=1 python tests/test_backend_021b.py   (o pytest)
"""
import os
import sys
import threading

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient  # noqa: E402

from pozzo import telemetry as T  # noqa: E402
from pozzo.app.server import create_app  # noqa: E402
from test_apiv1 import BASE, make_library, tmp_cfg  # noqa: E402


@pytest.fixture
def cfg(tmp_path):
    rom = tmp_path / "game.gba"
    rom.write_bytes(b"x" * 100)
    make_library(tmp_path, rom)
    return tmp_cfg(tmp_path, rom)


def test_errors_log_ruota(tmp_path):
    p = tmp_path / "errors.log"
    p.write_bytes(b"x" * (T.MAX_BYTES + 1))
    T.set_path(p)
    try:
        assert (tmp_path / "errors.log.old").exists() and not p.exists()
        T.log_error("t", "m")
        assert p.stat().st_size < 1000
    finally:
        T.set_path(None)
        T.clear()


def test_setup_doppio_avvio_409(cfg, monkeypatch):
    from pozzo.app.routes import setup as S
    gate = threading.Event()
    monkeypatch.setattr(S, "build", lambda cfg, log=print, progress=None: gate.wait(10))
    with TestClient(create_app(cfg), base_url=BASE) as c:
        try:
            assert c.post("/api/setup", json={"start": True, "scrape": False}).status_code == 200
            assert c.post("/api/setup", json={"start": True, "scrape": False}).status_code == 409
        finally:
            gate.set()


def test_rotte_morte_tolte(cfg):
    with TestClient(create_app(cfg), base_url=BASE) as c:
        assert c.post("/api/spotify/shuffle", json={}).status_code in (404, 405)
        assert c.post("/api/discord/volume", json={}).status_code in (404, 405)
        assert c.get("/api/maintenance/history").status_code in (404, 405)


@pytest.mark.parametrize("method,url,body", [
    ("post", "/api/collections/x/members", {"action": "add"}),
    ("post", "/api/collections/x/members", {"action": "add", "game": "abc"}),
    ("post", "/api/collections", {"name": "n", "game": "abc"}),
    ("post", "/api/scan", {"game": "abc"}),
    ("post", "/api/shots/open", {"id": "abc"}),
    ("post", "/api/sunshine", {"count": "abc"}),
    ("post", "/api/wishlist/settings", {"threshold": "abc"}),
    ("post", "/api/app/video-snap", {"max_mb": "abc"}),
    ("post", "/api/steamcmd/install", {"game_id": "abc"}),
    ("post", "/api/catalogs/gba/netmeta", {"limit": "abc"}),
])
def test_int_non_valido_400(cfg, method, url, body):
    with TestClient(create_app(cfg), base_url=BASE, raise_server_exceptions=False) as c:
        r = getattr(c, method)(url, json=body)
        assert r.status_code == 400, (url, r.status_code, r.text)


def test_bigpicture_passa_js_api(monkeypatch):
    import types

    from pozzo import cli, config
    from pozzo.app import server
    seen = {}
    fake = types.SimpleNamespace(create_window=lambda *a, **k: seen.update(k), start=lambda: None, windows=[])
    monkeypatch.setitem(sys.modules, "webview", fake)
    monkeypatch.setattr(server, "_is_pozzo", lambda port: True)
    monkeypatch.setattr(config, "load", lambda p=None: config.Config())
    cli.cmd_bigpicture(types.SimpleNamespace(config=None))
    api = seen["js_api"]
    assert callable(api.set_fullscreen) and callable(api.focus_window) and seen["fullscreen"] is True


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
