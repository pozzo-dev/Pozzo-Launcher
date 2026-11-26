"""Cartella static e versione degli asset. Modulo a parte perché le route lo importano senza passare da server.py."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .. import config as C

STATIC = Path(__file__).parent / "static"

_ASSET_V: list[str] = []


def _asset_version() -> str:
    """Hash per rompere la cache del browser. Nel build congelato i file non cambiano finche' il processo vive: una
    volta sola. Da sorgenti si ricalcola a ogni pagina (shortcut: ~100 file letti, solo in sviluppo, dove i file
    cambiano; se pesa, chiave = mtime piu' recente dell'albero static)."""
    if C.FROZEN and _ASSET_V:
        return _ASSET_V[0]
    v = _hash_assets()
    if C.FROZEN:
        _ASSET_V[:] = [v]
    return v


def _hash_assets() -> str:
    from .. import __version__

    digest = hashlib.sha256()
    assets = [*STATIC.glob("*.css"), *STATIC.glob("*.js")]
    assets.extend(path for path in STATIC.joinpath("js").rglob("*.js") if path.is_file())
    assets.extend(path for path in STATIC.joinpath("experiences").rglob("*")
                  if path.is_file() and path.suffix in (".css", ".js"))
    assets.extend(path for path in STATIC.joinpath("settings").rglob("*.html") if path.is_file())
    for path in sorted(assets):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return f"{__version__}.{digest.hexdigest()[:12]}"
