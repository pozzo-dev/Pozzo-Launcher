"""0.21.0 (W4c): una collezione cancellata non si riempie di nuovo coi vecchi giochi; impronta della chiave del PC."""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pozzo import config, sync  # noqa: E402

PROF = {"id": "default", "name": "Principale"}


def _ud(name):
    d = Path(tempfile.mkdtemp())
    cfg = config.Config(cache=d / "cache", output=d / "out")
    cfg.config_path = d / "config.toml"
    return sync.open_profile(cfg, "default"), {"pc_id": name, "pc_name": name}


def _sync(a, pa, b, pb):
    time.sleep(0.01)  # ore distinte tra una modifica e la successiva
    sync.merge(b, sync.export(a, PROF, pa))
    sync.merge(a, sync.export(b, PROF, pb))


def test_deleted_collection_does_not_refill():
    a, pa = _ud("A")
    b, pb = _ud("B")
    slug = a.create_collection("Rpg")
    a.edit_membership(slug, "nes/A", "add")
    a.edit_membership(slug, "nes/B", "add")
    _sync(a, pa, b, pb)
    assert len(b.edits()) == 2
    time.sleep(0.01)
    a.delete_collection(slug)
    sync.merge(a, sync.export(b, PROF, pb))  # B non sa ancora della cancellazione e rimanda le vecchie modifiche
    assert a.edits() == [], a.edits()
    _sync(a, pa, b, pb)
    assert not b.collections().get(slug) and not a.edits()
    time.sleep(0.01)
    assert a.create_collection("Rpg") == slug
    _sync(a, pa, b, pb)
    assert a.edits() == [] and b.edits() == [], (a.edits(), b.edits())


def _serve(crt, key):
    import http.server
    import ssl
    import threading

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *a):
            pass
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(crt, key)
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"https://127.0.0.1:{srv.server_port}"


def test_pin_survives_leaf_regeneration_and_accepts_old_cert_fp():
    import hashlib
    import ssl

    from pozzo.remote import certs
    t = Path(tempfile.mkdtemp())
    ips = ["192.168.7.7"]
    orig, certs.lan_ips = certs.lan_ips, lambda: ips
    try:
        crt, key, _ = certs.ensure(t)
        srv, url = _serve(crt, key)
        spki = sync.request(url, "/x", {})["_fp"]
        cert_fp = hashlib.sha256(ssl.PEM_cert_to_DER_cert(crt.read_text())).hexdigest()
        assert spki != cert_fp
        assert sync.request(url, "/x", {}, fp=cert_fp)["_fp"] == spki  # vecchio abbinamento: ancora valido
        srv.shutdown()
        ips.append("10.9.9.9")  # nuovo adattatore: certificato nuovo, stessa chiave
        crt, key, _ = certs.ensure(t)
        srv, url = _serve(crt, key)
        assert sync.request(url, "/x", {}, fp=spki)["_fp"] == spki
        try:
            sync.request(url, "/x", {}, fp="0" * 64)
        except RuntimeError:
            pass
        else:
            raise AssertionError("impronta sbagliata accettata")
        srv.shutdown()
    finally:
        certs.lan_ips = orig


if __name__ == "__main__":
    test_deleted_collection_does_not_refill()
    test_pin_survives_leaf_regeneration_and_accepts_old_cert_fp()
    print("ok")
