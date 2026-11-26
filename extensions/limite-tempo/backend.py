"""Limite di tempo: avvisa prima e al superamento del tempo di gioco al giorno o alla settimana; se scelto, chiude il gioco.

GET  /plugin-api/limite-tempo/stato   -> limiti, tempo usato oggi e questa settimana (compresa la partita in corso),
                                         tempo rimasto oggi e ore per giorno della settimana (lunedi' = 0)
POST /plugin-api/limite-tempo/salva   {"giorno_ore", "settimana_ore", "attivo", "preavviso", "chiudi"}

Conta le sessioni del profilo attivo (play_sessions) piu' la partita in corso. Durante una partita controlla ogni
TICK secondi: avvisa PREAVVISO secondi prima del limite, al superamento e poi ogni RIPETI secondi finche' si continua.
Con «chiudi» il gioco si chiude GRAZIA secondi dopo l'avviso (il tempo di salvare), come il pulsante Chiudi dell'app.
"""

import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Body, HTTPException

TICK = 30          # secondi tra un controllo e l'altro durante una partita
RIPETI = 30 * 60   # secondi tra un avviso e il successivo oltre il limite
PREAVVISO = 10 * 60
GRAZIA = 60


def inizi(now: float) -> tuple[float, float]:
    """Mezzanotte di oggi e lunedi' di questa settimana (ora locale), come timestamp."""
    d = datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0)
    return d.timestamp(), (d - timedelta(days=d.weekday())).timestamp()


def _sessioni(user: sqlite3.Connection, now: float, corso_da: float | None) -> list[tuple[float, float]]:
    _, sett = inizi(now)
    ss = user.execute("SELECT start, seconds FROM play_sessions WHERE start + seconds >= ?", (sett,)).fetchall()
    if corso_da is not None:  # la partita in corso non e' ancora in play_sessions (si scrive a fine partita)
        ss.append((corso_da, max(0.0, now - corso_da)))
    return ss


def _somma(ss, da: float, a: float) -> float:
    """Secondi giocati tra `da` e `a`: le sessioni a cavallo contano solo per la parte dentro."""
    return sum(max(0.0, min(s + d, a) - max(s, da)) for s, d in ss)


def usato(user: sqlite3.Connection, now: float, corso_da: float | None = None) -> tuple[float, float]:
    """(secondi oggi, secondi settimana)."""
    oggi, sett = inizi(now)
    ss = _sessioni(user, now, corso_da)
    return _somma(ss, oggi, now), _somma(ss, sett, now)


def per_giorno(user: sqlite3.Connection, now: float, corso_da: float | None = None) -> list[float]:
    """Secondi giocati in ogni giorno di questa settimana, da lunedi' a domenica (i giorni futuri valgono 0)."""
    _, sett = inizi(now)
    ss = _sessioni(user, now, corso_da)
    giorni = [datetime.fromtimestamp(sett) + timedelta(days=i) for i in range(8)]
    return [_somma(ss, giorni[i].timestamp(), min(giorni[i + 1].timestamp(), now)) for i in range(7)]


def rimasto(conf: dict, oggi: float, sett: float) -> float | None:
    """Secondi che restano prima del primo limite (negativo se superato), None senza limiti."""
    r = [conf[k] * 3600 - v for k, v in (("giorno_ore", oggi), ("settimana_ore", sett)) if conf.get(k)]
    return min(r) if r else None


def superati(conf: dict, oggi: float, sett: float) -> list[str]:
    """Quali limiti sono superati: "giorno" e/o "settimana"."""
    return [k for k, v in (("giorno", oggi), ("settimana", sett)) if conf.get(f"{k}_ore") and v >= conf[f"{k}_ore"] * 3600]


def register(gs):
    run = {"stop": None, "t0": 0.0}
    lock = threading.Lock()

    def conf() -> dict:
        s = gs.settings
        return {"giorno_ore": float(s.get("giorno_ore") or 0), "settimana_ore": float(s.get("settimana_ore") or 0),
                "attivo": s.get("attivo", True) is not False, "preavviso": s.get("preavviso", True) is not False,
                "chiudi": s.get("chiudi") is True}

    def db() -> sqlite3.Connection:
        from pozzo.sync import profile_path
        return sqlite3.connect(profile_path(gs.cfg, gs.cfg.app.get("profile") or "default"))

    def avvisa(titolo: str, testo: str):
        gs.log(f"[limite-tempo] {testo}")
        try:
            from pozzo import notify
            notify.send(gs.cfg, titolo, testo)
        except Exception:  # un avviso perso non deve mai fermare niente
            pass

    def chiudi_gioco():
        launcher = getattr(getattr(getattr(gs, "app", None), "state", None), "launcher", None)
        try:
            if launcher:
                launcher.stop()
        except Exception as e:  # chiusura non riuscita: resta l'avviso
            gs.log(f"[limite-tempo] chiusura non riuscita: {e}")

    def vigila(stop: threading.Event, titolo: str, t0: float):
        ultimo, preavvisato = 0.0, False
        while not stop.is_set():
            c = conf()
            if not c["attivo"]:
                return
            try:
                u = db()
                try:
                    oggi, sett = usato(u, time.time(), t0)
                finally:
                    u.close()
            except sqlite3.Error:  # database occupato un attimo: si riprova al giro dopo
                stop.wait(TICK)
                continue
            resto = rimasto(c, oggi, sett)
            if resto is not None and 0 < resto <= PREAVVISO and c["preavviso"] and not preavvisato:
                avvisa(gs.t("n.soon.t"), gs.t("n.soon.x", min=max(1, round(resto / 60)), gioco=titolo))
                preavvisato = True
            if resto is not None and resto <= 0 and time.time() - ultimo >= RIPETI:
                ultimo = time.time()
                if c["chiudi"]:
                    avvisa(gs.t("n.over.t"), gs.t("n.closing", s=GRAZIA, gioco=titolo))
                    if not stop.wait(GRAZIA):  # se nel frattempo il gioco e' stato chiuso non serve
                        chiudi_gioco()
                    return
                avvisa(gs.t("n.over.t"), gs.t("n.over.x", gioco=titolo))
            stop.wait(TICK)

    def avviata(info: dict):
        with lock:
            if run["stop"]:
                run["stop"].set()
            if not conf()["attivo"]:
                run["stop"] = None
                return
            run["stop"], run["t0"] = threading.Event(), time.time()
            threading.Thread(target=vigila, args=(run["stop"], info.get("title") or "?", run["t0"]), daemon=True).start()

    def finita(info: dict | None = None):
        with lock:
            if run["stop"]:
                run["stop"].set()
                run["stop"] = None

    @gs.route("stato")
    def stato():
        c = conf()
        now, corso = time.time(), run["t0"] if run["stop"] else None
        u = db()
        try:
            oggi, sett = usato(u, now, corso)
            giorni = per_giorno(u, now, corso)
        finally:
            u.close()
        return {**c, "oggi": oggi, "settimana": sett, "rimasto": rimasto(c, oggi, sett), "giorni": giorni,
                "oggi_idx": datetime.fromtimestamp(now).weekday(), "superati": superati(c, oggi, sett),
                "in_corso": bool(run["stop"]), "profilo": gs.cfg.app.get("profile") or "default"}

    @gs.route("salva", methods=("POST",))
    def salva(body: dict = Body(...)):
        try:
            g, s = float(body.get("giorno_ore") or 0), float(body.get("settimana_ore") or 0)
        except (TypeError, ValueError):
            raise HTTPException(400, gs.t("err.hours"))
        if not (0 <= g <= 24) or not (0 <= s <= 168):
            raise HTTPException(400, gs.t("err.range"))
        v = {"giorno_ore": g, "settimana_ore": s, "attivo": bool(body.get("attivo", True)),
             "preavviso": bool(body.get("preavviso", True)), "chiudi": bool(body.get("chiudi", False))}
        gs.save_settings(v)
        gs.settings.update(v)
        return stato()

    gs.on("game_started", avviata)
    gs.on("game_stopped", finita)
