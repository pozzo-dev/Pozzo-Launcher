"""Aggiornamento su macOS: nessun file non sigillato nel .app e riscrittura del sigillo dopo lo swap."""

import hashlib
import sys
import shutil
import tempfile
import time
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pozzo import updates


def _swap(platform, base):
    old = sys.platform
    sys.platform = platform
    try:
        cmd = updates.swap_script(base, PurePosixPath("/s/stage"), PurePosixPath("/a/App"), 42)  # "/" anche su Windows
    finally:
        sys.platform = old
    # write_text su Windows raddoppia i \r: si normalizza
    return Path(cmd[-1]).read_bytes().decode("utf-8").replace("\r\r\n", "\n").replace("\r\n", "\n")


def test_stage_has_no_manifest_in_bundle():
    old = sys.platform
    sys.platform = "darwin"
    try:
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            app, stage, pkg = root / "P.app", root / ".P.app.stage-x", root / "p.zip"
            (app / "Contents").mkdir(parents=True)
            (app / "Contents" / "a.txt").write_bytes(b"a")
            (app / updates.MANIFEST).write_text("vecchio")  # installazione precedente col manifest nel bundle
            new = {"version": "9.9.9", "file": {}}
            real = (updates._extract_package, updates._prune_removed, updates._overlay, updates._verify_files,
                    updates._platform_files)
            updates._extract_package = lambda p, u, k: u.mkdir()
            updates._prune_removed = lambda *a: None
            updates._overlay = lambda *a: None
            updates._verify_files = lambda *a: None
            updates._platform_files = lambda *a: {}
            try:
                updates._stage_full(app, stage, pkg, "portable", None, new, "macos")
            finally:
                updates._extract_package, updates._prune_removed, updates._overlay, updates._verify_files, \
                    updates._platform_files = real
            assert (root / ".P.app.manifest.json").is_file()
            assert not (stage / "Contents" / updates.MANIFEST).exists()
            # unico residuo ammesso nello stage: il vecchio manifest copiato, che lo swap rimuove
            assert {p.name for p in stage.iterdir()} <= {"Contents", updates.MANIFEST}
            assert updates._manifest_path(app) == root / ".P.app.manifest.json"
    finally:
        sys.platform = old


def test_swap_script_resigns_on_mac():
    with tempfile.TemporaryDirectory() as t:
        s = _swap("darwin", Path(t))
    assert "xattr -cr /a/App" in s and "codesign --force --deep -s - /a/App" in s
    assert s.index("rm -rf") < s.index("codesign") < s.rindex("open /a/App")
    assert f"rm -f /a/App/{updates.MANIFEST}" in s


def test_swap_script_unchanged_elsewhere():
    with tempfile.TemporaryDirectory() as t:
        assert _swap("linux", Path(t)) == (
            "#!/bin/sh\nwhile kill -0 42 2>/dev/null; do sleep 1; done\nn=0\n"
            "until mv /a/App /a/.App.old-42; do n=$((n+1)); [ $n -ge 15 ] && {\n/a/App/PozzoLauncher &\nexit 1; }; sleep 1; done\n"
            "if ! mv /s/stage /a/App; then mv /a/.App.old-42 /a/App\n/a/App/PozzoLauncher &\nexit 1; fi\nrm -rf /a/.App.old-42\n"
            "/a/App/PozzoLauncher &\n")
        assert _swap("win32", Path(t)) == (
            '@echo off\nchcp 65001 >nul\nset S=%SystemRoot%\\System32\n:wait\n"%S%\\tasklist.exe" /FI "PID eq 42" | '
            '"%S%\\find.exe" "42" >nul && ("%S%\\timeout.exe" /t 1 /nobreak >nul & goto wait)\n'
            'set N=0\n:swap\nmove "/a/App" "/a/.App.old-42" >nul && goto moved\nset /a N+=1\n'
            'if %N% lss 15 ("%S%\\ping.exe" -n 2 127.0.0.1 >nul & goto swap)\ngoto run\n:moved\n'
            'move "/s/stage" "/a/App" >nul\nif errorlevel 1 (move "/a/.App.old-42" "/a/App" >nul & goto run)\n'
            'rmdir /S /Q "/a/.App.old-42"\n:run\nstart "" "/a/App/PozzoLauncher.exe"\n')
        old = sys.platform
        sys.platform = "linux"
        try:
            assert updates._manifest_path(Path("/a/App")) == Path("/a/App") / updates.MANIFEST
        finally:
            sys.platform = old


def _run_swap(t: Path, lock: bool, good: bool = True):
    """Esegue davvero lo script di questo sistema (finto solo l'avvio dell'app). Ritorna il testo di chi e' ripartito."""
    import os
    import subprocess
    dst, src, tmp = t / "App", t / "stage", t / "work"
    tmp.mkdir()
    for d, v in ((dst, "vecchia"), (src, "nuova")):
        d.mkdir()
        (d / "v.txt").write_text(v)
        if os.name == "nt":
            (d / "PozzoLauncher.cmd").write_text(f'@copy "%~dp0v.txt" "{t / "partita.txt"}" >nul\r\n@exit\r\n')
        else:
            f = d / "PozzoLauncher"
            # relativo allo script, come %~dp0 su Windows: dopo lo swap «stage» e' diventata «App»
            f.write_text(f'#!/bin/sh\ncp "$(dirname "$0")/v.txt" "{t / "partita.txt"}"\n')
            f.chmod(0o755)
    if not good:
        shutil.rmtree(src)
    updates.SWAP_TRIES, saved = 2, updates.SWAP_TRIES
    try:
        cmd = updates.swap_script(tmp, src, dst, 99999999)
    finally:
        updates.SWAP_TRIES = saved
    script = Path(cmd[-1])
    script.write_bytes(script.read_bytes().replace(b"PozzoLauncher.exe", b"PozzoLauncher.cmd"))
    h = open(dst / "v.txt") if lock else None  # come un antivirus che tiene un file
    try:
        subprocess.run(cmd, capture_output=True, timeout=60, check=False)
    finally:
        h and h.close()
    for _ in range(100):
        if (t / "partita.txt").exists() and (t / "partita.txt").read_text():
            break
        time.sleep(0.1)
    return (t / "partita.txt").read_text() if (t / "partita.txt").exists() else None


def test_swap_riapre_sempre_l_app():
    if sys.platform == "darwin":
        return  # «open» vuole un bundle vero
    for lock, good, want in ((False, True, "nuova"), (False, False, "vecchia"), (True, True, "vecchia")):
        if lock and sys.platform != "win32":
            continue  # su Linux un file aperto non blocca la cartella
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
            assert _run_swap(Path(t), lock, good) == want, (lock, good)
            assert (Path(t) / "App" / "v.txt").read_text() == want


if __name__ == "__main__":
    test_stage_has_no_manifest_in_bundle()
    test_swap_script_resigns_on_mac()
    test_swap_script_unchanged_elsewhere()
    test_swap_riapre_sempre_l_app()
    print("ok")
