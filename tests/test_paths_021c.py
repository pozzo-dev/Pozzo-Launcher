"""Percorsi 0.21.0 (giro c): plugin collegato con symlink, temi utente con nome libero, cache dietro junction.

Esegui: python tests/test_paths_021c.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pozzo.app import extensions as X  # noqa: E402
from pozzo.app.routes import images as IM  # noqa: E402


def main():
    tmp = Path(tempfile.mkdtemp()).resolve()
    themes, plugins, dev = tmp / "themes", tmp / "plugins", tmp / "dev"
    (themes / "Mio Tema").mkdir(parents=True)
    (themes / "Mio Tema" / "a.css").write_text("x")
    (themes / "MioTema").mkdir()
    (themes / "MioTema" / "a.css").write_text("x")
    (tmp / "secret.css").write_text("s")
    X.theme_dirs = lambda cfg: [themes]
    X.plugin_dirs = lambda cfg: [plugins]
    assert X.theme_file(None, "Mio Tema", "a.css") is not None
    assert X.theme_file(None, "MioTema", "a.css") is not None
    for bad in ("", ".", "..", "a/b", "a\b", "../themes", "x\x00y"):
        assert X.theme_file(None, bad, "a.css") is None, bad
    assert X.theme_file(None, "Mio Tema", "../../secret.css") is None

    # plugin sviluppato fuori dalla cartella, collegato con symlink/junction
    dev.mkdir()
    (dev / "frontend.js").write_text("x")
    plugins.mkdir()
    try:
        (plugins / "lnk").symlink_to(dev, target_is_directory=True)
    except OSError:  # Windows senza privilegi: la junction non li richiede
        import subprocess
        subprocess.run(["cmd", "/c", "mklink", "/J", str(plugins / "lnk"), str(dev)], capture_output=True)
    if (plugins / "lnk").exists():
        assert X.plugin_file(None, "lnk", "frontend.js") is not None
        (tmp / "s.js").write_text("s")
        assert X.plugin_file(None, "lnk", "../s.js") is None
    else:
        print("symlink/junction non disponibili: salto")

    # immagini: controllo lessicale, niente resolve
    assert IM._rel_in_cache("covers/a.jpg")
    for bad in ("../x.jpg", "a/../../x.jpg", "/etc/passwd", "C:/x.jpg", "C:\\x.jpg"):
        assert not IM._rel_in_cache(bad), bad
    print("OK")


if __name__ == "__main__":
    main()
