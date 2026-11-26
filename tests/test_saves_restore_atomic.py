"""restore(): una copia danneggiata non deve lasciare i salvataggi a meta' (si legge tutto prima di toccare il disco)."""

import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pozzo import config  # noqa: E402
from pozzo.library import saves as SV  # noqa: E402

KEY = "pc/atomic"


def setup(root: Path):
    """cfg finto + cartella salvataggi con una copia fatta sulla cartella (cosi' restore gestisce gli «extra»)."""
    (root / "cache").mkdir()
    cfg = config.Config(cache=root / "cache", output=root / "out")
    sd = root / "saves" / "Game1"
    sd.mkdir(parents=True)
    (sd / "slot1.sav").write_bytes(b"vecchio")
    out = SV.backup(cfg, KEY, "Game1", [sd], "manuale")
    assert out is not None
    return cfg, sd, out


def test_restore_corrupt_backup_leaves_disk_untouched():
    with tempfile.TemporaryDirectory() as t:
        cfg, sd, out = setup(Path(t))
        (sd / "slot1.sav").write_bytes(b"nuovo")
        (sd / "extra.sav").write_bytes(b"x")
        if out.is_dir():  # copia come cartella: si toglie il file
            hit = [f for f in out.rglob("slot1.sav")]
            assert hit, list(out.rglob("*"))
            for f in hit:
                f.unlink()
        else:  # zip: lo si riscrive senza l'entry di slot1.sav
            with zipfile.ZipFile(out) as z:
                keep = {n: z.read(n) for n in z.namelist() if not n.endswith("slot1.sav")}
            with zipfile.ZipFile(out, "w") as z:
                for n, data in keep.items():
                    z.writestr(n, data)
        try:
            SV.restore(cfg, KEY, out.name)
        except Exception:
            pass
        else:
            assert False, "restore doveva fallire su una copia danneggiata"
        assert (sd / "slot1.sav").read_bytes() == b"nuovo", "il file non va toccato"
        assert (sd / "extra.sav").exists(), "il file extra non va cancellato"


def test_restore_ok_rolls_back_and_removes_extra():
    with tempfile.TemporaryDirectory() as t:
        cfg, sd, out = setup(Path(t))
        (sd / "slot1.sav").write_bytes(b"nuovo")
        (sd / "extra.sav").write_bytes(b"x")
        r = SV.restore(cfg, KEY, out.name)
        assert (sd / "slot1.sav").read_bytes() == b"vecchio"
        assert not (sd / "extra.sav").exists()
        assert r["removed"] == 1 and r["written"] == 1, r


def test_restore_non_toglie_i_file_che_non_sa_rimettere():
    """I tipi eseguibili non si ripristinano mai: quindi non si cancellano nemmeno."""
    with tempfile.TemporaryDirectory() as t:
        cfg, sd, _ = setup(Path(t))
        (sd / "plugin.js").write_bytes(b"mod")
        out = SV.backup(cfg, KEY, "Game1", [sd], "manuale")
        (sd / "slot1.sav").write_bytes(b"nuovo")
        assert SV.diff(cfg, KEY, out.name)["extra"] == []
        r = SV.restore(cfg, KEY, out.name)
        assert (sd / "slot1.sav").read_bytes() == b"vecchio" and (sd / "plugin.js").read_bytes() == b"mod", r
        assert r["removed"] == 0


def test_la_rotazione_toglie_solo_le_copie_del_gioco():
    """Due giochi con lo stesso nome (es. versioni regionali) condividono la cartella delle copie, non il limite."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
        cfg = config.Config(cache=Path(t) / "cache", output=Path(t) / "out")
        cfg.app["save_keep"] = 3
        usa, eur = Path(t) / "usa", Path(t) / "eur"
        usa.mkdir(), eur.mkdir()
        (usa / "T.sav").write_text("usa")
        SV._store(cfg, "nes/usa", "Tetris", {SV._mkey(usa / "T.sav"): (usa / "T.sav", None)}, "manuale", [], when=1_000_000)
        for i in range(5):
            (eur / "T.sav").write_text(f"eur{i}")
            SV._store(cfg, "nes/eur", "Tetris", {SV._mkey(eur / "T.sav"): (eur / "T.sav", None)}, "manuale", [],
                      when=2_000_000 + i * 60)
        names = [k for b in SV._mapping(SV._game_dir(cfg, "nes/usa"))["backups"] for k in b["files"]]
        assert sum("/usa/" in n for n in names) == 1 and sum("/eur/" in n for n in names) == 3, names


if __name__ == "__main__":
    test_restore_non_toglie_i_file_che_non_sa_rimettere()
    test_restore_corrupt_backup_leaves_disk_untouched()
    test_restore_ok_rolls_back_and_removes_extra()
    print("OK")
