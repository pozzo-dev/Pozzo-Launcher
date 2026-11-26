"""Obiettivi personali: obiettivi a periodo, sfide proposte dalla libreria, serie di giorni e distintivi (profilo attivo).

GET  /plugin-api/obiettivi/stato     -> {"obiettivi": [...con avanzamento], "proposte": [...], "serie": {attuale, migliore}, "distintivi": [...]}
POST /plugin-api/obiettivi/salva     {"obiettivi": [...]}  ogni voce:
     {"tipo": "finiti"|"ore"|"giorni", "n": 3, "periodo": "settimana"|"mese"|"anno"}   conteggio nel periodo
     {"tipo": "finisci", "gioco": <key>}      sfida: finire quel gioco (stato «Finito» dopo averla accettata)
     {"tipo": "prova", "console": <id>}       sfida: giocare per la prima volta a una console della libreria

«Finiti» conta i giochi (non le versioni) il cui stato e' «Finito», cambiato nel periodo: la data e' l'ultima modifica
dello stato (sync_times), quindi un gioco ritoccato dopo averlo finito conta dal ritocco.
I testi (etichette, distintivi) li scrive l'interfaccia nella sua lingua: qui solo tipi e numeri.
"""

import sqlite3
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import Body, HTTPException

TIPI = ("finiti", "ore", "giorni")
SFIDE = ("finisci", "prova")
PERIODI = ("settimana", "mese", "anno")
MAX_OBIETTIVI = 20


def inizio(periodo: str, now: float) -> float:
    d = datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0)
    if periodo == "settimana":
        d -= timedelta(days=d.weekday())
    elif periodo == "mese":
        d = d.replace(day=1)
    else:
        d = d.replace(month=1, day=1)
    return d.timestamp()


def giorni_di_gioco(sessions: list[tuple[float, float]]) -> set[date]:
    """Giorni (ora locale) in cui c'e' stata almeno una partita; una sessione a cavallo della mezzanotte conta per entrambi."""
    out = set()
    for s, d in sessions:
        a, b = datetime.fromtimestamp(s).date(), datetime.fromtimestamp(s + max(d, 0)).date()
        while a <= b:
            out.add(a)
            a += timedelta(days=1)
    return out


def serie(giorni: set[date], oggi: date) -> tuple[int, int]:
    """(serie in corso, serie migliore). Quella in corso vale anche se oggi non si e' ancora giocato ma ieri si'."""
    best = run = 0
    prev = None
    for g in sorted(giorni):
        run = run + 1 if prev and (g - prev).days == 1 else 1
        best, prev = max(best, run), g
    cur, g = 0, oggi if oggi in giorni else oggi - timedelta(days=1)
    while g in giorni:
        cur, g = cur + 1, g - timedelta(days=1)
    return cur, best


def avanzamento(ob: dict, sessions, finiti: list[tuple[str, float]], now: float, d: dict | None = None) -> float:
    """sessions = [(start, seconds)]; per le sfide d = {"grp": key->gruppo, "plat": key->console, "sess": [(key, start, s)]}."""
    if ob["tipo"] == "finisci":
        g = (d or {}).get("grp", {}).get(ob["gioco"], ob["gioco"])
        return 1.0 if any(x == g and t >= ob.get("creato", 0) for x, t in finiti) else 0.0
    if ob["tipo"] == "prova":
        plat = (d or {}).get("plat", {})
        # conta una partita finita dopo aver accettato la sfida (anche se era cominciata prima)
        return 1.0 if any(plat.get(k) == ob["console"] and s + x >= ob.get("creato", 0) for k, s, x in (d or {}).get("sess", [])) else 0.0
    da = inizio(ob["periodo"], now)
    if ob["tipo"] == "finiti":
        return len({g for g, t in finiti if t >= da})
    if ob["tipo"] == "ore":
        return sum(max(0.0, min(s + dd, now) - max(s, da)) for s, dd in sessions) / 3600
    return len({g for g in giorni_di_gioco([x for x in sessions if x[0] + x[1] >= da]) if g >= datetime.fromtimestamp(da).date()})


def proposte(in_corso: list[tuple[str, str, int]], console_mai: list[tuple[str, int]], attivi: list[dict]) -> list[dict]:
    """Sfide da accettare con un clic: giochi «In corso» da finire, una console mai giocata, 5 giorni a settimana.
    in_corso = [(key, titolo, id)] dal piu' recente; console_mai = [(console, quanti giochi)] dalla piu' fornita."""
    gia = {(o["tipo"], o.get("gioco") or o.get("console") or o.get("periodo")) for o in attivi}
    out = [{"tipo": "finisci", "gioco": k, "titolo": t, "id_gioco": i} for k, t, i in in_corso if ("finisci", k) not in gia][:2]
    out += [{"tipo": "prova", "console": c, "giochi": n} for c, n in console_mai if ("prova", c) not in gia][:1]
    if ("giorni", "settimana") not in gia:
        out.append({"tipo": "giorni", "n": 5, "periodo": "settimana"})
    return out


DISTINTIVI = [  # (id, misura, soglia): titoli e descrizioni nei testi dell'estensione (badge.<id>.t / .x)
    ("f1", "finiti", 1), ("f10", "finiti", 10), ("f50", "finiti", 50),
    ("o100", "ore", 100), ("o1000", "ore", 1000),
    ("s7", "serie", 7), ("s30", "serie", 30),
]


def register(gs):
    cache = Path(gs.cfg.cache)

    def conn():
        from pozzo.sync import profile_path
        return sqlite3.connect(cache / "library.db"), sqlite3.connect(profile_path(gs.cfg, gs.cfg.app.get("profile") or "default"))

    def dati(lib, user):
        info = {k: (g, plat, store) for k, g, plat, store in lib.execute("SELECT key, grp, platform, store FROM games")}
        grp = {k: v[0] for k, v in info.items()}
        sess = user.execute("SELECT key, start, seconds FROM play_sessions").fetchall()
        # «Finito» e quando: l'ora dell'ultima modifica dello stato per le chiavi che oggi sono «done»
        finiti = [(grp.get(k, k), t) for k, t in user.execute(
            "SELECT s.id, s.t FROM sync_times s JOIN user_games u ON u.key = s.id "
            "WHERE s.tbl='game' AND s.field='status' AND u.status='done'")]
        tot_finiti = len({grp.get(k, k) for (k,) in user.execute("SELECT key FROM user_games WHERE status='done'")})
        # per le proposte: giochi «In corso» (il piu' recente prima) e console della libreria mai giocate
        in_corso = []
        for k, in user.execute("SELECT key FROM user_games WHERE status='playing' ORDER BY last_played DESC LIMIT 20"):
            row = lib.execute("SELECT key, title, id FROM games WHERE grp=? ORDER BY is_primary DESC LIMIT 1", (grp.get(k, k),)).fetchone()
            if row and row[0] not in {x[0] for x in in_corso}:
                in_corso.append(row)
        giocate = {info[k][1] for k, _, _ in sess if k in info}
        console_mai = [(p, n) for p, n in lib.execute(
            "SELECT platform, COUNT(*) FROM games WHERE is_primary=1 AND store IS NULL GROUP BY platform ORDER BY 2 DESC")
            if p not in giocate]
        d = {"grp": grp, "plat": {k: v[1] for k, v in info.items()}, "sess": sess}
        return [(s, x) for _, s, x in sess], finiti, tot_finiti, d, in_corso, console_mai

    def lista() -> list[dict]:
        return [o for o in (gs.settings.get("obiettivi") or [])
                if (o.get("tipo") in TIPI and o.get("periodo") in PERIODI) or o.get("tipo") in SFIDE]

    @gs.route("stato")
    def stato():
        lib, user = conn()
        try:
            sessions, finiti, tot_finiti, d, in_corso, console_mai = dati(lib, user)
            titoli = {}  # titolo e id dei giochi delle sfide «finisci» (pochi: una query l'uno)
            for o in lista():
                if o["tipo"] == "finisci":
                    row = lib.execute("SELECT title, id FROM games WHERE key=?", (o["gioco"],)).fetchone()
                    titoli[o["gioco"]] = {"titolo": row[0], "id_gioco": row[1]} if row else {"titolo": o["gioco"]}
        finally:
            lib.close()
            user.close()
        now = time.time()
        cur, best = serie(giorni_di_gioco(sessions), date.today())
        misure = {"finiti": tot_finiti, "ore": sum(x for _, x in sessions) / 3600, "serie": best}
        obs = []
        for o in lista():
            v = avanzamento(o, sessions, finiti, now, d)
            n = o.get("n", 1)
            obs.append({**o, "n": n, "valore": round(v, 1), "fatto": v >= n, **titoli.get(o.get("gioco"), {})})
        return {"obiettivi": obs, "proposte": proposte(in_corso, console_mai, lista()), "serie": {"attuale": cur, "migliore": best},
                "distintivi": [{"id": i, "misura": m, "ottenuto": misure[m] >= n, "valore": round(min(misure[m], n), 1), "soglia": n}
                               for i, m, n in DISTINTIVI]}

    @gs.route("salva", methods=("POST",))
    def salva(body: dict = Body(...)):
        vecchi = {o.get("id"): o for o in lista()}
        out = []
        for o in body.get("obiettivi") or []:
            oid = str(o.get("id") or uuid.uuid4().hex[:8])
            creato = (vecchi.get(oid) or {}).get("creato") or time.time()  # le sfide contano da quando le accetti
            if o.get("tipo") == "finisci" and isinstance(o.get("gioco"), str) and o["gioco"]:
                out.append({"id": oid, "tipo": "finisci", "gioco": o["gioco"], "creato": creato})
                continue
            if o.get("tipo") == "prova" and isinstance(o.get("console"), str) and o["console"]:
                out.append({"id": oid, "tipo": "prova", "console": o["console"], "creato": creato})
                continue
            try:
                n = float(o.get("n"))
            except (TypeError, ValueError):
                raise HTTPException(400, gs.t("err.n"))
            if o.get("tipo") not in TIPI or o.get("periodo") not in PERIODI or not (0 < n <= 10000):
                raise HTTPException(400, gs.t("err.goal"))
            out.append({"id": oid, "tipo": o["tipo"], "periodo": o["periodo"], "n": int(n) if n == int(n) else n})
        if len(out) > MAX_OBIETTIVI:
            raise HTTPException(400, gs.t("err.max", n=MAX_OBIETTIVI))
        gs.save_settings({"obiettivi": out})
        gs.settings["obiettivi"] = out
        return stato()
