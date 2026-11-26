"""0.21.0: impostazioni sincronizzate senza cancellare l'altro PC; abbinamento dei PC nei due sensi."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pozzo import config, sync  # noqa: E402


def _cfg():
    d = Path(tempfile.mkdtemp())
    cfg = config.Config(cache=d / "cache", output=d / "out")
    cfg.config_path = d / "config.toml"
    return cfg


def test_fresh_pc_does_not_wipe_other_pc_settings():
    a, b = _cfg(), _cfg()
    config.save_settings(a, igdb={"client_id": "X", "client_secret": "Y"}, app={"theme": "neon"})
    ca, cb = sync.conf(a), sync.conf(b)
    ba, bb = sync.settings_bundle(a, ca), sync.settings_bundle(b, cb)
    assert bb["t"] == 0 and ba["t"] == 0, "prima volta: non e' 'il piu' recente'"
    assert not sync.merge_settings(a, ca, bb)
    # anche se B ha un'ora recente ma non ha quelle sezioni, A le tiene
    config.save_settings(b, app={"wishlist": {"x": 1}})
    bb = sync.settings_bundle(b, cb)
    assert bb["t"] > 0
    assert sync.merge_settings(a, ca, bb)
    s = config.read_settings(a)
    assert s["igdb"]["client_id"] == "X" and s["app"]["theme"] == "neon", s
    assert s["app"]["wishlist"] == {"x": 1}


def test_peer_pairing_is_stored_on_both_sides():
    """Chi mostra il codice registra anche chi si abbina (con un token per tirare i suoi salvataggi)."""
    import socket

    from fastapi.testclient import TestClient

    from pozzo.app.server import create_app
    from pozzo.remote import certs
    real_lan_ips = certs.lan_ips
    certs.lan_ips = lambda: ["127.0.0.1"]  # indipendente dalla rete della macchina: i PC si danno il loopback
    ports = []
    for _ in range(2):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            ports.append(s.getsockname()[1])
    apps = {}
    for name, port in zip("AB", ports):
        d = Path(tempfile.mkdtemp()) / name
        d.mkdir(parents=True)
        cfg = config.Config(cache=d / "cache", output=d / "out")
        cfg.config_path = d / "config.toml"
        cfg.app["phone"] = {"port": port, "host": "127.0.0.1"}  # solo loopback: niente collisioni/esposizione in parallelo
        app = create_app(cfg)
        apps[name] = (cfg, app, TestClient(app))
    try:
        (cfg_a, app_a, ca), (cfg_b, app_b, cb) = apps["A"], apps["B"]
        code = ca.post("/api/sync/code").json()["code"]
        assert app_a.state.phone_hub.code_kind == "pc"
        assert cb.post("/api/sync/peer", json={"url": f"127.0.0.1:{ports[0]}", "code": code}).status_code == 200
        pa = sync.conf(cfg_a)["peers"]
        assert len(pa) == 1 and pa[0]["id"] == sync.conf(cfg_b)["pc_id"], pa
        assert pa[0]["url"].startswith("https://") and len(pa[0]["fp"]) == 64
        dev = app_b.state.phone_hub.device_for(pa[0]["token"])  # il token e' valido su B
        assert dev and dev["kind"] == "pc"
    finally:
        certs.lan_ips = real_lan_ips
        app_a.state.phone_hub.stop()
        app_b.state.phone_hub.stop()
