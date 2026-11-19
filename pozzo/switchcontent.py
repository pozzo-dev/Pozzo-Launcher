"""Switch: aggiornamento, DLC e mod con cui parte un gioco, scritti nei file per gioco dell'emulatore.

Niente installazione nella NAND e niente copie: Ryujinx avviato da riga di comando non scansiona le sue cartelle
automatiche, quindi si scrivono games/<tid>/updates.json, dlc.json e mods.json (formati verificati sul sorgente di
Ryubing). Eden e Eglantine leggono invece le cartelle «contenuti esterni» di qt-config.ini (vedi write_eden).
Si tocca solo cio' che gestisce Pozzo: voci estranee e mod messe a mano restano com'erano.
"""

from __future__ import annotations

import json
import os
import sys
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


# ---------------------------------------------------------------- Eden / Eglantine (qt-config.ini)
B = "\\"  # separatore delle chiavi di QSettings
EXT = f"Paths{B}external_content_dirs{B}"  # [UI], elenco 1-based di QSettings: N\path e size


def _blocks(text: str) -> list[list]:
    out: list[list] = [[None, []]]
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            out.append([s[1:-1], [line]])
        else:
            out[-1][1].append(line)
    return out


def _unq(v: str) -> str:
    v = v.strip()
    return v[1:-1] if len(v) > 1 and v[0] == v[-1] == '"' else v


def _q(v: str) -> str:
    return f'"{v}"' if "," in v or v != v.strip() else v  # come QSettings: virgole e spazi ai bordi tra virgolette


def _section(blocks: list[list], name: str) -> list:
    b = next((b for b in blocks if b[0] == name), None)
    if b is None:
        if blocks[-1][1] and blocks[-1][1][-1].strip():
            blocks[-1][1].append("")
        b = [name, [f"[{name}]"]]
        blocks.append(b)
    return b


def _set_body(b: list, body: list[str]):
    while body and not body[-1].strip():
        body.pop()
    b[1] = [b[1][0], *body, ""]


def _disabled(body: list[str]) -> list[tuple[str, list[str]]]:
    """[DisabledAddOns] -> [(title_id, [nomi disattivati])] nell'ordine del file."""
    ent: dict[str, dict] = {}
    for line in body:
        if "=" not in line:
            continue
        k, v = (x.strip() for x in line.split("=", 1))
        p = k.split(B)
        if len(p) == 2 and p[1] == "title_id":
            ent.setdefault(p[0], {"d": {}})["tid"] = _unq(v)
        elif len(p) == 4 and p[1] == "disabled" and p[3] == "d":
            ent.setdefault(p[0], {"d": {}})["d"][int(p[2]) if p[2].isdigit() else 0] = _unq(v)
    order = sorted(ent, key=lambda n: int(n) if n.isdigit() else 0)
    return [(ent[n]["tid"], [ent[n]["d"][i] for i in sorted(ent[n]["d"])]) for n in order if ent[n].get("tid")]


def _eden_off(info: dict, ch: dict, mod_names_off: list[str]) -> list[str]:
    off = []
    if ch.get("update") == "none":
        off.append("Update")
    elif ch.get("update") not in (None, "", "latest"):
        # shortcut: «Update@<versione>» dal sorgente di Eden, non provato su Eden reale; se non va resta l'aggiornamento piu' nuovo
        off += [f"Update@{SF.version(u.name)}" for u in info["updates"] if u != info["update"]]
    if info["dlcs"] and all(str(d["path"]) in set(ch.get("dlc_off") or []) for d in info["dlcs"]):
        off.append("DLC")  # Eden accende e spegne i DLC solo tutti insieme
    return off + list(mod_names_off)


def eden_ini(text: str, roots: list[Path], info: dict, ch: dict, mod_names_off: list[str]) -> str:
    """qt-config.ini con le cartelle ROM tra i contenuti esterni e gli add-on spenti del gioco; il resto com'era."""
    blocks = _blocks(text)
    ui = _section(blocks, "UI")
    body = ui[1][1:]
    old = []
    for line in body:
        k = line.split("=", 1)[0].strip()
        if k.startswith(EXT) and k.endswith(f"{B}path") and "=" in line:
            old.append(_unq(line.split("=", 1)[1]))
    dirs = old + [r.as_posix() for r in roots if r.as_posix() not in old]
    if dirs != old:
        keep = [x for x in body if not x.split("=", 1)[0].strip().startswith(EXT)]
        while keep and not keep[-1].strip():
            keep.pop()
        _set_body(ui, [*keep, *(f"{EXT}{i}{B}path={_q(v)}" for i, v in enumerate(dirs, 1)), f"{EXT}size={len(dirs)}"])

    if info.get("tid") is not None:
        tid = str(info["tid"])
        b = next((b for b in blocks if b[0] == "DisabledAddOns"), None)
        cur = _disabled(b[1][1:]) if b else []
        want = _eden_off(info, ch, mod_names_off)
        if dict(cur).get(tid, []) != want:
            new = [(t, ds) for t, ds in cur if t != tid] + ([(tid, want)] if want else [])
            b = b or _section(blocks, "DisabledAddOns")
            lines = []
            for i, (t, ds) in enumerate(new, 1):
                lines += [f"{i}{B}title_id={t}", f"{i}{B}title_id{B}default=false"]
                for j, dname in enumerate(ds, 1):
                    lines += [f"{i}{B}disabled{B}{j}{B}d={_q(dname)}", f"{i}{B}disabled{B}{j}{B}d{B}default=false"]
                lines.append(f"{i}{B}disabled{B}size={len(ds)}")
            _set_body(b, [*lines, f"size={len(new)}"])
    out = "\n".join(line for blk in blocks for line in blk[1])
    return out if out.endswith("\n") or not out else out + "\n"


def write_eden(user_dir: Path, roots: list[Path], info: dict, ch: dict, mod_names_off: list[str]) -> bool:
    """Scrive config/qt-config.ini di Eden (cartella utente) solo se cambia. Da chiamare a Eden chiuso."""
    f = Path(user_dir) / "config" / "qt-config.ini"
    try:
        cur = f.read_text("utf-8")
    except OSError:
        cur = ""
    new = eden_ini(cur, roots, info, ch, mod_names_off)
    if new == cur:
        return False
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(new, "utf-8")
    return True


# ---------------------------------------------------------------- mod (romfs/exefs/cheats per Title ID)
MOD_DIRS = {"romfs", "exefs", "cheats"}
MARK = ".pozzo"  # file nelle copie fatte da Pozzo quando il collegamento non si puo' creare: solo quelle si tolgono


def mods_store(cache: Path, tid: int) -> Path:
    return Path(cache) / "mods" / "switch" / f"{tid:016X}"


def list_mods(cache: Path, tid: int) -> list[str]:
    d = mods_store(cache, tid)
    return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.is_dir() else []


def _mod_root(folder: Path) -> Path | None:
    """La cartella che contiene romfs/exefs/cheats: quella data o la sua unica sottocartella."""
    def has(p: Path) -> bool:
        return any(c.is_dir() and c.name.lower() in MOD_DIRS for c in p.iterdir())
    if has(folder):
        return folder
    subs = [p for p in folder.iterdir() if p.is_dir()]
    return subs[0] if len(subs) == 1 and has(subs[0]) else None


def import_mod(cache: Path, tid: int, src: Path, name: str = "") -> str:
    """Mette una mod (archivio zip/7z/rar o cartella) nell'archivio di Pozzo per questo gioco. Ritorna il nome."""
    import re
    import shutil
    import tempfile
    from . import mods as M
    src = Path(src)
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", name or (src.name if src.is_dir() else src.stem)).strip(" .")
    if not name:
        raise ValueError("nome della mod non valido")
    dest = mods_store(cache, tid) / name
    if dest.exists():
        raise ValueError(f"esiste gia' una mod chiamata {name}")
    with tempfile.TemporaryDirectory(dir=str(Path(cache))) if Path(cache).is_dir() else tempfile.TemporaryDirectory() as t:
        work = Path(t) / "mod"
        if src.is_dir():
            shutil.copytree(src, work)
        else:
            arc = Path(t) / src.name  # copia: extract_files rinomina l'archivio e quello dell'utente non si tocca
            shutil.copy2(src, arc)
            work.mkdir()
            M.extract_files(arc, work)
        root = _mod_root(work)
        if root is None:
            raise ValueError("la mod non contiene romfs, exefs o cheats")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(root), str(dest))
    return name


def _is_link(p: Path) -> bool:
    return p.is_symlink() or bool(getattr(os.path, "isjunction", lambda _: False)(p))


def _make_link(src: Path, dst: Path):
    if sys.platform == "win32":
        import _winapi  # junction: niente permessi di amministratore, a differenza dei symlink
        _winapi.CreateJunction(str(src), str(dst))
    else:
        dst.symlink_to(src, target_is_directory=True)


def _unlink(p: Path):
    import shutil
    if _is_link(p):
        p.unlink() if p.is_symlink() else os.rmdir(p)
    elif (p / MARK).is_file():
        shutil.rmtree(p)


def link_mods(cache: Path, tid: int, dest: Path, off: list[str]) -> list[str]:
    """Collega le mod accese di Pozzo nella cartella mod dell'emulatore (dest) e toglie le spente.
    Le cartelle messe dall'utente (ne' collegamento ne' copia di Pozzo) non si toccano. Ritorna le mod collegate."""
    import shutil
    dest = Path(dest)
    done = []
    for name in list_mods(cache, tid):
        src, dst = mods_store(cache, tid) / name, dest / name
        if name in off:
            if dst.exists() or _is_link(dst):
                _unlink(dst)
            continue
        if _is_link(dst) or (dst / MARK).is_file():
            done.append(name)
            continue
        if dst.exists():
            continue  # una mod dell'utente con lo stesso nome: vince la sua
        dest.mkdir(parents=True, exist_ok=True)
        try:
            _make_link(src, dst)
        except OSError:
            shutil.copytree(src, dst)  # disco che non accetta collegamenti (es. FAT32)
            (dst / MARK).write_text("copia di Pozzo Launcher\n", "utf-8")
        done.append(name)
    return done


def remove_mod(cache: Path, tid: int, name: str, dests: list[Path] = ()):
    """Toglie la mod dall'archivio di Pozzo e i suoi collegamenti/copie nelle cartelle degli emulatori."""
    import shutil
    if name not in list_mods(cache, tid):
        raise ValueError(f"mod sconosciuta: {name}")
    for d in dests:
        p = Path(d) / name
        if p.exists() or _is_link(p):
            _unlink(p)
    shutil.rmtree(mods_store(cache, tid) / name)
