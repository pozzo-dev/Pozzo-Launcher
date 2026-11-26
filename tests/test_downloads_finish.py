"""Dopo il download: estrazione, cartella ROM giusta, libreria, pulizia. Nessuna rete."""

import sys
import threading
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pozzo.downloads import finish  # noqa: E402
from pozzo.downloads.task import COMPLETED, DownloadTask  # noqa: E402
from test_downloads_ingest import make_cfg, make_ctx  # noqa: E402


class Mgr:
    def __init__(self, **s):
        self._s = {"auto_extract": True, "delete_archive": True, **s}
        self.store = SimpleNamespace(save=lambda tasks: None)
        self.lock = threading.Lock()

    def save(self, t):
        self.store.save([t])

    def settings(self):
        return self._s

    def _poke(self):
        pass


def _task(tmp, name, **opts):
    dl = tmp / "dl"
    dl.mkdir(exist_ok=True)
    return DownloadTask(source="https://x/" + name, save_path=str(dl), name=name, status=COMPLETED,
                        options={"game_id": 7, **opts})


def _ctx(tmp):
    cfg = make_cfg(tmp)
    ctx, calls, got = make_ctx(cfg, online={"id": 7, "title": "Gioco", "key": "online/7", "platform": "switch",
                                            "store": "online", "files": []})
    return ctx, calls, got, cfg


def test_zip_estratto_e_messo_nella_cartella_rom(tmp):
    ctx, calls, got, cfg = _ctx(tmp)
    z = tmp / "dl" / "Gioco.zip"
    z.parent.mkdir()
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("Gioco/Gioco [0100AAAA].xci", b"x" * 50)
        f.writestr("Gioco/leggimi.txt", "ciao")
    t = _task(tmp, "Gioco.zip")
    finish.run(t, Mgr(), ctx)
    placed = list((cfg.roms).rglob("*.xci"))
    assert len(placed) == 1, [str(p) for p in cfg.roms.rglob("*")]
    assert calls == [{"platforms": ["switch"]}] and got, (calls, got)
    assert not z.exists()  # archivio tolto a gioco messo a posto
    assert t.options["post_done"] and any("Nella libreria" in l["msg"] for l in t.log_after(0)[0])
    assert Path(t.options["placed"]) == placed[0], "«Apri cartella» porta al gioco, non all'archivio cancellato"


def test_senza_estrazione_automatica_non_tocca_l_archivio(tmp):
    ctx, calls, got, cfg = _ctx(tmp)
    z = tmp / "dl" / "Gioco.zip"
    z.parent.mkdir()
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("Gioco.xci", b"x")
    finish.run(_task(tmp, "Gioco.zip"), Mgr(auto_extract=False), ctx)
    assert z.exists() and not list(cfg.roms.rglob("*.xci")) and not calls


def test_file_di_gioco_gia_scaricato_va_in_libreria(tmp):
    ctx, calls, got, cfg = _ctx(tmp)
    (tmp / "dl").mkdir()
    (tmp / "dl" / "Gioco.xci").write_bytes(b"x" * 20)
    finish.run(_task(tmp, "Gioco.xci"), Mgr(), ctx)
    assert len(list(cfg.roms.rglob("*.xci"))) == 1 and calls


def test_volumi_mancanti_aspetta(tmp):
    ctx, calls, got, cfg = _ctx(tmp)
    (tmp / "dl").mkdir()
    (tmp / "dl" / "g.part1.rar").write_bytes(b"x")
    (tmp / "dl" / "g.part3.rar").write_bytes(b"x")  # manca il 2
    t = _task(tmp, "g.part1.rar")
    finish.run(t, Mgr(), ctx)
    assert any("Mancano" in l["msg"] for l in t.log_after(0)[0]) and not calls
    assert (tmp / "dl" / "g.part1.rar").exists()


def test_senza_gioco_estrae_e_basta(tmp):
    ctx, calls, got, cfg = _ctx(tmp)
    z = tmp / "dl" / "x.zip"
    z.parent.mkdir()
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("a.txt", "ciao")
    t = _task(tmp, "x.zip")
    t.options.pop("game_id")
    finish.run(t, Mgr(), ctx)
    assert (tmp / "dl" / "x" / "a.txt").exists() and not calls and z.exists()


def test_passi_in_libreria_nel_log_con_secondi_e_attesa_breve(tmp, monkeypatch):
    ctx, calls, got, cfg = _ctx(tmp)
    ctx.api_scan_start = lambda body: {}  # la libreria non si aggiorna mai
    real, phases = finish.I.ingest, []
    monkeypatch.setattr(finish.I, "ingest", lambda *a, **k: real(*a, **{**k, "timeout": 0.05, "poll": 0.01}))
    (tmp / "dl").mkdir()
    (tmp / "dl" / "Gioco.xci").write_bytes(b"x" * 20)
    t = _task(tmp, "Gioco.xci")
    mgr = Mgr()
    mgr._poke = lambda: phases.append(t.phase)
    finish.run(t, mgr, ctx)
    msgs = [(l["level"], l["msg"]) for l in t.log_after(0)[0]]
    assert any(m.startswith("Aggiungo alla libreria: scansione") and m.endswith(" s)") for _, m in msgs), msgs
    assert any(l == "warn" and "prossima scansione" in m for l, m in msgs), msgs
    assert any(p.startswith("Aggiungo alla libreria") for p in phases) and t.phase == "" and t.options["post_done"]


def test_ripresa_dopo_chiusura_non_riestrae_e_toglie_gli_avanzi(tmp, monkeypatch):
    """Launcher chiuso a meta' del post-download: gli archivi gia' estratti non si rifanno, gli altri si'."""
    ctx, calls, got, cfg = _ctx(tmp)
    dl = tmp / "dl"
    (dl / "Gioco").mkdir(parents=True)
    (dl / "Gioco" / "Gioco [0100AAAA].xci").write_bytes(b"x" * 50)  # estratto prima della chiusura
    (dl / "Gioco.zip").write_bytes(b"non serve aprirlo")
    monkeypatch.setattr(finish.X, "extract", lambda *a, **k: pytest.fail("non deve estrarre di nuovo"))
    t = _task(tmp, "Gioco.zip", steps={"extract": "done", "library": "active"},
              extracted={str(dl / "Gioco.zip"): str(dl / "Gioco")})
    finish.run(t, Mgr(), ctx)
    assert len(list(cfg.roms.rglob("*.xci"))) == 1 and calls
    assert (t.options["steps"]["extract"], t.options["steps"]["library"]) == ("done", "done") and t.options["post_done"]


def test_estrazione_interrotta_riparte_e_pulisce_la_cartella_d_appoggio(tmp):
    ctx, calls, got, cfg = _ctx(tmp)
    dl = tmp / "dl"
    (dl / ".estrazione-vecchia" / "Gioco").mkdir(parents=True)  # avanzo dell'estrazione interrotta
    with zipfile.ZipFile(dl / "Gioco.zip", "w") as f:
        f.writestr("Gioco/Gioco [0100AAAA].xci", b"x" * 50)
    saved = []
    mgr = Mgr()
    mgr.store.save = lambda tasks: saved.append(dict(tasks[0].options["steps"]))
    t = _task(tmp, "Gioco.zip", steps={"extract": "active"})
    finish.run(t, mgr, ctx)
    assert not (dl / ".estrazione-vecchia").exists() and len(list(cfg.roms.rglob("*.xci"))) == 1
    assert {"extract": "active"} in saved and any(x.get("extract") == "done" and x.get("library") == "active" for x in saved)  # ogni passo va su disco
    assert (t.options["steps"]["extract"], t.options["steps"]["library"]) == ("done", "done")


def _unlinked(tmp, name, member):
    ctx, calls, got, cfg = _ctx(tmp)
    z = tmp / "dl" / name
    z.parent.mkdir()
    with zipfile.ZipFile(z, "w") as f:
        f.writestr(member, b"x" * 50)
    t = _task(tmp, name)
    t.options.pop("game_id")
    finish.run(t, Mgr(), ctx)
    return t, calls, cfg, z


def test_link_incollato_console_dalle_estensioni(tmp):
    t, calls, cfg, z = _unlinked(tmp, "Gioco.zip", "Gioco/Gioco [0100AAAA].xci")
    assert len(list(cfg.roms.rglob("*.xci"))) == 1 and calls and not z.exists()
    assert any("Console riconosciuta" in l["msg"] for l in t.log_after(0)[0])


def test_link_incollato_estensione_ambigua_non_indovina(tmp):
    t, calls, cfg, z = _unlinked(tmp, "Altro.zip", "Altro/Altro.iso")
    assert not calls and z.exists() and any("non capisco" in l["msg"] for l in t.log_after(0)[0])


def test_repack_pc_estratto_lascia_il_setup_da_avviare(tmp):
    """Il setup di un repack non entra in libreria: si avvia dal launcher (downloads/install.py)."""
    cfg = make_cfg(tmp)
    ctx, calls, got = make_ctx(cfg, online={"id": 7, "title": "Gioco PC", "key": "windows/net:7",
                                            "platform": "windows", "store": "online", "files": []})
    z = tmp / "dl" / "Repack.zip"
    z.parent.mkdir()
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("Repack/setup.exe", b"x")
        f.writestr("Repack/fg-01.bin", b"x")
    t = _task(tmp, "Repack.zip")
    finish.run(t, Mgr(), ctx)
    setup = Path(t.options["setup"]["exe"])
    assert setup.name == "setup.exe" and setup.is_file(), t.options
    assert not calls and z.exists()  # niente libreria, archivio tenuto finche' non si installa
    assert any("Repack pronto" in l["msg"] for l in t.log_after(0)[0])


def test_arcade_zip_non_viene_estratto(tmp, monkeypatch):
    """Per console arcade (.zip in plat.exts), il .zip e' gia' la ROM: non va estratto."""
    cfg = make_cfg(tmp)
    ctx, calls, got = make_ctx(cfg, online={"id": 7, "title": "Metal Slug", "key": "online/7", "platform": "neogeo",
                                            "store": "online", "files": []})
    z = tmp / "dl" / "mslug.zip"
    z.parent.mkdir()
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("201-p1.p1", b"x" * 20)
    monkeypatch.setattr(finish.X, "extract", lambda *a, **k: pytest.fail("uno zip arcade non va estratto"))
    t = _task(tmp, "mslug.zip")
    finish.run(t, Mgr(), ctx)
    placed = list(cfg.roms.rglob("mslug.zip"))
    assert len(placed) == 1 and calls == [{"platforms": ["neogeo"]}] and got
    assert t._stage("extract")["state"] == "skip" and t._stage("library")["state"] == "done"


def test_giochi_a_cartella_estratti_ps3_ps5_switch2(tmp):
    """Cartelle estratte PS3 (PS3_GAME/USRDIR/EBOOT.BIN), PS5 (eboot.bin) e Switch 2 (exefs+romfs) riconosciute."""
    for pid, members, check_rel in (
        ("ps3", {"GiocoPS3/PS3_GAME/USRDIR/EBOOT.BIN": b"eboot", "GiocoPS3/PS3_GAME/PARAM.SFO": b"sfo"},
         "GiocoPS3/PS3_GAME/USRDIR/EBOOT.BIN"),
        ("ps5", {"GiocoPS5/eboot.bin": b"eboot", "GiocoPS5/sce_sys/param.sfo": b"sfo"},
         "GiocoPS5/eboot.bin"),
        ("switch2", {"GiocoSW2/exefs/main": b"main", "GiocoSW2/romfs/data.bin": b"data"},
         "GiocoSW2/exefs/main"),
    ):
        sub = tmp / pid
        sub.mkdir()
        cfg = make_cfg(sub)
        ctx, calls, got = make_ctx(cfg, online={"id": 7, "title": f"Gioco {pid}", "key": "online/7",
                                                "platform": pid, "store": "online", "files": []})
        z = sub / "dl" / f"Gioco_{pid}.zip"
        z.parent.mkdir(parents=True)
        with zipfile.ZipFile(z, "w") as f:
            for k, v in members.items():
                f.writestr(k, v)
        t = DownloadTask(source=f"https://x/{z.name}", save_path=str(z.parent), name=z.name,
                         status=COMPLETED, options={"game_id": 7})
        finish.run(t, Mgr(switch2_format="off"), ctx)
        assert t._stage("library")["state"] == "done", (pid, t.log_after(0)[0])
        assert (cfg.roms / finish.P.PLATFORMS[pid].name / check_rel).is_file()
        assert calls == [{"platforms": [pid]}]


def test_archivio_annidato_un_livello(tmp):
    """Un archivio che contiene un solo altro archivio e nessuna ROM si estrae di un altro livello (max 1)."""
    import py7zr
    ctx, calls, got, cfg = _ctx(tmp)
    dl = tmp / "dl"
    dl.mkdir()
    inner = dl / "Gioco.7z"
    with py7zr.SevenZipFile(inner, "w") as f:
        f.writestr(b"x" * 50, "Gioco/Gioco [0100AAAA].xci")
    outer = dl / "Outer.zip"
    with zipfile.ZipFile(outer, "w") as f:
        f.write(inner, "Outer/Gioco.7z")
    inner.unlink()
    t = _task(tmp, "Outer.zip")
    finish.run(t, Mgr(), ctx)
    assert len(list(cfg.roms.rglob("*.xci"))) == 1 and calls
    assert not outer.exists()


def test_pacchetto_installabile_pkg_vpk_cia_avviso_non_fatale(tmp):
    """Un .pkg/.vpk/.cia entra in libreria ma lascia un avviso chiaro che va installato nell'emulatore."""
    for pid, fname in (("psvita", "Gioco.vpk"), ("3ds", "Gioco.cia"), ("ps4", "Gioco.pkg")):
        sub = tmp / pid
        sub.mkdir()
        cfg = make_cfg(sub)
        ctx, calls, got = make_ctx(cfg, online={"id": 7, "title": "Gioco", "key": "online/7",
                                                "platform": pid, "store": "online", "files": []})
        dl = sub / "dl"
        dl.mkdir(parents=True)
        (dl / fname).write_bytes(b"pkgdata")
        t = DownloadTask(source=f"https://x/{fname}", save_path=str(dl), name=fname,
                         status=COMPLETED, options={"game_id": 7})
        finish.run(t, Mgr(), ctx)
        assert t._stage("library")["state"] == "done" and calls
        assert "install" in (t._stage("library").get("note") or "").lower(), t.stages
        assert any("install" in l["msg"].lower() for l in t.log_after(0)[0])

