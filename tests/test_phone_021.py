"""0.21.0: Moonlight dell'ospite (un PIN, nome, unpair alla revoca/scadenza), Origin nel PhoneGate, tipo del codice."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from pozzo import config  # noqa: E402
from pozzo.remote import phone as PH  # noqa: E402
from pozzo.remote import sunshine as SS  # noqa: E402


def new_hub() -> PH.PhoneHub:
    tmp = Path(tempfile.mkdtemp())
    (tmp / "roms").mkdir()
    (tmp / "config.toml").write_text('[paths]\nroms = "roms"\ncache = "cache"\n[scrape]\nsources = []\n', encoding="utf-8")
    cfg = config.load(tmp / "config.toml")
    cfg.app["sunshine"] = {"user": "u", "password": "p"}
    return PH.PhoneHub(cfg, config.save_settings)


class FakeSunshine:
    pinned: list = []
    unpaired: list = []
    clients_list: list = []

    @classmethod
    def from_conf(cls, conf, save=None):
        return cls()

    def pin(self, pin, name=""):
        FakeSunshine.pinned.append(name)
        FakeSunshine.clients_list.append({"name": name, "uuid": "uuid-" + name})
        return {"pending": 0}

    def clients(self):
        return list(FakeSunshine.clients_list)

    def unpair(self, uuid):
        FakeSunshine.unpaired.append(uuid)

    def close(self):
        pass


@pytest.fixture
def sun(monkeypatch):
    FakeSunshine.pinned, FakeSunshine.unpaired, FakeSunshine.clients_list = [], [], []
    monkeypatch.setattr(SS, "Sunshine", FakeSunshine)
    return FakeSunshine


def _guest_app(hub):
    app = FastAPI()
    PH.register(app, hub, Path(PH.__file__).resolve().parent.parent / "app" / "static")
    return TestClient(PH.PhoneGate(app, hub), base_url="https://testserver")


def test_guest_one_pin_named_and_unpaired_on_revoke(sun):
    hub = new_hub()
    hub._unpair_bg = hub.unpair_guest  # senza thread
    gate = _guest_app(hub)
    token = hub.join(hub.new_invite(), "Amico")
    did = hub.conf["devices"][0]["id"]
    gate.cookies.set(PH.COOKIE, token)
    assert gate.post("/g/api/pin", json={"pin": "1234"}).status_code == 200
    assert sun.pinned == [f"pozzo-guest-{did}"]
    assert gate.post("/g/api/pin", json={"pin": "5678"}).status_code == 409, "un solo PIN per ospite"
    assert len(sun.pinned) == 1
    hub.revoke(did)
    assert sun.unpaired == [f"uuid-pozzo-guest-{did}"]


def test_guest_expired_is_pruned_and_unpaired(sun):
    hub = new_hub()
    hub._unpair_bg = hub.unpair_guest
    token = hub.join(hub.new_invite(), "Amico")
    d = hub.conf["devices"][0]
    sun.clients_list.append({"name": f"pozzo-guest-{d['id']}", "uuid": "u1"})
    d["pinned"] = True
    d["created"] -= PH.GUEST_TTL + 1
    assert hub.device_for(token) is None
    assert hub.conf["devices"] == []
    assert sun.unpaired == ["u1"]


def test_revoke_survives_sunshine_down(monkeypatch):
    hub = new_hub()
    hub._unpair_bg = hub.unpair_guest
    hub.join(hub.new_invite(), "Amico")
    did = hub.conf["devices"][0]["id"]
    hub.mark_pin(did)

    class Boom(FakeSunshine):
        def clients(self):
            raise RuntimeError("giu'")
    monkeypatch.setattr(SS, "Sunshine", Boom)
    hub.revoke(did)
    assert hub.conf["devices"] == []


def test_origin_checked_on_post_and_ws():
    hub = new_hub()
    inner = FastAPI()
    PH.register(inner, hub, Path(PH.__file__).resolve().parent.parent / "app" / "static")

    hub.ensure_pad = lambda n: None
    gate = TestClient(PH.PhoneGate(inner, hub), base_url="https://testserver")
    code = hub.new_code()
    bad = {"Origin": "https://evil.example"}
    assert gate.post("/m/api/pair", json={"code": code, "name": "x"}, headers=bad).status_code == 403
    assert hub.conf["devices"] == []
    assert gate.post("/m/api/pair", json={"code": code, "name": "x"},
                     headers={"Origin": "https://testserver"}).status_code == 200
    assert gate.post("/m/api/pair", json={"code": "000000", "name": "x"}).status_code == 403  # senza Origin: passa al codice
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect) as e:
        with gate.websocket_connect("/m/ws", headers=bad):
            pass
    assert e.value.code == 4403
    hub.new_code()
    token = hub.pair(hub.code, "Tel")  # il cookie Secure non viaggia su ws:// del TestClient: lo passo a mano
    ok = {"Origin": "https://testserver", "Cookie": f"{PH.COOKIE}={token}"}
    with gate.websocket_connect("/m/ws", headers=ok) as w:
        assert w.receive_json()["t"] == "ok"


def test_code_kind_phone_vs_pc():
    hub = new_hub()
    code = hub.new_code()  # per telefoni
    with pytest.raises(ValueError):
        hub.pair(code, "PC", kind="pc")
    hub.new_code()
    hub.code = code = "123456"
    assert hub.pair(code, "Tel")
    code = hub.new_code("pc")
    with pytest.raises(ValueError):
        hub.pair(code, "Tel", kind="phone")
    hub.code = code
    assert hub.pair(code, "PC", kind="pc")
    assert sorted(d["kind"] for d in hub.conf["devices"]) == ["pc", "phone"]
