"""automation: il ripristino (risoluzione, piano energetico, HDR) parte anche all'uscita dell'app, una volta sola."""

from __future__ import annotations

from pozzo import onexit
from pozzo.library import automation


def test_ripristino_all_uscita(monkeypatch):
    n0 = len(onexit._FNS)
    ses = automation.Session({"after_cmd": "x"}, lambda ev: {}, lambda m: None)
    ses.begin()
    calls = []
    ses.undo.append(lambda: calls.append("undo"))
    ses_fns = onexit._FNS[n0:]
    assert ses_fns, "begin() deve registrare il ripristino in onexit"
    ran = []
    monkeypatch.setattr(automation, "run", lambda *a, **k: ran.append(a) or None)  # lo script «dopo» non deve partire all'uscita
    for fn in ses_fns:
        fn()
    assert calls == ["undo"] and not ran
    ses.end()  # fine partita dopo l'uscita: niente doppio ripristino
    assert calls == ["undo"]


def test_end_normale_una_volta():
    ses = automation.Session({}, lambda ev: {}, lambda m: None)
    ses.begin()
    calls = []
    ses.undo.append(lambda: calls.append(1))
    ses.end()
    for fn in onexit._FNS[-1:]:
        fn()
    assert calls == [1]


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
