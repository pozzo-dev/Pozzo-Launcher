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


TESTS = [test_dlc_ncas_da_nome, test_dlc_senza_id_non_collegabile, test_scelta_update, test_write_ryujinx_merge,
         test_mods_json]

if __name__ == "__main__":
    for fn in TESTS:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
            fn(Path(t))
            print("ok ", fn.__name__)
    print("TUTTI I TEST OK")
