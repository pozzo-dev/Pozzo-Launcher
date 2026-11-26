"""0.21.0: la porta si lega prima di costruire l'app (due copie insieme), e il server che non parte non blocca l'avvio."""
from __future__ import annotations

import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from pozzo.app import server as S  # noqa: E402


def _busy():
    sk = socket.socket()
    sk.bind(("127.0.0.1", 0))
    sk.listen()
    return sk, sk.getsockname()[1]


def test_run_second_copy_takes_already_running_branch(monkeypatch):
    sk, port = _busy()
    try:
        called = []
        monkeypatch.setattr(S, "create_app", lambda cfg: called.append(1))
        monkeypatch.setattr(S, "_is_pozzo", lambda p: True)
        monkeypatch.setattr(S, "_focus_running_window", lambda p: True)
        S.run(object(), port=port)
        assert not called, "la seconda copia non deve costruire l'app"
    finally:
        sk.close()


def test_run_foreign_program_uses_next_port(monkeypatch):
    sk, port = _busy()
    try:
        monkeypatch.setattr(S, "_is_pozzo", lambda p: False)
        monkeypatch.setattr(S, "_wait_pozzo", lambda p, secs=4: False)
        seen = []

        def boom(cfg):
            seen.append(1)
            raise RuntimeError("stop")
        monkeypatch.setattr(S, "create_app", boom)
        with pytest.raises(RuntimeError):
            S.run(object(), port=port)
        assert seen
    finally:
        sk.close()


def test_bind_port_is_exclusive():
    sk, port = _busy()
    try:
        assert S._bind_port(port) is None
    finally:
        sk.close()
    mine = S._bind_port(port)
    assert mine is not None
    assert S._bind_port(port) is None, "una seconda copia non puo' legare la stessa porta"
    mine.close()


def test_bind_port_blocker_from_bind_port_itself():
    # su Linux due socket SO_REUSEADDR legano la stessa porta se nessuno e' in ascolto: _bind_port deve ascoltare
    blocker = S._bind_port(0)
    assert blocker is not None
    try:
        assert S._bind_port(blocker.getsockname()[1]) is None
    finally:
        blocker.close()
