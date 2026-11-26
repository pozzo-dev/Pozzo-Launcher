"""0.21.0 (round fix): le impronte salvate all'abbinamento si aggiornano a quella della chiave (SPKI)."""
from __future__ import annotations

import hashlib
import ssl
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pozzo import config, sync  # noqa: E402
from pozzo.remote import certs  # noqa: E402
from pozzo.stores import pozzoremote as PR  # noqa: E402
from test_sync_021b import _serve  # noqa: E402


def _server():
    t = Path(tempfile.mkdtemp())
    orig, certs.lan_ips = certs.lan_ips, lambda: ["192.168.7.7"]
    try:
        crt, key, _ = certs.ensure(t)
    finally:
        certs.lan_ips = orig
    srv, url = _serve(crt, key)
    old = hashlib.sha256(ssl.PEM_cert_to_DER_cert(crt.read_text())).hexdigest()  # impronta pre-0.21
    return srv, url, old, certs.spki_fp(ssl.PEM_cert_to_DER_cert(crt.read_text()))


def _cfg():
    d = Path(tempfile.mkdtemp())
    cfg = config.Config(cache=d / "cache", output=d / "out")
    cfg.config_path = d / "config.toml"
    return cfg


def test_old_peer_fp_upgraded_to_spki():
    srv, url, old, spki = _server()
    try:
        cfg = _cfg()
        c = sync.conf(cfg)
        c["peers"] = [{"id": "p1", "url": url, "token": "t", "fp": old}]
        sync.save_conf(cfg, c)
        s = sync.Sync(cfg, lambda pid: None)
        s.bundles = lambda only=None: {}
        s.via_peer(sync.conf(cfg)["peers"][0])
        assert sync.conf(cfg)["peers"][0]["fp"] == spki, sync.conf(cfg)["peers"]
        assert config.read_settings(cfg)["app"]["sync"]["peers"][0]["fp"] == spki  # su disco
    finally:
        srv.shutdown()


def test_old_libshare_server_fp_upgraded_to_spki():
    srv, url, old, spki = _server()
    try:
        cfg = _cfg()
        cfg.stores["pozzoremote"] = {"servers": [{"id": "s1", "url": url, "token": "t", "fp": old}]}
        sv = PR.servers(cfg.stores["pozzoremote"])[0]
        PR.call(sv, "POST", "/x", {})
        PR.flush_pins(cfg)
        assert config.read_settings(cfg)["stores"]["pozzoremote"]["servers"][0]["fp"] == spki
        assert sv["fp"] == spki
    finally:
        srv.shutdown()


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
    print("ok")
