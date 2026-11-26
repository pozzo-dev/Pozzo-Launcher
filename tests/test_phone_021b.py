"""0.21.0 (W4c): ospiti e inviti scaduti da oltre 30 giorni spariscono quando se ne salva uno nuovo."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_phone_021 import new_hub  # noqa: E402

from pozzo.remote import libshare as LS  # noqa: E402

DAY = 86400


def test_join_and_pair_prune_stale():
    hub = new_hub()
    now = time.time()
    old = {"id": "old", "name": "x", "token": "t1", "created": now - 60 * DAY, "kind": "lib", "exp": now - 31 * DAY}
    recent = {"id": "rec", "name": "y", "token": "t2", "created": now - 10 * DAY, "kind": "lib", "exp": now - 2 * DAY}
    inv_old = {"id": "io", "name": "a", "hash": "h1", "created": now - 60 * DAY, "exp": now - 40 * DAY, "used": False, "device": ""}
    hub._save(devices=[old, recent], lib_invites=[inv_old])
    hub.new_invite()
    hub.join(hub.guest_code, "Ospite")
    ids = [d["id"] for d in hub.conf["devices"]]
    assert "old" not in ids and "rec" in ids and len(ids) == 2, ids
    _, code = LS.new_invite(hub, "Zia", 30)
    LS.pair(hub, code, "Zia")
    assert [i["id"] for i in hub.conf["lib_invites"] if i["id"] == "io"] == [], "invito scaduto da 40 giorni rimosso"
    assert len(hub.conf["lib_invites"]) == 1


def test_api_phone_keeps_unexpired_pc_code():
    """remote.js interroga /api/phone ogni 5 s: un codice «pc» (Impostazioni › Sync) ancora valido non va sostituito."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from pozzo.remote import phone as PH
    hub = new_hub()
    app = FastAPI()
    PH.register(app, hub, Path(PH.__file__).resolve().parent.parent / "app" / "static")
    hub.running = lambda: True
    c = TestClient(app)
    code = hub.new_code("pc")
    r = c.get("/api/phone").json()
    assert hub.code == code and hub.code_kind == "pc", "codice del PC sostituito"
    assert r["code"] is None
    hub.code_until = time.time() - 1  # scaduto: il telefono ne riceve uno suo
    r = c.get("/api/phone").json()
    assert hub.code_kind == "phone" and r["code"] == hub.code


if __name__ == "__main__":
    test_join_and_pair_prune_stale()
    test_api_phone_keeps_unexpired_pc_code()
    print("ok")
