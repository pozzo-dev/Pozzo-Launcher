"""Costanti e funzioni che server.py e le route usano entrambi. Stanno qui perche' le route non importino
server.py (che a sua volta importa le route)."""

from __future__ import annotations

import json
import re
import threading

from .. import platforms as P
from .. import stores as STORES
from ..onexit import hard_exit

STORE_NAMES = {p.id: p.name for p in STORES.PROVIDERS}
STORE_NAMES["online"] = "Store online"
_REMOTE_SEM = threading.Semaphore(4)  # immagini remote scaricate al massimo 4 alla volta
_REMOTE_DOWN: dict[str, float] = {}  # host che non risponde -> fino a quando non si riprova (secondi)
_REMOTE_MISS: dict[str, float] = {}  # copertina della griglia non scaricabile -> fino a quando non si riprova
THUMB_WIDTHS = (200, 300, 450, 700, 1280)


def _players(v, platform: str = "") -> int:
    """Numero massimo di giocatori IN LOCALE (stesso schermo/console), 0 se sconosciuto.
    '1-4', '2', 'Up to 8'... -> il massimo. Valori da gioco online (es. 16, 64) vengono scartati:
    per i PC oltre 4 (le schede PC indicano quasi sempre i giocatori online), per le console oltre 8.
    Portatili (P.NO_SPLIT): 0, il multiplayer richiede piu' console."""
    if platform in P.NO_SPLIT:
        return 0
    n =[int(x) for x in re.findall(r"\d+", str(v or ""))]
    m = max(n) if n else 0
    if m > (4 if platform == "windows" else 8):
        return 0
    return m


def _hltb_main(v) -> float | None:
    """Ore per finire la storia (o storia + extra) da HowLongToBeat, None se sconosciuto."""
    if not v:
        return None
    try:
        h = json.loads(v) if isinstance(v, str) else v
    except ValueError:
        return None
    return h.get("main") or h.get("extra") or h.get("complete")


def _json(o) -> bytes:
    """Gli stessi byte di JSONResponse, ma le liste lunghe a blocchi: json.dumps tiene un pezzo di testo per ogni
    valore fino alla fine (~200 MB in piu' per i 26 MB delle 150.000 righe di /api/library)."""
    if isinstance(o, dict):
        return b"{" + b",".join(_json(str(k)) + b":" + _json(v) for k, v in o.items()) + b"}"
    if isinstance(o, list) and len(o) > 2000:
        return b"[" + b",".join(_json(o[i:i + 2000])[1:-1] for i in range(0, len(o), 2000)) + b"]"
    return json.dumps(o, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()


def _players_label(v, platform: str = "") -> str:
    m = _players(v, platform)
    return "" if not m else "1 (solo giocatore)" if m == 1 else f"1–{m} in locale"


def _plain(s: str) -> str:
    return re.sub(r"\[/?[a-z ]*\]", "", s)


WINDOW_FOCUS = {"fn": None}  # impostata quando l'app gira in una finestra nativa
QUIT = {"fn": None}  # chiusura ordinata (la imposta run()): finestra o server, secondo come gira l'app


def quit_app(delay: float):
    """Chiude l'app tra `delay` secondi (il tempo di rispondere alla pagina) passando dallo spegnimento ordinato."""
    def go():
        guard = threading.Timer(15, hard_exit)  # se resta appesa si esce lo stesso
        guard.daemon = True
        guard.start()
        (QUIT["fn"] or hard_exit)()
    threading.Timer(delay, go).start()
