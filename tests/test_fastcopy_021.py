"""fastcopy: le tracce di .cue/.m3u (nomi diversi dal foglio) vengono copiate insieme."""

from __future__ import annotations

from pathlib import Path

from pozzo.library import fastcopy as FC


def _names(src: Path) -> set[str]:
    return {p.name for p in FC._entries(src)[1]}


def test_cue_con_tracce(tmp_path):
    (tmp_path / "Game (USA).cue").write_text(
        'FILE "Game (USA) (Track 01).bin" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n'
        'FILE "Game (USA) (Track 02).bin" BINARY\n  TRACK 02 AUDIO\n    INDEX 01 00:00:00\n', "utf-8")
    for n in ("Game (USA) (Track 01).bin", "Game (USA) (Track 02).bin", "Altro.bin"):
        (tmp_path / n).write_bytes(b"x")
    assert _names(tmp_path / "Game (USA).cue") == {"Game (USA).cue", "Game (USA) (Track 01).bin", "Game (USA) (Track 02).bin"}


def test_m3u_con_due_dischi(tmp_path):
    (tmp_path / "Game.m3u").write_text("Game (Disc 1).chd\nGame (Disc 2).chd\n", "utf-8")
    for n in ("Game (Disc 1).chd", "Game (Disc 2).chd"):
        (tmp_path / n).write_bytes(b"x")
    assert _names(tmp_path / "Game.m3u") == {"Game.m3u", "Game (Disc 1).chd", "Game (Disc 2).chd"}


if __name__ == "__main__":
    import tempfile
    for f in (test_cue_con_tracce, test_m3u_con_due_dischi):
        f(Path(tempfile.mkdtemp()))
    print("ok")
