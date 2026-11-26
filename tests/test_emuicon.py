"""Icona degli emulatori nella vetrina: quella dell'eseguibile installato, altrimenti il logo dell'organizzazione
del progetto su GitHub (solo organizzazioni: l'avatar di una persona non e' un logo), altrimenti nessuna.

Esegui: python tests/test_emuicon.py
"""
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace as N

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pozzo import emuinstall as EI  # noqa: E402

try:  # con pytest la cartella temporanea arriva dalla fixture «d»
    import pytest

    @pytest.fixture
    def d(tmp_path):
        return tmp_path
except ImportError:
    pass


def test_logo_solo_organizzazioni():
    # PCSX2 ha build su tutti e tre i sistemi (Dolphin no: su Linux non e' nel catalogo)
    assert EI.logo_url("pcsx2") == "https://github.com/PCSX2.png?size=128"
    assert EI.logo_url("duckstation") is None, "stenzek e' una persona"
    assert EI.logo_url("ryujinx") is None, "Forgejo dietro controllo anti-bot: niente logo remoto"
    assert EI.logo_url("inesistente") is None


def test_icona_dal_logo_e_cache(d: Path):
    chiamate = []

    def fetch(url):
        chiamate.append(url)
        return b"\x89PNG finto"
    cfg = N(emulators={})
    p = EI.emu_icon(cfg, "pcsx2", d, fetch=fetch)
    assert p and p.read_bytes() == b"\x89PNG finto"
    assert EI.emu_icon(cfg, "pcsx2", d, fetch=fetch) == p and len(chiamate) == 1, "seconda volta dalla cache"
    assert EI.emu_icon(cfg, "duckstation", d, fetch=fetch) is None
    assert EI.emu_icon(cfg, "pcsx2/../x", d, fetch=fetch) is None, "nome non nel catalogo"


def test_rete_giu(d: Path):
    def fetch(url):
        raise OSError("offline")
    assert EI.emu_icon(N(emulators={}), "pcsx2", d, fetch=fetch) is None
    assert not list(d.iterdir()), "nessun file a meta'"


if __name__ == "__main__":
    test_logo_solo_organizzazioni()
    for fn in (test_icona_dal_logo_e_cache, test_rete_giu):
        with tempfile.TemporaryDirectory() as t:
            fn(Path(t))
    print("TUTTI I TEST OK")
