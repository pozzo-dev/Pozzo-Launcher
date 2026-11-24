"""Collegamento sul desktop (.lnk) che avvia un gioco con PozzoLauncher («play --key», come le app di Sunshine).

Il tempo di gioco viene registrato: se l'app e' chiusa, il comando apre un PozzoLauncher senza finestra finche' si gioca.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path


def desktop_dir() -> Path:
    if sys.platform == "win32":
        import ctypes
        buf = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf) == 0:  # CSIDL_DESKTOPDIRECTORY (anche su OneDrive)
            return Path(buf.value)
    return Path.home() / "Desktop"


def file_name(title: str) -> str:
    """Titolo del gioco come nome di file valido su Windows."""
    return re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", title).strip(" .")[:100] or "Gioco"


def split_cmd(base: str) -> tuple[str, str]:
    """'"C:\\x\\cli.exe" -c "a b"' -> ('C:\\x\\cli.exe', '-c "a b"')."""
    m = re.match(r'\s*"([^"]+)"\s*(.*)', base)
    return (m.group(1), m.group(2)) if m else (base, "")


def make_icon(image: Path, out: Path) -> Path | None:
    """Icona .ico quadrata dalla copertina (centrata su fondo trasparente)."""
    try:
        from PIL import Image
        with Image.open(image) as im:
            im = im.convert("RGBA")
            im.thumbnail((256, 256))
            sq = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
            sq.paste(im, ((256 - im.width) // 2, (256 - im.height) // 2))
            out.parent.mkdir(parents=True, exist_ok=True)
            sq.save(out, format="ICO", sizes=[(256, 256), (64, 64), (48, 48), (32, 32), (16, 16)])
        return out
    except Exception:
        return None


def exe_icon(exe: Path, out: Path, size: int = 256) -> Path | None:
    """Icona di un .exe come PNG (la piu' grande disponibile, fino a `size`). Solo Windows; None se manca."""
    if sys.platform != "win32" or not Path(exe).is_file():
        return None
    import ctypes
    from ctypes import wintypes as W
    # DLL proprie: i tipi impostati qui (handle a 64 bit) non cambiano le windll condivise
    u32, g32 = ctypes.WinDLL("user32"), ctypes.WinDLL("gdi32")
    u32.GetDC.restype = W.HDC
    u32.GetDC.argtypes = [W.HWND]
    u32.ReleaseDC.argtypes = [W.HWND, W.HDC]
    u32.GetIconInfo.argtypes = [W.HICON, ctypes.c_void_p]
    u32.DestroyIcon.argtypes = [W.HICON]
    g32.GetObjectW.argtypes = [W.HANDLE, ctypes.c_int, ctypes.c_void_p]
    g32.GetDIBits.argtypes = [W.HDC, W.HBITMAP, W.UINT, W.UINT, ctypes.c_void_p, ctypes.c_void_p, W.UINT]
    g32.DeleteObject.argtypes = [W.HANDLE]
    hicon, iid = W.HICON(), W.UINT()
    if u32.PrivateExtractIconsW(str(exe), 0, size, size, ctypes.byref(hicon), ctypes.byref(iid), 1, 0) != 1 or not hicon:
        return None

    class ICONINFO(ctypes.Structure):
        _fields_ = [("fIcon", W.BOOL), ("x", W.DWORD), ("y", W.DWORD), ("mask", W.HBITMAP), ("color", W.HBITMAP)]

    class BITMAP(ctypes.Structure):
        _fields_ = [("type", W.LONG), ("w", W.LONG), ("h", W.LONG), ("wb", W.LONG), ("planes", W.WORD),
                    ("bpp", W.WORD), ("bits", ctypes.c_void_p)]

    ii, hdc = ICONINFO(), None
    try:
        if not u32.GetIconInfo(hicon, ctypes.byref(ii)) or not ii.color:
            return None
        bm = BITMAP()
        g32.GetObjectW(ii.color, ctypes.sizeof(bm), ctypes.byref(bm))
        w, h = bm.w, bm.h
        # BITMAPINFOHEADER a 32 bit, altezza negativa = righe dall'alto
        bih = (ctypes.c_uint32 * 10)(40, w, ctypes.c_uint32(-h).value, 1 | (32 << 16), 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * h * 4)
        hdc = u32.GetDC(None)
        if not g32.GetDIBits(hdc, ii.color, 0, h, buf, bih, 0):
            return None
        from PIL import Image
        im = Image.frombuffer("RGBA", (w, h), buf.raw, "raw", "BGRA", 0, 1)
        if not im.getchannel("A").getbbox():  # icone vecchie senza alfa: tutto opaco
            im.putalpha(255)
        out.parent.mkdir(parents=True, exist_ok=True)
        im.save(out, "PNG")
        return out
    except Exception:
        return None
    finally:
        if hdc:
            u32.ReleaseDC(None, hdc)
        for b in (ii.mask, ii.color):
            if b:
                g32.DeleteObject(b)
        u32.DestroyIcon(hicon)


def create(title: str, base_cmd: str, workdir: str, key: str, icon: str | None) -> Path:
    """Crea (o sostituisce) il collegamento sul desktop e ne restituisce il percorso."""
    target, args = split_cmd(base_cmd)
    if sys.platform != "win32":
        return _create_posix(title, target, args, workdir, key, icon)
    lnk = desktop_dir() / f"{file_name(title)}.lnk"
    # valori passati come variabili d'ambiente: nessun titolo o percorso finisce dentro il codice PowerShell
    env = {**os.environ, "GS_LNK": str(lnk), "GS_TARGET": target, "GS_ARGS": f'{args} play --key "{key}"'.strip(),
           "GS_WD": workdir, "GS_ICON": icon or target, "GS_DESC": f"Gioca a {title} con PozzoLauncher"}
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:GS_LNK);$s.TargetPath=$env:GS_TARGET;"
          "$s.Arguments=$env:GS_ARGS;$s.WorkingDirectory=$env:GS_WD;$s.IconLocation=$env:GS_ICON;"
          "$s.Description=$env:GS_DESC;$s.WindowStyle=7;$s.Save()")  # 7 = ridotta a icona: la console del comando non si vede
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], env=env, capture_output=True,
                       text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    if r.returncode or not lnk.exists():
        raise RuntimeError(f"Collegamento non creato: {(r.stderr or r.stdout).strip()[:300]}")
    return lnk


def _create_posix(title: str, target: str, args: str, workdir: str, key: str, icon: str | None) -> Path:
    """macOS: script .command (il Finder lo apre in Terminale); Linux: voce .desktop. Stesso comando di Windows."""
    cmd = " ".join(p for p in (shlex.quote(target), args, "play --key", shlex.quote(key)) if p)
    d = desktop_dir()
    d.mkdir(parents=True, exist_ok=True)
    if sys.platform == "darwin":
        out = d / f"{file_name(title)}.command"
        out.write_text(f"#!/bin/sh\ncd {shlex.quote(workdir)} || exit 1\nexec {cmd}\n", encoding="utf-8")
    else:
        out = d / f"{file_name(title)}.desktop"
        # in Exec il comando e' un solo argomento tra virgolette: \ " ` $ si proteggono, % si raddoppia (codici di campo)
        ex = "".join("\\" + c if c in '\\"`$' else "%%" if c == "%" else c for c in cmd)
        name = " ".join(title.split())
        lines = ["[Desktop Entry]", "Type=Application", f"Name={name}", f"Comment=Gioca a {name} con PozzoLauncher",
                 f'Exec=sh -c "{ex}"', f"Path={workdir}", "Terminal=false"]
        if icon and not icon.lower().endswith(".ico"):  # .ico e' un formato solo Windows
            lines.append(f"Icon={icon}")
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out.chmod(0o755)
    return out
