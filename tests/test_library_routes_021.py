"""Fix 0.21.0 di routes/library.py: cache della risposta, magnet singolo, link in parallelo. Nessuna rete."""
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from pozzo import config  # noqa: E402
from pozzo.app.server import create_app  # noqa: E402
from test_frontend import make_library  # noqa: E402


def _app(tmp, monkeypatch):
    rom = tmp / "g.gba"
    rom.write_bytes(b"x")
    cfg = config.Config(cache=tmp, output=tmp / "out")
    cfg.config_path = tmp / "config.toml"
    make_library(tmp, rom)
    from pozzo.app.routes import system
    monkeypatch.setattr(system, "build", lambda cfg, log=print, progress=None: {})
    return cfg, create_app(cfg)


def test_smart_collections_cambiate_invalidano_la_cache(tmp, monkeypatch):
    cfg, app = _app(tmp, monkeypatch)
    c = TestClient(app)
    cfg.app["smart_collections"] = [{"name": "A"}]
    assert c.get("/api/library?part=owned").json()["smart"][0]["name"] == "A"
    cfg.app["smart_collections"] = [{"name": "B"}]  # stessa lunghezza, contenuto diverso
    assert c.get("/api/library?part=owned").json()["smart"][0]["name"] == "B"


def test_single_magnet_errore_non_resta_in_cache(tmp, monkeypatch):
    cfg, app = _app(tmp, monkeypatch)
    c = TestClient(app)
    app.state.lib.game = lambda gid: {"title": "X", "platform": "gba", "launch": {
        "sources": [{"url": "https://minerva-archive.org/rom?id=1"}]}}
    calls = []

    def fake_get(url, **kw):
        calls.append(url)
        return httpx.Response(500, text="", request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx, "get", fake_get)
    c.post("/api/game/1/torrent")
    c.post("/api/game/1/torrent")
    assert len(calls) == 2, "un errore della pagina non va ricordato per sempre"


def test_links_pagine_in_parallelo(tmp, monkeypatch):
    cfg, app = _app(tmp, monkeypatch)
    c = TestClient(app)
    urls = ["https://a.example/x", "https://b.example/y"]
    app.state.lib.game = lambda gid: {"title": "X", "platform": "gba", "launch": {"sources": [{"url": u} for u in urls]}}
    barrier = threading.Barrier(2, timeout=3)  # passa solo se le due richieste sono in volo insieme

    def fake_fetch(u):
        barrier.wait()
        return u
    from pozzo import storelinks as SL
    monkeypatch.setattr(SL, "fetch", fake_fetch)
    monkeypatch.setattr(SL, "put", lambda cache, u, page: {"site": u, "links": [{"url": page}]})
    r = c.get("/api/game/1/links").json()
    assert not r["error"] and [x["url"] for x in r["links"]] == urls, r
