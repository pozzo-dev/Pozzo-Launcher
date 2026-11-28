"""Test offline di pozzo/achievements.py: fixture registrate (Steam x3, GOG, Epic), forma normalizzata, rarita', errori.

Esegui: pytest -q tests/test_achievements.py
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402
import pytest  # noqa: E402

from pozzo import achievements as A  # noqa: E402

FX = Path(__file__).resolve().parent / "fixtures"
fx = lambda n: json.loads((FX / n).read_text(encoding="utf-8"))  # noqa: E731


def client(handler):
    return A.http(httpx.MockTransport(handler))


def steam_handler(req):
    p = req.url.path
    if "GetPlayerAchievements" in p:
        return httpx.Response(200, json=fx("steam_player_ach.json"))
    if "GetSchemaForGame" in p:
        return httpx.Response(200, json=fx("steam_schema.json"))
    if "GetGlobalAchievementPercentagesForApp" in p:
        return httpx.Response(200, json=fx("steam_global.json"))
    return httpx.Response(404)


def test_steam_merge():
    r = A.steam(client(steam_handler), "K", "7656", "10")
    assert (r["source"], r["game_id"], r["total"], r["unlocked"]) == ("steam", "10", 2, 1)
    win, hid = r["items"]  # gli sbloccati per primi
    assert win["id"] == "ACH_WIN" and win["unlocked"] and win["unlocked_at"] == 1700000000
    assert win["icon"].endswith("win.jpg") and win["rarity_pct"] == 42.1  # percentuale come stringa
    assert hid["icon"].endswith("s_g.jpg") and hid["rarity_pct"] == 3.5 and not hid["unlocked"]


def test_steam_errors():
    with pytest.raises(A.AchError, match="chiave API"):
        A.steam(client(steam_handler), "", "", "10")
    with pytest.raises(A.AchError, match="negato"):
        A.steam(client(lambda r: httpx.Response(403)), "K", "7656", "10")
    with pytest.raises(A.AchError, match="rete"):
        def boom(r):
            raise httpx.ConnectError("no")
        A.steam(client(boom), "K", "7656", "10")
    priv = {"playerstats": {"success": False, "error": "Profile is not public"}}
    with pytest.raises(A.AchError, match="non e' pubblico"):
        A.steam(client(lambda r: httpx.Response(200, json=priv)), "K", "7656", "10")
    none = {"playerstats": {"success": False, "error": "Requested app has no stats"}}
    assert A.steam(client(lambda r: httpx.Response(200, json=none)), "K", "7656", "10")["total"] == 0


def test_gog():
    def h(req):
        assert req.headers["authorization"] == "Bearer T" and "/clients/C1/users/U1/" in req.url.path
        return httpx.Response(200, json=fx("gog_achievements.json"))
    r = A.gog(client(h), "T", "C1", "U1", "123")
    assert (r["source"], r["total"], r["unlocked"]) == ("gog", 2, 1)
    a, b = r["items"]
    assert a["name"] == "First" and a["icon"].endswith("u1.png") and a["unlocked_at"] == 1709287200 and a["rarity_pct"] == 55.5
    assert b["icon"].endswith("l2.png") and b["unlocked_at"] is None
    with pytest.raises(A.AchError, match="429"):
        A.gog(client(lambda r: httpx.Response(429)), "T", "C1", "U1", "123")


def test_gog_client_id(tmp_path):
    (tmp_path / "goggame-9.info").write_text('{"clientId": "555", "gameId": "9"}', encoding="utf-8")
    assert A.gog_client_id(str(tmp_path), "9") == "555"
    assert A.gog_client_id(str(tmp_path), "8") is None


def test_epic():
    def h(req):
        q = json.loads(req.content)
        assert req.headers["authorization"] == "Bearer T" and q["variables"]["sandboxId"] == "ns"
        return httpx.Response(200, json=fx("epic_mine.json" if "PlayerAchievement" in q["query"].split("{")[0] else "epic_defs.json"))
    r = A.epic(client(h), "T", "acc", "ns", "item")
    assert (r["source"], r["total"], r["unlocked"]) == ("epic", 2, 1)
    one, two = r["items"]
    assert one["id"] == "e1" and one["unlocked"] and one["rarity_pct"] == 10.0 and one["icon"].endswith("u.png")
    assert two["name"] == "Hidden" and two["description"] == ""  # segreto non sbloccato: niente spoiler
    with pytest.raises(A.AchError, match="Epic: boom"):
        A.epic(client(lambda r: httpx.Response(200, json={"errors": [{"message": "boom"}]})), "T", "acc", "ns", "item")


def test_api_pagina_obiettivi(tmp_path):
    """/api/achievements: totali, recenti (per data), piu' rari (per percentuale) e ultimo sblocco per gioco."""
    from fastapi.testclient import TestClient

    from pozzo import config as C
    from pozzo.app.server import create_app
    from pozzo.cache import Cache
    (tmp_path / "config.toml").write_text('[paths]\nroms = "roms"\ncache = "cache"\n[scrape]\nsources = []\n', encoding="utf-8")
    cfg = C.load(tmp_path / "config.toml")
    it = lambda n, at=None, pct=None: {"id": n, "name": n, "description": "", "icon": None,  # noqa: E731
                                        "unlocked": at is not None, "unlocked_at": at, "rarity_pct": pct}
    c = Cache(cfg.cache)
    c.kv_set("ach:steam:1", {"source": "steam", "game_id": "1", "title": "Uno", "total": 3, "unlocked": 2,
                             "items": [it("a", 100, 50.0), it("b", 300, 2.5), it("c")]})
    c.kv_set("ach:gog:2", {"source": "gog", "game_id": "2", "title": "Due", "total": 1, "unlocked": 1, "items": [it("d", 200, 9.0)]})
    c.kv_set("ach:epic:3", {"source": "epic", "game_id": "3", "title": "Vuoto", "total": 0, "unlocked": 0, "items": []})
    c.close()
    with TestClient(create_app(cfg)) as cl:
        d = cl.get("/api/achievements").json()
    assert d["totals"] == {"games": 2, "total": 4, "unlocked": 3, "perfect": 1}, d["totals"]
    assert [a["name"] for a in d["recent"]] == ["b", "d", "a"] and d["recent"][0]["game"] == "Uno"
    assert [a["name"] for a in d["rare"]] == ["b", "d", "a"]  # i piu' rari prima
    by = {g["title"]: g for g in d["games"]}
    assert set(by) == {"Uno", "Due"} and by["Uno"]["last_at"] == 300 and by["Due"]["unlocked"] == 1
    assert all(g["id"] is None for g in d["games"])  # nessun gioco in libreria: niente copertina ne' link
