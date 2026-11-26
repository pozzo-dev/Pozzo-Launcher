"""Fix 0.21.0 (giro c): cache API parallela, Ledger.used. Nessuna rete."""
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient  # noqa: E402

from test_library_routes_021 import _app  # noqa: E402


def test_api_library_parallela_senza_errori(tmp, monkeypatch):
    cfg, app = _app(tmp, monkeypatch)
    errs = []

    def work(i):
        try:
            c = TestClient(app)
            for n in range(40):
                cfg.app["hide_dlc"] = [f"{i}-{n}"]  # chiave diversa ogni volta: forza la pulizia della cache
                assert c.get("/api/library?part=owned").status_code == 200
        except Exception as e:  # noqa: BLE001
            errs.append(repr(e))
    ts = [threading.Thread(target=work, args=(i,)) for i in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errs, errs[:3]
