"""0.21.0 (W4c): library server paired with the old whole-cert fp keeps working; new pairings pin the key (SPKI)."""
from __future__ import annotations

import hashlib
import ssl
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_sync_021b import _serve  # noqa: E402

from pozzo.remote import certs  # noqa: E402
from pozzo.stores import pozzoremote as PR  # noqa: E402


def test_open_pinned_accepts_spki_and_old_cert_fp():
    t = Path(tempfile.mkdtemp())
    crt, key, _ = certs.ensure(t)
    srv, url = _serve(crt, key)
    try:
        der = ssl.PEM_cert_to_DER_cert(crt.read_text())
        spki, whole = certs.spki_fp(der), hashlib.sha256(der).hexdigest()
        for fp in (None, spki, whole):
            conn, r, got = PR.open_pinned(url, fp, "POST", "/x", body={})
            conn.close()
            assert got == spki, "new pairings pin the key"
        try:
            PR.open_pinned(url, "0" * 64, "POST", "/x", body={})
        except PR.PinError:
            pass
        else:
            raise AssertionError("wrong fp accepted")
    finally:
        srv.shutdown()


def test_back_pin_uses_spki():
    src = (Path(__file__).resolve().parent.parent / "pozzo/app/routes/sync.py").read_text(encoding="utf-8")
    assert "certs.spki_fp(" in src and "hashlib.sha256(ssl.PEM_cert_to_DER_cert" not in src
