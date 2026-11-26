"""0.21.0: settings.json e profili: copia .bak letta quando il file e' rotto, scrittura con fsync."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pozzo import config, profilecfg  # noqa: E402


def _cfg():
    d = Path(tempfile.mkdtemp())
    cfg = config.Config(cache=d / "cache", output=d / "out")
    cfg.config_path = d / "config.toml"
    return cfg


def test_corrupt_settings_read_from_bak():
    cfg = _cfg()
    config.save_settings(cfg, igdb={"client_id": "A"})
    config.save_settings(cfg, rawg={"key": "B"})  # il secondo salvataggio lascia in .bak il primo stato
    p = config.settings_path(cfg)
    assert p.with_suffix(".bak").exists()
    p.write_text("{rotto", encoding="utf-8")
    assert config.read_settings(cfg)["igdb"]["client_id"] == "A"
    config.save_settings(cfg, limits={"x": {"a": 1}})  # scrive dal .bak, il rotto va in quarantena
    s = config.read_settings(cfg)
    assert s["igdb"]["client_id"] == "A" and "limits" in s
    assert p.with_suffix(".rotto.json").exists()


def test_corrupt_without_bak_is_empty():
    cfg = _cfg()
    p = config.settings_path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{rotto", encoding="utf-8")
    assert config.read_settings(cfg) == {}


def test_atomic_write_fsyncs(monkeypatch):
    import os
    calls = []
    real = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: (calls.append(fd), real(fd)))
    cfg = _cfg()
    config.save_settings(cfg, igdb={"client_id": "A"})
    assert calls


def test_profile_file_falls_back_to_bak():
    cfg = _cfg()
    p = Path(cfg.config_path).parent / "profiles" / "luca.json"
    profilecfg._save(p, {"a": 1})
    profilecfg._save(p, {"a": 2})
    p.write_text("{rotto", encoding="utf-8")
    assert profilecfg._load(p) == {"a": 1}


def test_restore_keeps_current_devices_and_peers():
    import zipfile  # noqa: F401

    from pozzo import backup
    cfg = _cfg()
    Path(cfg.cache).mkdir(parents=True, exist_ok=True)
    config.save_settings(cfg, app={"phone": {"devices": [{"id": "X", "name": "Tel"}], "lib_invites": [{"id": "i1"}],
                                             "port": 8766},
                                   "sync": {"peers": [{"id": "pcB"}], "what": "all"}})
    b = backup.create(cfg)
    config.save_settings(cfg, app={"phone": {"devices": [{"id": "Y", "name": "Nuovo"}], "lib_invites": []},
                                   "sync": {"peers": []}})
    backup.restore(cfg, b.name)
    app = config.read_settings(cfg)["app"]
    assert [d["id"] for d in app["phone"]["devices"]] == ["Y"], app["phone"]  # X revocato: non torna
    assert not app["phone"].get("lib_invites") and not app["sync"].get("peers"), app
    assert app["phone"]["port"] == 8766 and app["sync"]["what"] == "all", "il resto viene dalla copia"
