"""Path traversal su /themes e /plugins: id validati, radice figlia diretta, file dentro la radice.

Esegui: python tests/test_extensions_path_021.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pozzo.app import extensions as X  # noqa: E402


class Cfg:
    pass


def main():
    tmp = Path(tempfile.mkdtemp()).resolve()
    themes, plugins = tmp / "themes", tmp / "plugins"
    (themes / "ok").mkdir(parents=True)
    (themes / "ok" / "a.css").write_text("x")
    (plugins / "p1").mkdir(parents=True)
    (plugins / "p1" / "a.js").write_text("x")
    (tmp / "secret.js").write_text("s")
    (themes / "secret.css").write_text("s")
    X.theme_dirs = lambda cfg: [themes]
    X.plugin_dirs = lambda cfg: [plugins]
    X.BUILTIN_PLUGINS = plugins

    assert X.theme_file(Cfg(), "ok", "a.css")
    assert X.plugin_file(Cfg(), "p1", "a.js")
    for bad_id in ("..", ".", "", "../themes", "ok/..", "OK", str(tmp), "a/b"):
        assert X.theme_file(Cfg(), bad_id, "secret.css") is None, bad_id
        assert X.plugin_file(Cfg(), bad_id, "secret.js") is None, bad_id
    for rel in ("../secret.css", "..%2fsecret.css", "../../secret.js", str(tmp / "secret.js")):
        assert X.theme_file(Cfg(), "ok", rel) is None, rel
        assert X.plugin_file(Cfg(), "p1", rel) is None, rel
    assert X.is_inside(themes, themes / "ok" / "a.css")
    assert not X.is_inside(themes, tmp / "secret.js")
    assert not X.is_inside(themes / "ok", themes / "ok" / ".." / "secret.css")
    print("ok")


if __name__ == "__main__":
    main()
