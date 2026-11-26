"""Riduci spazio su disco: compressione WOF di un gioco PC installato, di una ROM o di tutte le ROM di una console."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException

from ... import i18n as I, platforms as P, ports as PT
from ...cache import Cache
from ...library import wof as W


def build_router(ctx) -> APIRouter:
    cfg, lib = ctx.cfg, ctx.lib
    router = APIRouter()
    jobs: dict[tuple, W.Job] = {}  # un lavoro per gioco o console; l'ultimo resta consultabile finche' non ne parte un altro

    checks: dict[tuple, dict] = {}  # (kind, ref, libreria) -> misura: il menu la chiede ogni volta che si apre

    def on_ntfs(paths) -> list:
        vol = {a: W.filesystem(a) in ("", "NTFS") for a in {Path(p).anchor for p in paths}}
        if not (ok := [p for p in paths if vol[Path(p).anchor]]):
            raise HTTPException(400, I.tr("s.wof.noNtfs"))
        return ok

    def target_of(kind: str, ref: str):
        """(cartella del gioco PC, None) oppure (None, file delle ROM)."""
        if kind == "game" and ref.isdecimal():
            g = lib.game(int(ref))  # install_dir non sta in memoria: con lib.get() e' sempre None
            if g.get("store"):
                # «manual»: la cartella puo' essere il Desktop o una di programmi, non e' solo del gioco
                d = Path(g["install_dir"]) if g.get("install_dir") and g["store"] not in ("online", "manual") else None
                if not W.supported() or not d or not d.is_dir():
                    raise HTTPException(400, I.tr("s.wof.unavailable"))
                return on_ntfs([d])[0], None
            paths = g["files"]
        elif kind == "platform":
            paths = [f for g in lib.games if g["platform"] == ref and not g.get("store") for f in g["files"]]
        else:
            raise HTTPException(404, I.tr("s.wof.unavailable"))
        files = W.rom_files(paths) if sys.platform == "win32" else []
        if not files:
            raise HTTPException(400, I.tr("s.wof.unavailable"))
        files = [f for f in files if Path(f).suffix.lower() not in W.PACKED]
        if not files:
            raise HTTPException(400, I.tr("s.wof.packed"))
        return None, on_ntfs(files)

    def measure(kind: str, ref: str) -> dict:
        """Quanto occupa, quanto si puo' ancora risparmiare (gain) e se c'e' qualcosa da decomprimere (undo)."""
        key = (kind, ref, lib.built_at)
        running = any(j.status == "running" for j in jobs.values())
        if not running and key in checks:
            return checks[key]
        d, files = target_of(kind, ref)
        all_files = files if files is not None else W.tree_files(d)
        (size, disk), est = W.sizes(all_files), None
        if d:
            c = Cache(cfg.cache)
            try:
                est = W.estimate(lib.get(int(ref))["title"], size, W.load_index(c))
            except Exception:  # offline o database illeggibile: resta la stima a campioni
                pass
            finally:
                c.close()
        after = size - max(est["savings"].values()) if est else round(size * W.sample_ratio(all_files))
        saved = max(0, disk - after)
        out = {"dir": d, "files": files, "count": len(all_files), "size": size, "disk": disk, "estimate": est,
               "sampled": None if est else saved, "gain": saved > size * W.MIN_GAIN, "undo": disk < size * 0.98}
        if not running:  # durante un lavoro i numeri cambiano
            checks[key] = out
        return out

    @router.get("/api/wof/{kind}/{ref}")
    def api_wof(kind: str, ref: str):
        m = dict(measure(kind, ref))
        d, files = m.pop("dir"), m.pop("files")
        if d:
            name = str(d)
        elif kind == "platform":
            name = P.PLATFORMS[ref].name if ref in P.PLATFORMS else ref
        else:
            name = files[0]
        j = jobs.get((kind, ref))
        return {**m, "folder": name, "dstorage": bool(d) and W.has_dstorage(d), "algos": W.ALGOS, "default": W.DEFAULT_ALGO,
                "blocked": "" if m["gain"] else I.tr("s.wof.noGain"), "job": j.state() if j else None}

    @router.get("/api/wof/{kind}/{ref}/check")
    def api_wof_check(kind: str, ref: str):
        """Per il menu: la voce e' attiva solo se c'e' spazio da guadagnare, qualcosa da decomprimere o un lavoro in corso."""
        if (j := jobs.get((kind, ref))) and j.status == "running":
            return {"ok": True, "reason": ""}
        try:
            m = measure(kind, ref)
        except HTTPException as e:
            return {"ok": False, "reason": e.detail}
        ok = m["gain"] or m["undo"]
        return {"ok": ok, "reason": "" if ok else I.tr("s.wof.noGain")}

    @router.post("/api/wof/{kind}/{ref}")
    def api_wof_start(kind: str, ref: str, body: dict = Body(default={})):
        d, files = target_of(kind, ref)
        if any(j.status == "running" for j in jobs.values()):  # uno alla volta: gioco e console si sovrappongono
            raise HTTPException(409, I.tr("s.wof.busy"))
        if sys.platform == "darwin" and PT._running(d):  # macOS riscrive la cartella: salvataggi scritti ora andrebbero persi
            raise HTTPException(409, I.tr("s.wof.closeFirst"))
        undo = body.get("action") == "uncompress"
        algo = body.get("algo") or W.DEFAULT_ALGO
        if not undo and algo not in W.ALGOS:
            raise HTTPException(400, I.tr("s.wof.badAlgo"))
        if not undo and d and W.has_dstorage(d) and not body.get("confirm_dstorage"):
            raise HTTPException(409, I.tr("s.wof.dstorage"))
        if not undo and not measure(kind, ref)["gain"]:
            raise HTTPException(400, I.tr("s.wof.noGain"))
        checks.clear()
        job = jobs[kind, ref] = W.Job(files if files is not None else d, algo, undo)
        return job.state()

    @router.get("/api/wof/{kind}/{ref}/job")
    def api_wof_job(kind: str, ref: str):
        j = jobs.get((kind, ref))
        return j.state() if j else {"status": "idle", "done": 0, "total": 0, "error": ""}

    @router.delete("/api/wof/{kind}/{ref}")
    def api_wof_cancel(kind: str, ref: str):
        if j := jobs.get((kind, ref)):
            j.cancel()
        return {"ok": True}

    return router
