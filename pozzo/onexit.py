"""Ripristini da fare in uscita (gioco sospeso, controller nascosto, stanze aperte). Come atexit, ma girano anche quando
l'app esce con os._exit, che atexit non lo esegue."""

from __future__ import annotations

import atexit
import os
import threading

_FNS: list = []
MAX_WAIT = 10  # secondi per tutti i ripristini: l'uscita non deve restare appesa


def register(fn):
    _FNS.append(fn)
    atexit.register(fn)  # uscita normale (Ctrl+C, riga di comando): le funzioni sono idempotenti


def _run():
    for fn in reversed(list(_FNS)):
        try:
            fn()
        except Exception:  # noqa: BLE001 - si provano comunque gli altri
            pass


def hard_exit():
    """os._exit dopo i ripristini."""
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(MAX_WAIT)
    os._exit(0)
