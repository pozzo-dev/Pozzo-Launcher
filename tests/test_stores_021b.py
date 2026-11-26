"""0.21.0b: un manifest illeggibile/anomalo non butta via tutto lo store (Epic, Steam).

Esegui: python tests/test_stores_021b.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pozzo.stores import epic, steam  # noqa: E402


def test_epic():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "list.item").write_text("[1, 2]")
        (root / "nokeys.item").write_text(json.dumps({"DisplayName": "x"}))
        (root / "ok.item").write_text(json.dumps({"AppName": "a", "CatalogNamespace": "n", "CatalogItemId": "c"}))
        old = epic.MANIFESTS
        epic.MANIFESTS = root
        try:
            got = epic.Epic.installed(None)
        finally:
            epic.MANIFESTS = old
        assert set(got) == {"c"}, set(got)


def test_steam():
    with tempfile.TemporaryDirectory() as tmp:
        lib = Path(tmp)
        apps = lib / "steamapps"
        apps.mkdir()
        (apps / "appmanifest_1.acf").write_text('"AppState"\n{\n"appid" "1"\n"name" "Good"\n"StateFlags" "4"\n}\n')
        (apps / "appmanifest_2.acf").mkdir()  # leggerlo da' OSError
        (apps / "appmanifest_3.acf").write_text('"AppState"\n{\n"appid" "3"\n"name" "Bad"\n"StateFlags" "x"\n}\n')
        got = steam.Steam.installed(SimpleNamespace(libraries=lambda: [lib],
                                                    _game=lambda appid, name, **k: SimpleNamespace(name=name)))
        assert "1" in got and got["1"].name == "Good", got


if __name__ == "__main__":
    test_epic(); test_steam()
    print("OK test_stores_021b")
