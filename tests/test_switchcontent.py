"""Switch: aggiornamento scelto, DLC e mod scritti nei file per gioco di Ryujinx ed Eden (pozzo/switchcontent.py).
Pacchetti finti (solo intestazione PFS0), nessun file reale.

Esegui: python tests/test_switchcontent.py
"""

import json
import struct
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pozzo import switchcontent as SC  # noqa: E402

BASE = "Gioco [0100AAAA00000000][v0].nsp"
DLC_TID = 0x0100AAAA00001001


def _nsp(path: Path, names: list[str]) -> Path:
    """PFS0 minimo: intestazione, tabella delle entry (dimensione 0) e tabella dei nomi."""
    strtab = b"".join(n.encode() + b"\0" for n in names)
    offs, pos = [], 0
    for n in names:
        offs.append(pos)
        pos += len(n.encode()) + 1
    body = b"".join(struct.pack("<QQII", 0, 0, o, 0) for o in offs)
    path.write_bytes(struct.pack("<4sIII", b"PFS0", len(names), len(strtab), 0) + body + strtab)
    return path


def _files(d: Path) -> list[Path]:
    _nsp(d / BASE, ["base.nca"])
    _nsp(d / "Gioco [0100AAAA00000800][v65536].nsp", ["u1.nca"])
    _nsp(d / "Gioco [0100AAAA00000800][v131072].nsp", ["u2.nca"])
    _nsp(d / "Gioco DLC [0100AAAA00001001].nsp", ["abc.cnmt.nca", "def.nca"])
    return sorted(d.iterdir())


def test_dlc_ncas_da_nome(d: Path):
    p = _nsp(d / "X [0100AAAA00001001].nsp", ["abc.cnmt.nca", "def.nca", "x.tik"])
    assert SC.dlc_ncas(p) == [{"path": "/def.nca", "title_id": DLC_TID}]


def test_dlc_senza_id_non_collegabile(d: Path):
    files = _files(d) + [_nsp(d / "Pack.nsp", ["a.cnmt.nca", "b.nca", "c.nca"])]
    ch = SC.choices({"switch": {"extra": [str(d / "Pack.nsp")]}})
    info = SC.gather(d / BASE, files, ch)
    pack = next(x for x in info["dlcs"] if x["path"].name == "Pack.nsp")
    assert pack["error"] and pack["enabled"] is False, pack
    ok = next(x for x in info["dlcs"] if x["path"].name != "Pack.nsp")
    assert ok["error"] == "" and ok["enabled"] is True


def test_scelta_update(d: Path):
    files = _files(d)
    assert SC.gather(d / BASE, files, SC.choices(None))["update"].name.endswith("[v131072].nsp")
    assert SC.gather(d / BASE, files, SC.choices({"switch": {"update": "none"}}))["update"] is None
    old = str(d / "Gioco [0100AAAA00000800][v65536].nsp")
    assert str(SC.gather(d / BASE, files, SC.choices({"switch": {"update": old}}))["update"]) == old
    assert SC.choices({"switch": {"update": 3, "dlc_off": "x"}}) == SC.DEFAULT, "valori non validi: default"


def test_write_ryujinx_merge(d: Path):
    files = _files(d)
    data = d / "ryu"
    gdir = data / "games" / "0100aaaa00000000"
    gdir.mkdir(parents=True)
    estranea = {"path": "Z:/altro.nsp", "dlc_nca_list": [{"path": "/z.nca", "title_id": 1, "is_enabled": True}]}
    (gdir / "dlc.json").write_text(json.dumps([estranea]), "utf-8")
    dlc = str(d / "Gioco DLC [0100AAAA00001001].nsp")
    info = SC.gather(d / BASE, files, SC.choices({"switch": {"dlc_off": [dlc]}}))
    assert SC.write_ryujinx(data, info) is True
    got = json.loads((gdir / "dlc.json").read_text("utf-8"))
    assert estranea in got, "le voci non di Pozzo restano"
    mine = next(x for x in got if x["path"] == dlc)
    assert mine["dlc_nca_list"] == [{"path": "/def.nca", "title_id": DLC_TID, "is_enabled": False}]
    up = json.loads((gdir / "updates.json").read_text("utf-8"))
    assert up["selected"].endswith("[v131072].nsp") and len(up["paths"]) == 2
    assert SC.write_ryujinx(data, info) is False, "niente da cambiare: nessuna scrittura"


def test_mods_json(d: Path):
    files = _files(d)
    data = d / "ryu"
    mod = data / "mods" / "contents" / "0100aaaa00000000" / "MiaMod"
    info = SC.gather(d / BASE, files, SC.choices(None))
    SC.write_ryujinx(data, info, mods_off=[mod])
    got = json.loads((data / "games" / "0100aaaa00000000" / "mods.json").read_text("utf-8"))
    assert got == {"mods": [{"name": "MiaMod", "path": str(mod), "enabled": False}]}, got
    SC.write_ryujinx(data, info, mods_off=[], mods_all=[mod])  # riaccesa: la voce sparisce
    got = json.loads((data / "games" / "0100aaaa00000000" / "mods.json").read_text("utf-8"))
    assert got == {"mods": []}, got


INI = r"""[UI]
theme=default
Paths\external_content_dirs\1\path=E:/old
Paths\external_content_dirs\size=1

[DisabledAddOns]
1\title_id=42
1\disabled\1\d=DLC
1\disabled\size=1
size=1
"""


def _lines(text: str) -> list[str]:
    return text.splitlines()


def test_eden_cartelle_merge(d: Path):
    files = _files(d)
    info = SC.gather(d / BASE, files, SC.choices(None))
    out = SC.eden_ini(INI, [d], info, SC.choices(None), [])
    lines = _lines(out)
    assert "theme=default" in lines
    assert r"Paths\external_content_dirs\1\path=E:/old" in lines
    assert rf"Paths\external_content_dirs\2\path={d.as_posix()}" in lines
    assert r"Paths\external_content_dirs\size=2" in lines
    assert SC.eden_ini(out, [d], info, SC.choices(None), []) == out, "seconda volta: nessun cambio"


def test_eden_disabled(d: Path):
    files = _files(d)
    ch = SC.choices({"switch": {"update": "none"}})
    lines = _lines(SC.eden_ini(INI, [d], SC.gather(d / BASE, files, ch), ch, ["MiaMod"]))
    tid = 0x0100AAAA00000000
    assert r"1\title_id=42" in lines and r"1\disabled\1\d=DLC" in lines, "l'altro gioco resta"
    assert rf"2\title_id={tid}" in lines
    assert r"2\disabled\1\d=Update" in lines and r"2\disabled\2\d=MiaMod" in lines
    assert r"2\disabled\size=2" in lines and "size=2" in lines


def test_eden_niente_da_spegnere(d: Path):
    files = _files(d)
    ch = SC.choices(None)
    out = SC.eden_ini(INI, [d], SC.gather(d / BASE, files, ch), ch, [])
    assert str(0x0100AAAA00000000) not in out and "size=1" in _lines(out)


def test_write_eden(d: Path):
    files = _files(d)
    user = d / "eden"
    ch = SC.choices(None)
    assert SC.write_eden(user, [d], SC.gather(d / BASE, files, ch), ch, []) is True
    assert "external_content_dirs" in (user / "config" / "qt-config.ini").read_text("utf-8")
    assert SC.write_eden(user, [d], SC.gather(d / BASE, files, ch), ch, []) is False


TID = 0x0100AAAA00000000


def _zip_mod(d: Path) -> Path:
    import zipfile
    z = d / "MiaMod.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("MiaMod/romfs/x.txt", "ciao")
    return z


def test_import_zip_appiattito(d: Path):
    cache = d / "cache"
    assert SC.import_mod(cache, TID, _zip_mod(d)) == "MiaMod"
    assert SC.list_mods(cache, TID) == ["MiaMod"]
    assert (SC.mods_store(cache, TID) / "MiaMod" / "romfs" / "x.txt").read_text() == "ciao"
    assert (d / "MiaMod.zip").is_file(), "l'archivio dell'utente resta dov'era"
    try:
        SC.import_mod(cache, TID, _zip_mod(d))
        raise AssertionError("nome gia' usato: deve fallire")
    except ValueError:
        pass


def test_import_senza_romfs(d: Path):
    src = d / "Strana"
    (src / "altro").mkdir(parents=True)
    (src / "altro" / "f.txt").write_text("x")
    try:
        SC.import_mod(d / "cache", TID, src)
        raise AssertionError("senza romfs/exefs/cheats deve fallire")
    except ValueError:
        pass
    assert SC.list_mods(d / "cache", TID) == []


def test_link_e_spegni(d: Path):
    cache, dest = d / "cache", d / "emu" / "load" / f"{TID:016X}"
    SC.import_mod(cache, TID, _zip_mod(d))
    (dest / "Manuale" / "romfs").mkdir(parents=True)
    assert SC.link_mods(cache, TID, dest, []) == ["MiaMod"]
    assert (dest / "MiaMod" / "romfs" / "x.txt").read_text() == "ciao"
    assert SC.link_mods(cache, TID, dest, ["MiaMod"]) == []
    assert not (dest / "MiaMod").exists() and (dest / "Manuale" / "romfs").is_dir(), "la mod a mano resta"
    assert (SC.mods_store(cache, TID) / "MiaMod" / "romfs" / "x.txt").is_file(), "spegnere non cancella la mod"
    SC.remove_mod(cache, TID, "MiaMod")
    assert SC.list_mods(cache, TID) == []


def test_link_ripiego_copia(d: Path):
    cache, dest = d / "cache", d / "emu"
    SC.import_mod(cache, TID, _zip_mod(d))
    orig = SC._make_link

    def rotto(src, dst):
        raise OSError("niente link")
    SC._make_link = rotto
    try:
        assert SC.link_mods(cache, TID, dest, []) == ["MiaMod"]
    finally:
        SC._make_link = orig
    assert (dest / "MiaMod" / SC.MARK).is_file() and (dest / "MiaMod" / "romfs" / "x.txt").is_file()
    SC.link_mods(cache, TID, dest, ["MiaMod"])
    assert not (dest / "MiaMod").exists()


def test_prepare_ryujinx(d: Path):
    files = _files(d)
    exe = d / "ryu" / "Ryujinx.exe"
    (exe.parent / "portable").mkdir(parents=True)
    exe.write_bytes(b"")
    msg = SC.prepare_launch("ryujinx", str(exe), d / "cache", d / BASE, files, [d], None, running=False)
    gdir = exe.parent / "portable" / "games" / "0100aaaa00000000"
    assert (gdir / "updates.json").is_file() and (gdir / "dlc.json").is_file()
    assert "v131072" in msg and "1 DLC" in msg, msg


def test_prepare_eden_aperto(d: Path):
    files = _files(d)
    exe = d / "eden" / "eden.exe"
    (exe.parent / "user").mkdir(parents=True)
    exe.write_bytes(b"")
    SC.import_mod(d / "cache", TID, _zip_mod(d))
    SC.prepare_launch("eden", str(exe), d / "cache", d / BASE, files, [d], None, running=True)
    assert not (exe.parent / "user" / "config" / "qt-config.ini").exists(), "Eden aperto: ini non toccato"
    assert (exe.parent / "user" / "load" / f"{TID:016X}" / "MiaMod" / "romfs").is_dir(), "le mod si collegano comunque"
    SC.prepare_launch("eden", str(exe), d / "cache", d / BASE, files, [d], None, running=False)
    assert "external_content_dirs" in (exe.parent / "user" / "config" / "qt-config.ini").read_text("utf-8")
    assert SC.prepare_launch("dolphin", str(exe), d / "cache", d / BASE, files, [d], None) == ""


def test_switch_roots_ripiego(d: Path):
    from pozzo import config as C
    from pozzo.library import launcher as L
    cfg = C.Config() if hasattr(C, "Config") else None
    if cfg is None:
        return
    cfg.roms = str(d / "non-esiste")
    game = d / "Gioco"
    game.mkdir()
    assert L.switch_roots(cfg, game) == [game], "cartelle ROM non trovate: almeno quella del gioco"


def test_descrivi_per_la_scheda(d: Path):
    files = _files(d)
    SC.import_mod(d / "cache", TID, _zip_mod(d))
    ch = SC.choices({"switch": {"mods_off": ["MiaMod"]}})
    out = SC.describe(SC.gather(d / BASE, files, ch), ch, d / "cache")
    assert out["tid"] == "0100AAAA00000000"
    assert [u["version"] for u in out["updates"]] == [131072, 65536]
    assert out["dlcs"][0]["enabled"] is True and out["dlcs"][0]["name"].startswith("Gioco DLC")
    assert out["mods"] == [{"name": "MiaMod", "enabled": False}]
    json.dumps(out)  # serializzabile


def test_valida_scelte(d: Path):
    files = _files(d)
    info = SC.gather(d / BASE, files, SC.choices(None))
    old = str(d / "Gioco [0100AAAA00000800][v65536].nsp")
    ok = SC.clean_choices({"update": old, "dlc_off": [str(files[0])], "extra": [], "mods_off": ["X"]}, info)
    assert ok["update"] == old and ok["mods_off"] == ["X"]
    for bad in ({"update": "C:/a_caso.nsp"}, {"extra": [str(d / "manca.nsp")]}, {"extra": [str(d / BASE) + ".txt"]}):
        try:
            SC.clean_choices(bad, info)
            raise AssertionError(f"doveva rifiutare {bad}")
        except ValueError:
            pass


def test_profilo_conserva_switch(d: Path):
    old = {"emulator": "eden", "switch": {"update": "none"}}
    assert SC.keep_switch(old, {"emulator": "ryujinx"}) == {"emulator": "ryujinx", "switch": {"update": "none"}}
    assert SC.keep_switch(None, {"emulator": "ryujinx"}) == {"emulator": "ryujinx"}
    assert SC.with_choices({"emulator": "eden"}, {"update": "latest"}) == {"emulator": "eden", "switch": {"update": "latest"}}


TESTS = [test_dlc_ncas_da_nome, test_dlc_senza_id_non_collegabile, test_scelta_update, test_write_ryujinx_merge,
         test_mods_json, test_eden_cartelle_merge, test_eden_disabled, test_eden_niente_da_spegnere, test_write_eden,
         test_import_zip_appiattito, test_import_senza_romfs, test_link_e_spegni, test_link_ripiego_copia,
         test_prepare_ryujinx, test_prepare_eden_aperto, test_switch_roots_ripiego,
         test_descrivi_per_la_scheda, test_valida_scelte, test_profilo_conserva_switch]

if __name__ == "__main__":
    for fn in TESTS:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
            fn(Path(t))
            print("ok ", fn.__name__)
    print("TUTTI I TEST OK")
