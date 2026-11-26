"""Salvataggi scritti accanto a una copia temporanea del gioco («disco veloce», ZIP estratto in cache): non si perdono."""

import os
import sys
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from pozzo import config as C, platforms as P  # noqa: E402
from pozzo.library import fastcopy as FC, launcher as L  # noqa: E402


def _rom(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "G.nds").write_bytes(b"rom")
    (lib / "G.sav").write_text("prima")
    return lib / "G.nds", tmp_path / "fast" / "nds_g"


def _copied(tmp_path):
    rom, d = _rom(tmp_path)
    FC.copy(rom, d)
    FC.mark(d, rom)
    return rom, d


def _cfg(tmp_path):
    cfg = SimpleNamespace(cache=tmp_path, app={"fastcopy": {"dir": str(tmp_path / "fast")}})
    FC.ensure_root(cfg)
    return cfg


def test_sync_back_riporta_solo_cio_che_e_cambiato(tmp_path):
    rom, d = _copied(tmp_path)
    before = rom.stat().st_mtime_ns
    (d / "G.sav").write_text("dopo la partita")
    (d / "G.ml1").write_text("stato")
    FC.sync_back(d)
    assert (rom.parent / "G.sav").read_text() == "dopo la partita" and (rom.parent / "G.ml1").read_text() == "stato"
    assert rom.stat().st_mtime_ns == before and sorted(f.name for f in rom.parent.iterdir()) == ["G.ml1", "G.nds", "G.sav"]
    assert FC.same(d / "G.nds", rom), "copia tenuta: la prossima volta si riusa, salvataggi compresi"
    (d / "G.sav").write_text("seconda partita, senza ricopiare")
    FC.sync_back(d)
    assert (rom.parent / "G.sav").read_text() == "seconda partita, senza ricopiare"


def test_sync_back_cartella_di_un_gioco_pc(tmp_path):
    src = tmp_path / "Giochi" / "Foo"
    (src / "saves").mkdir(parents=True)
    (src / "foo.exe").write_bytes(b"x")
    d = tmp_path / "fast" / "pc"
    out = FC.copy(src, d)
    FC.mark(d, src)
    (out / "saves" / "1.sav").write_text("s")
    (out / "nuova").mkdir()
    (out / "nuova" / "cfg.ini").write_text("c")
    FC.sync_back(d)
    assert (src / "saves" / "1.sav").read_text() == "s" and (src / "nuova" / "cfg.ini").read_text() == "c"


def test_sync_back_non_sovrascrive_un_originale_cambiato(tmp_path):
    rom, d = _copied(tmp_path)
    (d / "G.sav").write_text("nella copia")
    (rom.parent / "G.sav").write_text("giocato dall'originale")
    os.utime(rom.parent / "G.sav", (time.time() + 60,) * 2)
    with pytest.raises(FC.FastCopyError, match="G.sav"):
        FC.sync_back(d)
    assert (rom.parent / "G.sav").read_text() == "giocato dall'originale" and (d / "G.sav").read_text() == "nella copia"


def test_purge_dopo_un_crash_salva_prima(tmp_path):
    cfg = _cfg(tmp_path)
    rom, d = _copied(tmp_path)
    (d / "G.sav").write_text("partita interrotta")
    assert FC.purge_stale(cfg) == 1 and not d.exists()
    assert (rom.parent / "G.sav").read_text() == "partita interrotta"


def test_purge_tiene_la_copia_se_non_riesce_a_salvare(tmp_path):
    cfg = _cfg(tmp_path)
    rom, d = _copied(tmp_path)
    (d / "G.sav").write_text("partita interrotta")
    rom.parent.rename(tmp_path / "disco-scollegato")
    assert FC.purge_stale(cfg) == 0 and (d / "G.sav").read_text() == "partita interrotta"


def test_purge_non_tocca_un_gioco_ancora_aperto(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    rom, d = _copied(tmp_path)
    (d / "G.sav").write_text("in corso")
    monkeypatch.setattr(FC, "in_use", lambda p: Path(p) == d)
    assert FC.purge_stale(cfg) == 0 and (d / "G.nds").exists() and (d / "G.sav").read_text() == "in corso"
    ln = L.Launcher.__new__(L.Launcher)  # e nemmeno riavviandolo mentre gira
    ln.cfg, ln.state, ln._set = cfg, {}, lambda **k: None
    os.utime(d / "G.nds", (1, 1))  # copia diversa dall'originale: si rifarebbe
    with pytest.raises(FC.FastCopyError, match="ancora aperto"):
        ln._fast_copy("nds/g", rom, {})
    assert (d / "G.nds").exists()


@pytest.mark.parametrize("delete_after", [True, False])
def test_avvio_da_disco_veloce_tiene_il_salvataggio(tmp_path, monkeypatch, delete_after):
    rom, _ = _rom(tmp_path)
    exe = tmp_path / "melonDS.exe"
    exe.write_bytes(b"")
    cfg = C.Config(cache=tmp_path / "cache")
    cfg.app["fastcopy"] = {"dir": str(tmp_path / "fast"), "delete_after": delete_after}
    cfg.emulators["melonds"] = str(exe)
    cfg.launch = {"nds": {"emulator": "melonds"}}

    class Proc:
        returncode, pid = 0, 0

        def poll(self):
            return 0

        def wait(self, timeout=None):
            return 0

    def popen(cmd, **kw):  # l'emulatore salva accanto alla ROM che gli si da'
        Path(cmd[-1]).with_suffix(".sav").write_text("salvato giocando")
        return Proc()

    monkeypatch.setattr(L, "subprocess", SimpleNamespace(Popen=popen, CREATE_NO_WINDOW=0))
    ln = L.Launcher(cfg, SimpleNamespace(mark_started=lambda k: None, record_play=lambda k, s: None))
    ln.launch("nds/g", "G", P.get("nds"), rom, fast=True)
    end = time.time() + 10
    while ln.state.get("status") not in ("finished", "error") and time.time() < end:
        time.sleep(0.02)
    assert ln.state["status"] == "finished", ln.state
    assert (rom.parent / "G.sav").read_text() == "salvato giocando"
    assert (tmp_path / "fast" / "nds_g" / "G.nds").exists() is not delete_after


# ---------------------------------------------------------------- ZIP estratti in cache
def _zip(tmp_path, i, files=None):
    p = tmp_path / f"g{i}.zip"
    with zipfile.ZipFile(p, "w") as z:
        for n, b in (files or {f"d/g{i}.nds": b"rom"}).items():
            z.writestr(n, b)
    return p


def _age(d, secs):
    os.utime(d, (time.time() - secs,) * 2)


def test_zip_estratto_il_salvataggio_resta(tmp_path):
    cfg = SimpleNamespace(cache=tmp_path / "cache")
    zips = [_zip(tmp_path, 0, {"g0.nds": b"rom grande", "g0.sav": b"zip"})]
    zips += [_zip(tmp_path, i) for i in range(1, L.MAX_EXTRACTED + 2)]

    def run(i):
        return L._extract(cfg, zips[i], f"nds_{i}", lambda m: None)

    out = run(0)
    out.with_suffix(".sav").write_text("partita")  # cambiato giocando
    out.with_suffix(".ml1").write_text("stato")
    _age(out.parent, 500)
    for i in range(1, L.MAX_EXTRACTED + 1):
        _age(run(i).parent, 400 - i)
    assert not out.exists(), "la ROM si libera"
    assert out.with_suffix(".sav").read_text() == "partita" and out.with_suffix(".ml1").read_text() == "stato"
    # la cartella coi soli salvataggi non toglie il posto ai giochi recenti
    run(L.MAX_EXTRACTED + 1)
    root = cfg.cache / "extract"
    assert sum(1 for d in root.iterdir() if any(d.glob("*.nds"))) == L.MAX_EXTRACTED
    assert not (root / "nds_1").exists(), "senza salvataggi la cartella sparisce"
    # di nuovo lo stesso gioco: la ROM torna, i salvataggi restano quelli dell'utente
    assert run(0).read_bytes() == b"rom grande"
    assert out.with_suffix(".sav").read_text() == "partita" and out.with_suffix(".ml1").read_text() == "stato"


def test_zip_estratto_da_una_versione_vecchia(tmp_path):
    """Cartella senza elenco dei file estratti: si libera solo il file piu' grande (la ROM)."""
    cfg = SimpleNamespace(cache=tmp_path / "cache")
    d = cfg.cache / "extract" / "nds_old"
    d.mkdir(parents=True)
    (d / "old.nds").write_bytes(b"x" * 1000)
    (d / "old.sav").write_text("s")
    _age(d, 900)
    for i in range(1, L.MAX_EXTRACTED + 1):
        L._extract(cfg, _zip(tmp_path, i), f"nds_{i}", lambda m: None)
    assert not (d / "old.nds").exists() and (d / "old.sav").read_text() == "s"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


def test_gruppo_processi_ignora_pid_finti():
    # pid 0 su Linux e' il gruppo dei thread del kernel: tenerlo farebbe restare la partita «in corso» per sempre
    job = L._PgJob()
    assert not job.add(SimpleNamespace(pid=0)) and not job.add(object()) and not job.pgids
    assert job.add(SimpleNamespace(pid=4242)) and job.pgids == {4242}
