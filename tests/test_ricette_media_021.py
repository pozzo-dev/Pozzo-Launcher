"""Fix 0.21.0 di ricette-web (kodi_addons, hls_proxy, addon Kodi, DB) e media-server (proxy artwork).

Esegui: PYTHONUTF8=1 python -m pytest -q tests/test_ricette_media_021.py
EXT_ROOT (solo per confronto con una copia vecchia delle estensioni) cambia la cartella extensions/.
"""
from __future__ import annotations

import importlib.util
import os
import socket
import sqlite3
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
EXT = Path(os.environ.get("EXT_ROOT") or ROOT / "extensions")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


kb = _load("kb021", EXT / "ricette-web" / "kodi_bridge.py")
rw = _load("rw021", EXT / "ricette-web" / "backend.py")
ms = _load("ms021", EXT / "media-server" / "backend.py")


class FakeGS:
    def __init__(self, cfg, settings=None):
        self.cfg, self.routes, self.settings = cfg, {}, settings or {}
        self.log = lambda *a, **k: None

    def route(self, path, methods=("GET",)):
        def deco(fn):
            self.routes[(path.lstrip("/"), methods[0])] = fn
            return fn
        return deco

    def get(self, path, **kw):
        return self.routes[(path.lstrip("/"), "GET")](**kw)

    def post(self, path, body=None, **kw):
        return self.routes[(path.lstrip("/"), "POST")](body=body, **kw)

    def add_player(self, p): pass
    def add_scraper(self, s): pass
    def add_library_kind(self, k): pass
    def job(self, *a, **k): pass


def make_rw(tmp: Path, monkeypatch):
    monkeypatch.setattr(rw, "load_recipes", lambda ext_dir=None: [])
    monkeypatch.setattr(rw, "kodi_bridge_module", lambda: kb)
    gs = FakeGS(SimpleNamespace(config_path=tmp / "config.toml", app={}))
    rw.register(gs)
    return gs, tmp / "ricette-web-cache"


def mock_client(monkeypatch, mod, handler):
    """Instrada httpx.Client del modulo su MockTransport."""
    real = httpx.Client
    monkeypatch.setattr(mod.httpx, "Client", lambda *a, **kw: real(*a, **{**kw, "transport": httpx.MockTransport(handler)}))


def resolve_to(monkeypatch, ip: str):
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port, *a, **k: [(2, 1, 6, "", (ip, 0))])


# ---------------------------------------------------------------- 1a kodi_addons
@pytest.mark.parametrize("bad", ["..", ".", "a/../b", "../x", ".hidden", "a\\b"])
def test_kodi_addons_remove_rifiuta_id_pericolosi(tmp_path, monkeypatch, bad):
    gs, cache = make_rw(tmp_path, monkeypatch)
    (cache / "kodi-addons").mkdir(exist_ok=True)
    (cache / "tieni.txt").write_text("x")
    with pytest.raises(HTTPException) as err:
        gs.post("kodi_addons", {"remove": bad})
    assert err.value.status_code == 400
    assert (cache / "tieni.txt").exists() and (cache / "ricette.db").exists()


def test_kodi_addons_remove_addon_valido(tmp_path, monkeypatch):
    gs, cache = make_rw(tmp_path, monkeypatch)
    d = cache / "kodi-addons" / "plugin.video.x"
    d.mkdir(parents=True)
    assert gs.post("kodi_addons", {"remove": "plugin.video.x"})["ok"] and not d.exists()


def test_safe_name_del_bridge_rifiuta_come_il_backend():
    for bad in ("..", ".", "a/b", ".x", "a b"):
        with pytest.raises(ValueError):
            kb._safe_name(bad)
    assert kb._safe_name("plugin.video.s4me") == "plugin.video.s4me"


# ---------------------------------------------------------------- 1b hls_proxy
def hls(gs, url):
    return gs.get("hls.m3u8", u=url)


def test_hls_proxy_rifiuta_reti_locali(tmp_path, monkeypatch):
    gs, _ = make_rw(tmp_path, monkeypatch)
    calls = []
    mock_client(monkeypatch, rw, lambda r: calls.append(r) or httpx.Response(200, content=b"x"))
    rw._PROXY_HOSTS.update({"localhost", "10.1.2.3", "cdn.vixcloud.test"})
    for url in ("http://localhost/a.ts", "http://10.1.2.3/a.ts", "http://127.0.0.1/a.ts"):
        with pytest.raises(HTTPException) as err:
            hls(gs, url)
        assert err.value.status_code == 403
    resolve_to(monkeypatch, "127.0.0.1")  # nome pubblico che punta al loopback (DNS rebinding)
    with pytest.raises(HTTPException) as err:
        hls(gs, "https://cdn.vixcloud.test/a.ts")
    assert err.value.status_code == 403 and not calls


def test_hls_proxy_redirect_verso_localhost_rifiutato(tmp_path, monkeypatch):
    gs, _ = make_rw(tmp_path, monkeypatch)
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port, *a, **k: [(2, 1, 6, "", ("127.0.0.1" if host == "localhost" else "93.184.216.34", 0))])
    rw._PROXY_HOSTS.add("localhost")
    calls = []

    def handler(r):
        calls.append(str(r.url))
        return httpx.Response(302, headers={"Location": "http://localhost:8765/api/secret"})

    mock_client(monkeypatch, rw, handler)
    with pytest.raises(HTTPException) as err:
        hls(gs, "https://cdn.vixcloud.test/a.ts")
    assert err.value.status_code == 403 and calls == ["https://cdn.vixcloud.test/a.ts"]


def test_hls_proxy_tetto_byte_e_content_type(tmp_path, monkeypatch):
    gs, _ = make_rw(tmp_path, monkeypatch)
    resolve_to(monkeypatch, "93.184.216.34")
    monkeypatch.setattr(rw, "MAX_PROXY", 50)
    body = {"v": (b"x" * 500, "video/mp2t")}
    mock_client(monkeypatch, rw, lambda r: httpx.Response(200, content=body["v"][0], headers={"content-type": body["v"][1]}))
    url = "https://cdn.vixcloud.test/a.ts"
    with pytest.raises(HTTPException) as err:
        hls(gs, url)
    assert err.value.status_code == 502
    body["v"] = (b"<html><script>x</script>", "text/html")
    with pytest.raises(HTTPException) as err:
        hls(gs, url)
    assert err.value.status_code == 502
    body["v"] = (b"x" * 20, "video/mp2t")
    out = hls(gs, url)
    assert out.body == b"x" * 20 and out.headers["x-content-type-options"] == "nosniff"
    body["v"] = (b"#EXTM3U\nseg.ts\n", "text/plain")  # le playlist si riconoscono dal contenuto
    out = hls(gs, url)
    assert out.media_type == "application/vnd.apple.mpegurl" and out.headers["x-content-type-options"] == "nosniff"


# ---------------------------------------------------------------- 1c addon Kodi + Stream4me
def test_stream4me_senza_addon_non_inventa_voci(tmp_path, monkeypatch):
    assert not hasattr(kb, "_STREAM4ME_SIMULATED")
    sec = kb.get_stream4me_sections(None, force=True)
    assert set(sec) == {"film", "serie", "canali", "animazione"} and not any(sec.values())
    gs, cache = make_rw(tmp_path, monkeypatch)
    res = gs.get("stream4me/sections")
    assert all(not s["items"] for s in res["sections"])
    n = sqlite3.connect(cache / "ricette.db").execute("SELECT COUNT(*) FROM items WHERE recipe_id='stream4me'").fetchone()[0]
    assert n == 0


def test_righe_example_vecchie_ripulite_all_avvio(tmp_path, monkeypatch):
    gs, cache = make_rw(tmp_path, monkeypatch)
    db = cache / "ricette.db"
    c = sqlite3.connect(db)
    for i, (rid, url) in enumerate([("stream4me", "https://stream4me.example/film"),
                                    ("stream4me", "https://cdn.example/x"), ("stream4me", "https://vero.it/a"),
                                    ("altro", "https://x.example/p")]):
        c.execute("INSERT INTO items (id, recipe_id, kind, title, url, stream_url) VALUES (?,?,?,?,?,?)",
                  (f"r{i}", rid, "film", "t", url, ""))
    c.commit()
    c.close()
    rw.register(FakeGS(SimpleNamespace(config_path=tmp_path / "config.toml", app={})))
    ids = {r[0] for r in sqlite3.connect(db).execute("SELECT id FROM items")}
    assert ids == {"r2", "r3"}  # restano la voce vera e quella di un'altra ricetta


def _addon(tmp_path: Path, secs: float) -> Path:
    d = tmp_path / "plugin.video.slow"
    d.mkdir(exist_ok=True)
    (d / "addon.xml").write_text('<addon id="plugin.video.slow" name="S" version="1"><extension point="xbmc.python.pluginsource" library="default.py"/></addon>')
    (d / "default.py").write_text(f"import time\ntime.sleep({secs})\n")
    return d


def test_addon_kodi_timeout_e_un_solo_addon_alla_volta(tmp_path, monkeypatch):
    d = _addon(tmp_path, 1.0)
    monkeypatch.setattr(kb, "ADDON_TIMEOUT", 0.2)
    t0 = time.time()
    with pytest.raises(TimeoutError):
        kb.run_kodi_addon_directory(d)
    with pytest.raises(TimeoutError):  # il primo gira ancora: il secondo non parte in parallelo
        kb.run_kodi_addon_directory(d)
    assert time.time() - t0 < 0.9
    time.sleep(1.2)  # il thread del primo finisce e libera il lock
    monkeypatch.setattr(kb, "ADDON_TIMEOUT", 5.0)
    assert kb.run_kodi_addon_directory(d) == []


# ---------------------------------------------------------------- 1d connessioni DB
def test_connect_unico_con_timeout_e_wal(tmp_path):
    c = rw._connect(tmp_path / "t.db")
    try:
        assert c.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    finally:
        c.close()
    assert (EXT / "ricette-web" / "backend.py").read_text("utf-8").count("sqlite3.connect(") == 1


# ---------------------------------------------------------------- 2 media-server: proxy artwork
def make_ms(monkeypatch, handler):
    mock_client(monkeypatch, ms, handler)
    gs = FakeGS(SimpleNamespace(), {"servers": {"plex": {"base_url": "http://plex.local:32400", "token": "TOK"}}})
    ms.register(gs)
    return gs


def test_artwork_redirect_ad_altro_host_non_seguito(monkeypatch):
    calls = []

    def handler(r):
        calls.append(r)
        return httpx.Response(302, headers={"Location": "http://evil.example/steal"})

    gs = make_ms(monkeypatch, handler)
    with pytest.raises(HTTPException):
        gs.get("artwork", src="/library/metadata/1/thumb", source="plex")
    assert len(calls) == 1 and "TOK" in str(calls[0].url)  # il token e' partito solo verso il server configurato


def test_artwork_tetto_tipo_e_nosniff(monkeypatch):
    state = {"body": b"x" * 100, "ct": "image/png"}
    gs = make_ms(monkeypatch, lambda r: httpx.Response(200, content=state["body"], headers={"content-type": state["ct"]}))
    out = gs.get("artwork", src="/library/metadata/1/thumb", source="plex")
    assert out.body == b"x" * 100 and out.media_type == "image/png" and out.headers["x-content-type-options"] == "nosniff"
    for body, ct in ((b"<html>", "text/html"), (b"<svg onload=1>", "image/svg+xml")):
        state.update(body=body, ct=ct)
        with pytest.raises(HTTPException):
            gs.get("artwork", src="/library/metadata/1/thumb", source="plex")
    monkeypatch.setattr(ms, "MAX_IMAGE", 50)
    state.update(body=b"x" * 500, ct="image/png")
    with pytest.raises(HTTPException) as err:
        gs.get("artwork", src="/library/metadata/1/thumb", source="plex")
    assert err.value.status_code == 502
