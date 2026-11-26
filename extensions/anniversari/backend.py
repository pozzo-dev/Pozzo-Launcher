"""Anniversari retro: i giochi della libreria che compiono gli anni oggi e nei prossimi giorni.

GET /plugin-api/anniversari/oggi[?giorno=MM-GG]          -> {"giorno": "06-23", "anno": 2026, "giochi": [{id, titolo, piattaforma, anni}]}
GET /plugin-api/anniversari/prossimi[?giorni=30&da=AAAA-MM-GG]
    -> {"da": "2026-06-23", "giorni": [{"data": "2026-06-24", "tra": 1, "giochi": [{id, titolo, piattaforma, anni, tondo}]}]}
"""

import sqlite3
from datetime import date
from pathlib import Path

from fastapi import HTTPException

PER_GIORNO = 24  # librerie enormi: per ogni giorno i compleanni tondi e piu' vecchi, non migliaia di copertine


def anniversari(db: sqlite3.Connection, mese_giorno: str, anno: int) -> list[dict]:
    """Giochi con release_date AAAA-MM-GG uguale a oggi (mese-giorno), usciti in un anno precedente."""
    out = []
    for gid, title, plat, store, rel in db.execute(
            "SELECT id, title, platform, store, release_date FROM games "
            "WHERE is_primary=1 AND release_date LIKE ? AND COALESCE(store,'') != 'online'", (f"____-{mese_giorno}",)):
        anni = anno - int(rel[:4])
        if anni > 0:
            out.append({"id": gid, "titolo": title, "piattaforma": store or plat, "anni": anni})
    out.sort(key=lambda g: (-g["anni"], g["titolo"].lower()))
    return out


def prossimi(db: sqlite3.Connection, da: date, giorni: int) -> list[dict]:
    """Compleanni da `da` (compreso) per `giorni` giorni, raggruppati per data. Il 29 febbraio solo negli anni bisestili."""
    per_data: dict[date, list[dict]] = {}
    for gid, title, plat, store, rel in db.execute(
            "SELECT id, title, platform, store, release_date FROM games "
            "WHERE is_primary=1 AND release_date LIKE '____-__-__' AND COALESCE(store,'') != 'online'"):
        try:
            y, m, d = int(rel[:4]), int(rel[5:7]), int(rel[8:10])
            quando = date(da.year, m, d)
            if quando < da:
                quando = date(da.year + 1, m, d)
        except ValueError:  # data scritta male, o 29/02 in un anno che non lo ha
            continue
        anni = quando.year - y
        if (quando - da).days < giorni and anni > 0:
            per_data.setdefault(quando, []).append({"id": gid, "titolo": title, "piattaforma": store or plat,
                                                    "anni": anni, "tondo": anni % 5 == 0})
    out = []
    for quando in sorted(per_data):
        giochi = sorted(per_data[quando], key=lambda g: (not g["tondo"], -g["anni"], g["titolo"].lower()))
        out.append({"data": quando.isoformat(), "tra": (quando - da).days, "totale": len(giochi), "giochi": giochi[:PER_GIORNO]})
    return out


def register(gs):
    db_path = Path(gs.cfg.cache) / "library.db"

    def con():
        return sqlite3.connect(db_path) if db_path.exists() else None

    @gs.route("oggi")
    def oggi(giorno: str = ""):
        today = date.today()
        md = giorno or today.strftime("%m-%d")
        if len(md) != 5 or md[2] != "-" or not (md[:2] + md[3:]).isdigit():
            raise HTTPException(400, gs.t("err.giorno"))
        db = con()
        if db is None:
            return {"giorno": md, "anno": today.year, "giochi": []}
        try:
            return {"giorno": md, "anno": today.year, "giochi": anniversari(db, md, today.year)}
        finally:
            db.close()

    @gs.route("prossimi")
    def prossimi_route(giorni: int = 30, da: str = ""):
        try:
            inizio = date.fromisoformat(da) if da else date.today()
        except ValueError:
            raise HTTPException(400, gs.t("err.data"))
        giorni = max(1, min(int(giorni), 366))
        db = con()
        if db is None:
            return {"da": inizio.isoformat(), "giorni": []}
        try:
            return {"da": inizio.isoformat(), "giorni": prossimi(db, inizio, giorni)}
        finally:
            db.close()
