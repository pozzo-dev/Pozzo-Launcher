"""Coda del browser nascosto: la fase "In attesa" compare solo se il lock e' gia' occupato. Nessuna finestra."""

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pozzo import storelinks as SL  # noqa: E402
from pozzo.app import browserdl as B  # noqa: E402
from pozzo.downloads import resolvers  # noqa: E402

WAIT = "In attesa del browser (un altro download lo sta usando)"


class _Lock:
    """Lock finto: `locked()` dice se e' occupato, il `with` non blocca."""

    def __init__(self, busy):
        self.busy = busy

    def locked(self):
        return self.busy

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _spy(monkeypatch):
    seen = []
    monkeypatch.setattr(resolvers, "phase", lambda name: seen.append(name))
    return seen


def test_with_browser_mostra_attesa_solo_se_occupato(monkeypatch):
    monkeypatch.setitem(SL.RESOLVER, "fn", lambda url: "https://x.example/file.zip")
    monkeypatch.setitem(SL.RESOLVER, "reason", None)

    monkeypatch.setattr(SL, "_LOCK", _Lock(busy=True))
    seen = _spy(monkeypatch)
    assert SL.with_browser("https://short.example/a", timeout=5) == "https://x.example/file.zip"
    assert WAIT in seen

    monkeypatch.setattr(SL, "_LOCK", _Lock(busy=False))
    seen = _spy(monkeypatch)
    assert SL.with_browser("https://short.example/a", timeout=5) == "https://x.example/file.zip"
    assert WAIT not in seen


def test_browserdl_resolve_mostra_attesa_solo_se_occupato(monkeypatch):
    monkeypatch.setattr(B, "_resolve", lambda link, timeout: "ok")

    monkeypatch.setattr(B, "_LOCK", _Lock(busy=True))
    seen = _spy(monkeypatch)
    assert B.resolve("https://host.example/f", timeout=5) == "ok"
    assert WAIT in seen

    monkeypatch.setattr(B, "_LOCK", _Lock(busy=False))
    seen = _spy(monkeypatch)
    assert B.resolve("https://host.example/f", timeout=5) == "ok"
    assert WAIT not in seen


def test_lock_unificato_e_timeout_dopo_acquisizione(monkeypatch):
    """Un solo lock condiviso tra storelinks e browserdl; il timeout parte dopo aver acquisito il lock."""
    import time
    assert B._LOCK is SL._LOCK

    def slow_fn(url):
        if url.endswith("/1"):
            time.sleep(0.5)
            return "https://cdn/1"
        time.sleep(0.1)
        return "https://cdn/2"

    monkeypatch.setitem(SL.RESOLVER, "fn", slow_fn)
    monkeypatch.setitem(SL.RESOLVER, "reason", None)
    r1, r2 = [], []
    t1 = threading.Thread(target=lambda: r1.append(SL.with_browser("https://x.test/1", timeout=1.0)))
    t1.start()
    time.sleep(0.05)  # t1 ha gia' il lock
    # timeout=0.35 < 0.5: se il timeout partisse in coda scadrebbe prima di iniziare!
    t2 = threading.Thread(target=lambda: r2.append(SL.with_browser("https://x.test/2", timeout=0.35)))
    t2.start()
    t1.join(5)
    t2.join(5)
    assert r1 == ["https://cdn/1"] and r2 == ["https://cdn/2"]

    # rientro sullo stesso thread (SL.with_browser -> B.resolve) senza deadlock
    monkeypatch.setitem(SL.RESOLVER, "fn", lambda u: B.resolve(u, timeout=1))
    monkeypatch.setattr(B, "_resolve", lambda link, timeout: "https://cdn/ok")
    assert SL.with_browser("https://x.test/3", timeout=1) == "https://cdn/ok"
