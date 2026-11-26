"""0.21.0b: gruppi store con anno nel titolo, lookups negativi scaduti, Ledger senza flush a ogni used().

Esegui: python tests/test_scrape_021b.py
"""
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pozzo import net  # noqa: E402
from pozzo.cache import Cache  # noqa: E402
from pozzo.cachepolicy import ttls  # noqa: E402
from pozzo.library import build  # noqa: E402
from pozzo.policy import Ledger  # noqa: E402
import pozzo.stores as stores  # noqa: E402


def snap(store, i, title):
    return {"store": store, "id": i, "title": title, "installed": True}


def test_year_groups():
    orig = stores.load_snapshots
    stores.load_snapshots = lambda cache: [snap("steam", "1", "DOOM (1993)"), snap("steam", "2", "DOOM"),
                                           snap("steam", "3", "Game"), snap("epic", "4", "Game")]
    try:
        cache = SimpleNamespace(kv_get=lambda k: None)
        es = {e["key"]: e for e in build._store_entries(SimpleNamespace(app={}), cache)}
    finally:
        stores.load_snapshots = orig
    assert es["windows/steam:1"]["grp"] != es["windows/steam:2"]["grp"]
    assert es["windows/steam:1"]["primary"] and es["windows/steam:2"]["primary"]
    assert es["windows/steam:3"]["grp"] == es["windows/epic:4"]["grp"]


def test_negative_lookup_expiry():
    with tempfile.TemporaryDirectory() as tmp:
        c = Cache(Path(tmp))
        now = time.time()
        neg = ttls("rawg")[1]
        for k, st, ts in (("a", "notfound", now - neg - 10), ("b", "notfound", now - 60),
                          ("c", "found", now - 10 * neg), ("d", "nodata", now - neg - 10),
                          ("e", "done", now - 8 * 86400)):
            c.db.execute("INSERT INTO lookups VALUES(?,?,?,?)", (k, "rawg", st, ts))
        got = c.lookup_status(list("abcde"), "rawg")
        assert got == {"b": "notfound", "c": "found", "e": "done"}, got
        c.db.close()


def test_ledger_no_flush_on_used():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "l.db"
        led = Ledger(db)
        led.spend("x", 3)
        led._last = time.monotonic()  # niente flush periodico in spend
        led.spend("x")
        assert led.used("x") == (4, 4), led.used("x")
        con = sqlite3.connect(db)
        raw = con.execute("SELECT COUNT(*) FROM usage").fetchone()[0]
        con.close()
        assert raw == 0, "used() ha scritto sul DB"
        led.flush()
        assert led.used("x") == (4, 4)
        led.close()


def test_ua():
    assert "github.com/erpaffo/Pozzo-Launcher" in net.UA, net.UA


if __name__ == "__main__":
    test_year_groups(); test_negative_lookup_expiry(); test_ledger_no_flush_on_used(); test_ua()
    print("OK test_scrape_021b")
