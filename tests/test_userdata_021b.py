"""userdata 0.21b: record_play in una transazione, stesso risultato di prima."""

from __future__ import annotations

from pathlib import Path

from pozzo.library.userdata import UserData


def test_record_play(tmp_path):
    u = UserData(Path(tmp_path) / "u.db")
    r0 = u.rev
    u.record_play("a", 60)  # riga nuova
    g = u.games()["a"]
    assert (g["playtime"], g["play_count"], g["status"]) == (60, 1, "playing") and u.rev == r0 + 1
    u.set_flag("b", "status", "backlog")
    u.record_play("b", 30)
    assert u.games()["b"]["status"] == "playing"
    u.set_flag("c", "status", "done")
    u.record_play("c", 10)
    u.record_play("c", 5)
    g = u.games()["c"]
    assert (g["playtime"], g["play_count"], g["status"]) == (15, 2, "done")
    assert len(u.sessions()) == 4


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
