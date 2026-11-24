"""Icona delle app aggiunte a mano: estratta dal loro .exe e salvata tra le immagini dello store «manual».

Esegui: PYTHONUTF8=1 python tests/test_exe_icon.py
"""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pozzo import stores as ST
from pozzo.library import shortcut as SC

with tempfile.TemporaryDirectory() as t:
    t = Path(t)
    assert SC.exe_icon(t / "manca.exe", t / "x.png") is None  # file assente: nessuna icona, nessun errore
    if sys.platform == "win32":
        exe = Path(sys.executable)  # python.exe ha un'icona
        out = SC.exe_icon(exe, t / "py.png")
        from PIL import Image
        with Image.open(out) as im:
            assert im.mode == "RGBA" and im.width >= 32 and im.getchannel("A").getbbox()

    # aggancio in _download_images: solo app a mano con un .exe, e senza ricerca/scaricamento online
    class Cache:
        folder = t
        media_dir = t / "media"
    fake = t / "media" / "windows" / "icon" / "manual_7.png"
    SC.exe_icon = lambda exe, out: (out.parent.mkdir(parents=True, exist_ok=True), out.write_bytes(b"x"), out)[2]
    games = [{"store": "manual", "id": "7", "title": "App", "images": {"cover": "c"}, "media": {"cover": "gia'"},
              "launch": {"type": "exe", "target": "C:/a.exe"}},
             {"store": "manual", "id": "8", "title": "Web", "images": {"cover": "c"}, "media": {"cover": "gia'"},
              "launch": {"type": "uri", "target": "https://x"}}]
    asyncio.run(ST._download_images(None, Cache(), None, games, print))
    assert games[0]["media"]["icon"] == fake.relative_to(t).as_posix() and fake.exists()
    assert "icon" not in games[1]["media"]  # i giochi browser non hanno un .exe

print("ok")
