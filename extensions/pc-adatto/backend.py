"""Il mio PC ce la fa?: confronta l'hardware con i requisiti del gioco.

GET /plugin-api/pc-adatto/hw
  -> {"cpu": {"name","cores","threads","mhz","tier"}, "ram_gb", "gpu": {"name","vram_gb","tier"}, "incerto": bool}
GET /plugin-api/pc-adatto/check/{game_id}
  -> {"verdict": "ok"|"impostazioni"|"insufficiente"|"sconosciuto",
      "meters": [{"part": "cpu"|"gpu"|"ram", "have", "min", "rec", "status": "ok"|"rec"|"min"|None}],
      "note": codice|None, "tips": [codice], "hw": <come sopra>, "requirements": {...}}
Testi di note e tips nel locales.json dell'estensione (note.<codice>, tip.<codice>): li scrive l'interfaccia.
"""

import json
import os
import platform
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import httpx
from fastapi import HTTPException

TTL = 30 * 86400
_HW: dict | None = None


# ---------- hardware ----------
def _ps(cmd: str):
    if os.name != "nt":
        return None
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", f"{cmd} | ConvertTo-Json -Compress"],
                             capture_output=True, text=True, timeout=10, creationflags=0x08000000).stdout.strip()
        j = json.loads(out) if out else None
        return j if isinstance(j, list) else ([j] if j else [])
    except Exception:
        return None


def _run(*cmd: str) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return ""


def _detect_mac() -> dict:
    ram = int(_run("sysctl", "-n", "hw.memsize") or 0)
    name = _run("sysctl", "-n", "machdep.cpu.brand_string")
    g = {}
    try:
        g = (json.loads(_run("system_profiler", "SPDisplaysDataType", "-json")).get("SPDisplaysDataType") or [{}])[0]
    except ValueError:
        pass
    m = re.search(r"([\d.]+)\s*(GB|MB)", str(g.get("spdisplays_vram") or g.get("spdisplays_vram_shared") or ""))
    # Apple Silicon: memoria unificata senza VRAM dedicata, stimo meta' della RAM per la GPU
    vram = float(m[1]) / (1 if m[2] == "GB" else 1024) if m else round(ram / 2**30 / 2, 1)
    return {"cpu": {"name": name or platform.processor(), "cores": int(_run("sysctl", "-n", "hw.physicalcpu") or 0) or (os.cpu_count() or 1),
                    "threads": os.cpu_count() or 1, "mhz": 0},
            "ram_gb": round(ram / 2**30, 1), "gpu": {"name": g.get("sppci_model") or "", "vram_gb": vram}}


def _detect_linux() -> dict:
    def read(p):
        try:
            return Path(p).read_text(errors="ignore")
        except OSError:
            return ""
    m = re.search(r"MemTotal:\s+(\d+)", read("/proc/meminfo"))
    cpu = re.search(r"model name\s*:\s*(.+)", read("/proc/cpuinfo"))
    gpu, vram = "", 0.0
    nv = _run("nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader").splitlines()
    if nv and (p := nv[0].split(",")) and len(p) == 2:
        gpu = p[0].strip()
        vram = round(float(re.sub(r"[^\d.]", "", p[1]) or 0) / 1024, 1)  # MiB
    else:
        v = re.search(r'^\S+ "VGA[^"]*" "[^"]*" "([^"]*)"', _run("lspci", "-mm"), re.M)
        gpu = v[1] if v else ""
    return {"cpu": {"name": (cpu[1] if cpu else platform.processor() or platform.machine()).strip(),
                    "cores": os.cpu_count() or 1, "threads": os.cpu_count() or 1, "mhz": 0},
            "ram_gb": round(int(m[1]) / 2**20, 1) if m else 0, "gpu": {"name": gpu, "vram_gb": vram}}


def detect() -> dict:
    if sys.platform == "darwin":
        return _detect_mac()
    if sys.platform.startswith("linux"):
        return _detect_linux()
    cpu = (_ps("Get-CimInstance Win32_Processor | Select Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed") or [{}])[0]
    gpus = _ps("Get-CimInstance Win32_VideoController | Select Name,AdapterRAM") or []
    ram = (_ps("Get-CimInstance Win32_ComputerSystem | Select TotalPhysicalMemory") or [{}])[0]
    name = (cpu.get("Name") or platform.processor() or platform.machine()).strip()
    gpu = max(gpus, key=lambda g: gpu_tier(g.get("Name") or "")[0], default={})
    return {"cpu": {"name": name, "cores": cpu.get("NumberOfCores") or (os.cpu_count() or 1),
                    "threads": cpu.get("NumberOfLogicalProcessors") or os.cpu_count() or 1,
                    "mhz": cpu.get("MaxClockSpeed") or 0},
            "ram_gb": round((ram.get("TotalPhysicalMemory") or 0) / 2**30, 1),
            # shortcut: AdapterRAM e' uint32 (max 4 GB) sulle GPU recenti, solo indicativo
            "gpu": {"name": gpu.get("Name") or "", "vram_gb": round((gpu.get("AdapterRAM") or 0) / 2**30, 1)}}


def hw() -> dict:
    global _HW
    if _HW is None:
        h = detect()
        c, g = cpu_tier(h["cpu"]["name"]), gpu_tier(h["gpu"]["name"])
        h["cpu"]["tier"], h["gpu"]["tier"] = c[0], g[0]
        h["incerto"] = not (c[1] and g[1])
        _HW = h
    return _HW


# ---------- punteggi 1..5: (tier, riconosciuto) ----------
# CPU: Core iN/Ryzen N -> base 3=>2, 5=>3, 7=>4, 9=>5; generazione vecchia -1, recente +1.
def cpu_tier(name: str) -> tuple[int, bool]:
    n = name.lower()
    base = {"3": 2, "5": 3, "7": 4, "9": 5}
    if "apple" in n or re.search(r"\bm[1-9]\b", n):
        return 5, True
    if m := re.search(r"ryzen\s*(?:ai\s*)?([3579])\s+(\d)\d{3}", n):
        return max(1, min(5, base[m[1]] - (m[2] in "12") + (m[2] in "89" and m[1] != "9"))), True
    if m := re.search(r"i([3579])-?\s*(\d{4,5})", n):
        gen = int(m[2][:2] if len(m[2]) == 5 else m[2][0])
        return max(1, min(5, base[m[1]] - (gen <= 5) + (gen >= 12 and m[1] != "9"))), True
    if "core ultra" in n:
        return 4, True
    if re.search(r"celeron|pentium|atom|\bn\d{3,4}\b|athlon|a[46]-", n):
        return 1, True
    if "core 2" in n or "phenom" in n:
        return 2, True
    return 3, False


# GPU: numero di modello -> tier. Le integrate (UHD/HD/Iris/Vega/Radeon Graphics) stanno a 1-2.
def gpu_tier(name: str) -> tuple[int, bool]:
    n = name.lower()
    if m := re.search(r"rtx\s*(\d{4})", n):
        v = int(m[1])
        s = v % 100
        t = 5 if s >= 70 else 4 if s >= 60 else 3
        return (t - 1 if v < 3000 and t == 5 else t), True
    if m := re.search(r"gtx\s*(\d{3,4})", n):
        v = int(m[1])
        return (3 if v >= 1600 else 4 if v >= 1070 else 3 if v >= 1050 else 2 if v >= 900 else 1), True
    if m := re.search(r"\brx\s*(\d{3,4})", n):
        v = int(m[1])
        if v >= 6000:
            s = v % 1000 // 100
            return (5 if s >= 7 else 4 if s >= 6 else 3), True
        if v >= 5000:
            return (4 if v % 1000 // 100 >= 7 else 3), True
        return (3 if v >= 570 else 2), True
    if m := re.search(r"arc\s*a(\d)", n):
        return (4 if int(m[1]) >= 7 else 3), True
    if "apple" in n:
        return 4, True
    if "iris xe" in n:
        return 2, True
    if re.search(r"uhd|intel.*hd graphics|iris|vega \d|radeon.*graphics|radeon\(tm\) graphics", n):
        return 1, True
    return 3, False


# ---------- requisiti per console: (cpu min, gpu min, ram min, cpu cons., gpu cons., ram cons., consigli) ----------
EASY = (1, 1, 2, 1, 1, 4, [])
REQ = {
    "ps3": (3, 3, 8, 4, 4, 16, ["vulkan", "res720", "spu", "nopost"]),
    "switch": (3, 3, 8, 4, 4, 16, ["vulkan", "res1x", "undocked", "shaders"]),
    "wiiu": (3, 3, 8, 4, 4, 16, ["vulkan", "native"]),
    "ps2": (2, 2, 4, 3, 3, 8, ["res12x", "vulkan_d3d11"]),
    "gc": (2, 2, 4, 3, 3, 8, ["vulkan_d3d11", "res12x"]),
    "wii": (2, 2, 4, 3, 3, 8, ["vulkan_d3d11", "res12x"]),
    "xbox360": (4, 3, 8, 5, 4, 16, ["vulkan_d3d12", "native", "fps30"]),
    "xbox": (2, 2, 4, 3, 3, 8, ["res1x"]),
    "psp": (2, 2, 4, 2, 2, 4, ["res12x"]),
    "psvita": (3, 2, 8, 4, 3, 8, ["res1x"]),
    "3ds": (2, 2, 4, 3, 2, 8, ["res12x", "shaders"]),
    "n64": (1, 1, 4, 2, 2, 4, ["n64video"]),
    "dreamcast": (2, 2, 4, 2, 2, 4, ["native"]),
    "saturn": (2, 1, 4, 3, 2, 4, ["mednafen"]),
    "ps4": (4, 4, 16, 5, 5, 16, ["experimental"]),
    "ps5": (5, 5, 16, 5, 5, 32, ["experimental"]),
}
for _p in ("nes fds snes gb gbc gba nds virtualboy pokemini gameandwatch mastersystem megadrive gamegear sega32x segacd "
           "psx atari2600 atari5200 atari7800 atarilynx atarijaguar atarist atari800 pcengine pcenginecd pcfx neogeo "
           "neogeocd ngp ngpc wonderswan wonderswancolor 3do coleco intellivision vectrex videopac channelf c64 vic20 "
           "amiga amigacd32 msx msx2 amstradcpc zxspectrum zx81 x68000 pc98 dos scummvm arcade fbneo cps1 cps2 cps3 "
           "naomi atomiswave").split():
    REQ.setdefault(_p, EASY)


def meters(h: dict, mins: tuple, recs: tuple) -> list[dict]:
    """Un indicatore per CPU, scheda video e RAM: status "ok" (consigliato), "rec" (sotto il consigliato),
    "min" (sotto il minimo), None (requisito sconosciuto). Livelli CPU/GPU da 1 a 5, RAM in GB."""
    out = []
    for part, have, mn, rc in zip(("cpu", "gpu", "ram"), (h["cpu"]["tier"], h["gpu"]["tier"], h["ram_gb"]), mins, recs):
        eff = have + 0.5 if part == "ram" else have  # 16 GB installati = ~15,9 GB visti da Windows: non e' «sotto i 16»
        st = None if mn is None and rc is None else "min" if mn is not None and eff < mn else "rec" if rc is not None and eff < rc else "ok"
        out.append({"part": part, "have": have, "min": mn, "rec": rc, "status": st})
    return out


def verdict(ms: list[dict]) -> str:
    st = {m["status"] for m in ms}
    return ("insufficiente" if "min" in st else "impostazioni" if "rec" in st else "ok" if "ok" in st else "sconosciuto")


def verdict_console(plat: str, h: dict) -> dict | None:
    r = REQ.get(plat)
    if not r:
        return None
    cmin, gmin, rmin, crec, grec, rrec, tips = r
    ms = meters(h, (cmin, gmin, rmin), (crec, grec, rrec))
    v = verdict(ms)
    return {"verdict": v, "meters": ms, "note": None, "tips": tips if v != "ok" else [],
            "requirements": {"min": {"cpu": cmin, "gpu": gmin, "ram_gb": rmin},
                             "recommended": {"cpu": crec, "gpu": grec, "ram_gb": rrec}}}


# ---------- requisiti Steam ----------
FIELDS = {"cpu": r"processor|processore|cpu", "gpu": r"graphics|grafica|scheda video|video card|gpu",
          "ram_gb": r"memory|memoria|ram"}


def parse_req(html: str) -> dict:
    """HTML dei requisiti Steam -> {"cpu","gpu","ram_gb","raw"} (campi mancanti = None)."""
    txt = re.sub(r"</?(?:br|li|p)\s*/?>", "\n", html or "", flags=re.I)
    txt = re.sub(r"<[^>]+>", "", txt).replace("&nbsp;", " ").replace("&amp;", "&")
    out = {"cpu": None, "gpu": None, "ram_gb": None, "raw": txt.strip()}
    for line in txt.splitlines():
        for k, pat in FIELDS.items():
            m = re.match(rf"\s*(?:{pat})\s*:\s*(.+)", line, re.I)
            if not m or out[k] is not None:
                continue
            if k == "ram_gb":
                q = re.search(r"(\d+(?:[.,]\d+)?)\s*(gb|mb)", m[1], re.I)
                if q:
                    v = float(q[1].replace(",", "."))
                    out[k] = v / 1024 if q[2].lower() == "mb" else v
            else:
                out[k] = m[1].strip()
    return out


def text_tier(fn, text: str | None) -> int | None:
    """Tier piu' basso tra le alternative 'A / B' riconosciute."""
    ts = [t for part in re.split(r"/|\bor\b|\bo\b|,", text or "", flags=re.I) for t, ok in [fn(part)] if ok]
    return min(ts) if ts else None


def steam_reqs(appid: str, cache: Path) -> dict | None:
    try:
        data = json.loads(cache.read_text("utf-8"))
    except Exception:
        data = {}
    e = data.get(appid)
    if not e or time.time() - e["t"] > TTL:
        try:
            r = httpx.get("https://store.steampowered.com/api/appdetails",
                          params={"appids": appid, "l": "italian"}, timeout=15).json()[appid]
        except Exception:
            return e["d"] if e else None
        pc = (r.get("data") or {}).get("pc_requirements") if r.get("success") else None
        pc = pc if isinstance(pc, dict) else {}
        e = data[appid] = {"t": time.time(), "d": {"min": pc.get("minimum", ""), "rec": pc.get("recommended", "")}}
        cache.write_text(json.dumps(data), "utf-8")
    return e["d"]


def verdict_steam(raw: dict, h: dict) -> dict:
    mn, rc = parse_req(raw.get("min", "")), parse_req(raw.get("rec", ""))
    need = lambda q: (text_tier(cpu_tier, q["cpu"]), text_tier(gpu_tier, q["gpu"]), q["ram_gb"])  # noqa: E731
    ms = meters(h, need(mn), need(rc))
    v = verdict(ms)
    return {"verdict": v, "meters": ms, "note": "unparsed" if v == "sconosciuto" else None,
            "tips": ["lowgfx", "noshadows"] if v == "impostazioni" else [], "requirements": {"minimum": mn, "recommended": rc}}


def check(db: sqlite3.Connection, gid: int, cache: Path) -> dict | None:
    row = db.execute("SELECT platform, store, page FROM games WHERE id=?", (gid,)).fetchone()
    if not row:
        return None
    plat, store, page = row
    h = hw()
    res = verdict_console(plat, h)
    if res is None:
        m = re.search(r"/app/(\d+)", page or "")
        raw = steam_reqs(m[1], cache) if m and store == "steam" else None
        res = verdict_steam(raw, h) if raw else {"verdict": "sconosciuto", "meters": meters(h, (None,) * 3, (None,) * 3),
                                                 "tips": [], "requirements": {}, "note": "noreq"}
    if h["incerto"] and res["verdict"] != "sconosciuto":
        res["note"] = "uncertain"
    return {**res, "hw": h}


def register(gs):
    db_path = Path(gs.cfg.cache) / "library.db"
    cache = Path(gs.cfg.cache) / "pc-adatto.json"

    @gs.route("hw")
    def hw_route():
        return hw()

    @gs.route("check/{game_id}")
    def check_route(game_id: int):
        if not db_path.exists():
            raise HTTPException(404, gs.t("err.lib"))
        db = sqlite3.connect(db_path)
        try:
            r = check(db, game_id, cache)
        finally:
            db.close()
        if r is None:
            raise HTTPException(404, gs.t("err.game"))
        return r
