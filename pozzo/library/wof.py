"""Compressione WOF (Windows Overlay Filter) della cartella di un gioco PC, come CompactGUI: `compact.exe /c /i /exe:<algo>`,
o dei file delle ROM: restano leggibili da ogni emulatore, con nome, dimensione e data invariati.

La stima viene dal database della comunita' di CompactGUI (risparmio medio misurato per gioco), in cache 7 giorni;
per le ROM e i giochi fuori dal database da campioni letti dai file."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import threading
import urllib.request
import zlib
from pathlib import Path

from .. import matching as M

DB_URL = "https://raw.githubusercontent.com/IridiumIO/CompactGUI/database/database.json"
DB_TTL = 7 * 86400
MIN_GAIN = 0.05  # sotto questa quota non vale ore di lettura: la stima a campioni sbaglia fino a 5 punti
ALGOS = ("xpress4k", "xpress8k", "xpress16k", "lzx")  # stesso ordine di CompType nel database (0..3)
DEFAULT_ALGO = "xpress8k"
# formati gia' compressi o cifrati: ricomprimerli legge tutto il disco per guadagnare (quasi) zero
PACKED = {".zip", ".7z", ".rar", ".gz", ".chd", ".rvz", ".wia", ".gcz", ".cso", ".zso", ".pbp", ".nsp", ".nsz", ".xcz",
          ".nup", ".wua", ".wux", ".pkg", ".mp4"}


def supported() -> bool:
    return sys.platform in ("win32", "darwin")  # mac: compressione trasparente APFS/HFS+ via ditto


def mac_compressed(folder) -> bool:
    """True se almeno un file ha il flag UF_COMPRESSED (stesso significato di `ls -lO`)."""
    for r, _, files in os.walk(folder):
        for f in files:
            try:
                if os.lstat(os.path.join(r, f)).st_flags & stat.UF_COMPRESSED:
                    return True
            except OSError:
                pass
    return False


def mac_rewrite(folder, uncompress: bool = False):
    """Ricopia la cartella con ditto in una temporanea e scambia: in caso di errore l'originale resta intatto."""
    src = os.path.abspath(folder)
    tmp, bak = src + ".pozzo-new", src + ".pozzo-old"
    for p in (tmp, bak):
        if os.path.lexists(p):
            raise OSError(f"esiste gia': {p}")
    try:
        subprocess.run(["ditto", "--nopreserveHFSCompression" if uncompress else "--hfsCompression", src, tmp],
                       check=True, capture_output=True)
        os.rename(src, bak)
        try:
            os.rename(tmp, src)
        except OSError:
            os.rename(bak, src)
            raise
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    shutil.rmtree(bak, ignore_errors=True)


def build_cmd(algo: str = DEFAULT_ALGO, uncompress: bool = False, files: list[str] | tuple = ()) -> list[str]:
    """Argomenti di compact.exe per un elenco di file."""
    if uncompress:
        return ["compact", "/u", "/i", "/exe", *files]
    if algo not in ALGOS:
        raise ValueError(algo)
    return ["compact", "/c", "/i", f"/exe:{algo}", *files]


def has_dstorage(folder) -> bool:
    """DirectStorage legge i file in modo diretto: su file compressi il gioco puo' non partire."""
    return any(f.lower() == "dstorage.dll" for _, _, files in os.walk(folder) for f in files)


def tree_files(folder) -> list[str]:
    return [os.path.join(r, f) for r, _, files in os.walk(folder) for f in files]


def rom_files(paths) -> list[str]:
    """File veri delle ROM: cartelle aperte, tracce di .cue/.gdi e dischi di .m3u compresi, senza doppioni."""
    from ..tools.impl.chd import _refs
    out: dict[str, None] = {}
    todo = [str(p) for p in paths]
    while todo:
        p = todo.pop()
        ext = os.path.splitext(p)[1].lower()
        if os.path.isdir(p):
            out.update(dict.fromkeys(tree_files(p)))
        elif p not in out and os.path.isfile(p):
            out[p] = None
            if ext in (".cue", ".gdi"):
                out.update(dict.fromkeys(map(str, _refs(Path(p)))))
            elif ext == ".m3u":
                lines = Path(p).read_text("utf-8", "replace").splitlines()
                todo += [os.path.join(os.path.dirname(p), s.strip()) for s in lines if s.strip() and not s.startswith("#")]
    return list(out)


def filesystem(path) -> str:
    """Nome del file system ("NTFS", "exFAT"...); "" se non si sa. WOF esiste solo su NTFS."""
    if sys.platform != "win32":
        return ""
    import ctypes
    root, name = ctypes.create_unicode_buffer(1024), ctypes.create_unicode_buffer(64)
    k = ctypes.windll.kernel32
    if not k.GetVolumePathNameW(str(path), root, 1024) or not k.GetVolumeInformationW(root, None, 0, None, None, None, name, 64):
        return ""
    return name.value


def sizes(files) -> tuple[int, int]:
    """(dimensione, byte occupati davvero sul disco) dei file; quelli spariti contano zero."""
    total = disk = 0
    if sys.platform == "win32":
        import ctypes
        fn = ctypes.WinDLL("kernel32", use_last_error=True).GetCompressedFileSizeW
        fn.argtypes, fn.restype = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_ulong)], ctypes.c_ulong
    for f in files:
        try:
            st = os.stat(f)
        except OSError:
            continue
        total += st.st_size
        if sys.platform == "win32":
            high = ctypes.c_ulong(0)
            ctypes.set_last_error(0)
            low = fn(f, ctypes.byref(high))
            disk += st.st_size if low == 0xFFFFFFFF and ctypes.get_last_error() else (high.value << 32) + low
        else:
            disk += st.st_blocks * 512
    return total, disk


def sample_ratio(files, n: int = 64, block: int = 32768) -> float:
    """Rapporto dopo/prima stimato con zlib su `n` blocchi sparsi nei file (xpress e LZX stanno li' attorno)."""
    parts = [(f, os.path.getsize(f)) for f in files if os.path.isfile(f)]
    total, raw, packed = sum(s for _, s in parts), 0, 0
    it, base = iter(parts), 0
    f, size = next(it, (None, 0))
    for i in range(n if total else 0):
        pos = total * i // n
        while pos >= base + size:
            base += size
            f, size = next(it)
        try:
            with open(f, "rb") as h:
                h.seek(pos - base)
                data = h.read(block)
        except OSError:  # file bloccato: gli altri campioni bastano
            continue
        raw += len(data)
        packed += min(len(data), len(zlib.compress(data)))
    return packed / raw if raw else 1.0


def fingerprint(path, n: int = 16, block: int = 65536) -> tuple | None:
    """(dimensione, data, CRC di blocchi sparsi; file piccoli per intero); None se il file non si legge."""
    try:
        st, crc = os.stat(path), 0
        step = max(block, (st.st_size - block) // (n - 1))
        with open(path, "rb") as h:
            for pos in range(0, st.st_size, step):
                h.seek(pos)
                crc = zlib.crc32(h.read(block), crc)
        return st.st_size, st.st_mtime_ns, crc
    except OSError:
        return None


def damaged(before: tuple | None, after: tuple | None) -> bool:
    """Contenuto cambiato senza che nessuno abbia scritto il file (data e dimensione uguali)."""
    return bool(before and after) and before[:2] == after[:2] and before[2] != after[2]


def batches(files, max_files: int = 20, max_bytes: int = 64 << 20):
    """Gruppi di file per una chiamata a compact: pochi alla volta, cosi' l'avanzamento si muove anche con le ISO."""
    cur, tot = [], 0
    for f in files:
        size = os.path.getsize(f) if os.path.isfile(f) else 0
        if cur and (len(cur) >= max_files or tot + size > max_bytes):
            yield cur
            cur, tot = [], 0
        cur.append(f)
        tot += size
    if cur:
        yield cur


# ------------------------------------------------------------ stima dal database CompactGUI
def build_index(raw: list) -> dict:
    """{titolo normalizzato: {"n": nome, "r": [rapporto dopo/prima per ciascun algoritmo, None = nessun dato]}}."""
    out = {}
    for e in raw:
        r = [None] * len(ALGOS)
        for c in e.get("CompressionResults") or []:
            if 0 <= c.get("CompType", -1) < len(ALGOS) and c.get("BeforeBytes"):
                r[c["CompType"]] = c["AfterBytes"] / c["BeforeBytes"]
        if any(x is not None for x in r):
            for name in (e.get("GameName"), e.get("FolderName")):
                if name and M.normalize(name):
                    out.setdefault(M.normalize(name), {"n": e.get("GameName") or name, "r": r})
    return out


def _download() -> list:
    req = urllib.request.Request(DB_URL, headers={"User-Agent": "Pozzo"})
    with urllib.request.urlopen(req, timeout=60) as r:  # nosec B310 - URL http(s) fissi o scelti dall'utente
        return json.loads(r.read().decode("utf-8-sig"))


def load_index(cache, fetch=_download) -> dict:
    hit = cache.kv_get("wof:db", DB_TTL)
    if hit is not None:
        return hit
    idx = build_index(fetch())
    cache.kv_set("wof:db", idx)
    return idx


def estimate(title: str, size: int, index: dict) -> dict | None:
    """{"name", "savings": {algo: byte risparmiati}, "best": algo} oppure None se il gioco non e' nel database."""
    hit = index.get(M.normalize(title))
    if not hit:
        n, _ = M.best(title, list(index), min_score=92)
        hit = index.get(n) if n else None
    if not hit:
        return None
    sav = {a: round(size * (1 - r)) for a, r in zip(ALGOS, hit["r"]) if r is not None}
    return {"name": hit["n"], "savings": sav, "best": max(sav, key=sav.get)}


# ------------------------------------------------------------ esecuzione
class Job:
    """compact.exe in un thread su una cartella o su un elenco di file: `done`/`total` = file elaborati / file totali,
    `saved` = byte liberati (compact esce con 0 anche quando non comprime niente). cancel() lo interrompe."""

    def __init__(self, target, algo: str = DEFAULT_ALGO, uncompress: bool = False):
        self.files = list(target) if isinstance(target, (list, tuple)) else None
        self.folder = None if self.files is not None else str(target)
        self.algo, self.uncompress = algo, uncompress
        build_cmd(algo, uncompress)  # algoritmo sbagliato: errore subito, non nel thread
        self.status, self.done, self.total, self.error, self.saved = "running", 0, 0, "", 0
        self._proc: subprocess.Popen | None = None
        self._cancel = False
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            files = tree_files(self.folder) if self.files is None else self.files
            self.total, before, rc = len(files), sizes(files)[1], 0
            if sys.platform == "darwin":
                mac_rewrite(self.folder, self.uncompress)
                self._cancel = False  # la riscrittura non si interrompe: e' comunque finita
            else:
                for group in batches(files):
                    if self._cancel:
                        break
                    marks = {f: fingerprint(f) for f in group}
                    rc = self._compact(build_cmd(self.algo, self.uncompress, group)) or rc
                    if bad := [f for f in group if damaged(marks[f], fingerprint(f))]:
                        self._compact(build_cmd(uncompress=True, files=bad))
                        raise OSError(f"{os.path.basename(bad[0])}: contenuto diverso dopo la compressione, lavoro fermato")
                    if not self._cancel:
                        self.done += len(group)
            if not self._cancel:
                self.done = self.total
            self.saved = before - sizes(files)[1]
            self.error = f"compact.exe: {rc}" if rc and not self._cancel else ""
            self.status = "cancelled" if self._cancel else "error" if rc else "done"
        except Exception as e:
            self.status, self.error = "error", str(e)

    def _compact(self, cmd) -> int:
        self._proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                      creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if self._cancel:  # annullato mentre il processo partiva
            self._proc.terminate()
        return self._proc.wait()

    def cancel(self):
        self._cancel = True
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    def state(self) -> dict:
        return {"status": self.status, "done": self.done, "total": self.total, "error": self.error,
                "saved": self.saved, "action": "uncompress" if self.uncompress else "compress"}
