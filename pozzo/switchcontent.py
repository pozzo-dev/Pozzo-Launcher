"""Switch: aggiornamento, DLC e mod con cui parte un gioco, scritti nei file per gioco dell'emulatore.

Niente installazione nella NAND e niente copie: Ryujinx avviato da riga di comando non scansiona le sue cartelle
automatiche, quindi si scrivono games/<tid>/updates.json, dlc.json e mods.json (formati verificati sul sorgente di
Ryubing). Eden e Eglantine leggono invece le cartelle «contenuti esterni» di qt-config.ini (vedi write_eden).
Si tocca solo cio' che gestisce Pozzo: voci estranee e mod messe a mano restano com'erano.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import switchfiles as SF
from .switchmeta import SwitchError

DEFAULT = {"update": "latest", "dlc_off": [], "extra": [], "mods_off": []}


def choices(profile: dict | None) -> dict:
    """Scelte del gioco (profilo di avvio, chiave «switch») con i valori non validi riportati al default."""
    raw = (profile or {}).get("switch") or {}
    out = {k: (list(v) if isinstance(v, list) else v) for k, v in DEFAULT.items()}
    if isinstance(raw.get("update"), str) and raw["update"]:
        out["update"] = raw["update"]
    for k in ("dlc_off", "extra", "mods_off"):
        v = raw.get(k)
        if isinstance(v, list) and all(isinstance(x, str) for x in v):
            out[k] = list(v)
    return out


def dlc_ncas(path: Path, keys: dict | None = None) -> list[dict]:
    """NCA di contenuto di un DLC dentro l'NSP, come le vuole dlc.json di Ryujinx: [{"path": "/x.nca", "title_id"}].
    L'intestazione PFS0 e' in chiaro; il Title ID viene dal nome del file, o dal CNMT se ci sono le chiavi."""
    from . import switchmeta as SM
    if path.suffix.lower() in (".xci", ".xcz"):
        raise SwitchError("xci")  # Ryujinx carica i DLC solo da NSP
    with open(path, "rb") as f:
        entries = SM._package_files(f)
    data = [n for n, _, _ in entries if n.lower().endswith(".nca") and not n.lower().endswith(".cnmt.nca")]
    if len(data) != 1:
        raise SwitchError("ambiguo")  # shortcut: piu' DLC in un NSP solo; servirebbe la tabella contenuti del CNMT
    tid = SF.tid(path.name)
    if tid is None and keys:
        cn = [c for c in SM._package_cnmts(path, keys) if c.get("type") == "dlc"]
        tid = cn[0]["title_id"] if len(cn) == 1 else None
    if tid is None:
        raise SwitchError("prod.keys")
    return [{"path": "/" + data[0], "title_id": tid}]


def gather(base: Path, siblings: list[Path], ch: dict, keys: dict | None = None) -> dict:
    """Aggiornamenti (il piu' nuovo prima), aggiornamento scelto e DLC del gioco, con lo stato di ciascuno."""
    extra = [Path(x) for x in ch.get("extra") or [] if Path(x).is_file()]
    files = list(dict.fromkeys([*siblings, *extra]))
    ups, dlcs = SF.companions(base, files)
    # aggiunti a mano senza Title ID nel nome: per l'utente sono DLC di questo gioco
    dlcs += [p for p in extra if p not in dlcs and p not in ups and p != base]
    want = ch.get("update") or "latest"
    update = None if want == "none" else ups[0] if ups and want == "latest" else next(
        (u for u in ups if str(u) == want), ups[0] if ups else None)
    off = set(ch.get("dlc_off") or [])
    items = []
    for p in dlcs:
        try:
            ncas, err = dlc_ncas(p, keys), ""
        except (OSError, SwitchError) as e:
            ncas, err = [], str(e) or type(e).__name__
        items.append({"path": p, "ncas": ncas, "enabled": not err and str(p) not in off, "error": err})
    return {"tid": SF.family(base.name), "updates": ups, "update": update, "dlcs": items}


def _game_dir(data_dir: Path, tid: int) -> Path:
    return Path(data_dir) / "games" / f"{tid:016x}"


def _load(f: Path, default):
    try:
        return json.loads(f.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _save(f: Path, cur, new) -> bool:
    if cur == new:
        return False
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(new, indent=2), "utf-8")
    return True


def write_ryujinx(data_dir: Path, info: dict, mods_off: list[Path] = (), mods_all: list[Path] = ()) -> bool:
    """updates.json, dlc.json e mods.json del gioco. mods_all: tutte le mod collegate da Pozzo (accese e spente),
    per togliere la voce di quelle riaccese. True se ha scritto qualcosa."""
    if info.get("tid") is None:
        return False
    gdir = _game_dir(data_dir, info["tid"])
    wrote = False

    cur = _load(gdir / "updates.json", {})
    cur = cur if isinstance(cur, dict) else {}
    paths = [p for p in cur.get("paths") or [] if isinstance(p, str)]
    paths += [str(u) for u in info["updates"] if str(u) not in paths]
    if info["updates"] or cur:
        new = {"selected": str(info["update"]) if info["update"] else "", "paths": paths}
        wrote |= _save(gdir / "updates.json", cur, new)

    cur = _load(gdir / "dlc.json", [])
    cur = cur if isinstance(cur, list) else []
    mine = {str(d["path"]) for d in info["dlcs"]}
    new = [x for x in cur if not (isinstance(x, dict) and x.get("path") in mine)]
    new += [{"path": str(d["path"]), "dlc_nca_list": [{**n, "is_enabled": d["enabled"]} for n in d["ncas"]]}
            for d in info["dlcs"] if d["ncas"]]
    if cur or new:
        wrote |= _save(gdir / "dlc.json", cur, new)

    cur = _load(gdir / "mods.json", {})
    cur = cur if isinstance(cur, dict) else {}
    off = {str(Path(m)) for m in mods_off}
    managed = off | {str(Path(m)) for m in mods_all}
    # le voci delle mod di Pozzo si rifanno; le altre (spente dall'utente nella GUI) restano
    rest = [m for m in cur.get("mods") or [] if isinstance(m, dict) and m.get("path") not in managed]
    new_mods = rest + [{"name": Path(m).name, "path": m, "enabled": False} for m in sorted(off)]
    if cur or new_mods:
        wrote |= _save(gdir / "mods.json", cur, {**cur, "mods": new_mods})
    return wrote
