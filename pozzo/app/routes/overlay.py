"""Overlay in gioco: pagine, stato e impostazioni (la finestra e' in pozzo/overlay.py)."""

from __future__ import annotations

import threading
import time

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import HTMLResponse

from ... import config as C, i18n as I
from ... import overlay as OV
from ...emuadapters import retroarch as RA
from ..assets import STATIC, _asset_version


def _timing(run: dict) -> dict:
    started = run.get("started")
    paused = bool(run.get("paused", False))
    paused_total = float(run.get("paused_total") or 0.0)
    if started:
        elapsed = max(0.0, time.time() - float(started) - paused_total)
    else:
        elapsed = 0.0
    return {"started": started, "paused": paused, "paused_total": paused_total, "elapsed": elapsed}


def build_router(ctx) -> APIRouter:
    cfg, launcher, lib, ov = ctx.cfg, ctx.launcher, ctx.lib, ctx.overlay
    router = APIRouter()
    cpu_cache: dict = {"ts": None, "val": 0}
    cpu_lock = threading.Lock()

    def _page(name: str) -> HTMLResponse:
        html = (STATIC / name).read_text(encoding="utf-8").replace("{{v}}", _asset_version())
        return HTMLResponse(html, headers={"Cache-Control": "no-cache"})

    @router.get("/overlay")
    def overlay_page():
        return _page("overlay.html")

    @router.get("/overlay/toast")
    def overlay_toast_page():
        return _page("overlay-toast.html")

    @router.get("/overlay/hud")
    def overlay_hud_page():
        return _page("overlay-hud.html")

    def _ra(run):
        """RetroArch in esecuzione: (exe, comandi di rete attivi), altrimenti None. Gli altri emulatori non hanno comandi (v1)."""
        if run.get("status") != "running" or run.get("emulator_id") != RA.NAME or not run.get("exe"):
            return None
        return run["exe"], RA.net_ready(run["exe"])

    @router.get("/api/overlay/state")
    def api_overlay_state():
        run = launcher.running()
        g = lib.by_key.get(run.get("key") or "")
        ra = _ra(run)
        return {**_timing(run), "running": run.get("status") == "running", "gid": g["id"] if g else None,
                "title": (g or {}).get("title") or run.get("title") or "",
                "emu": {"id": RA.NAME, "ready": ra[1]} if ra else None, "settings": OV.settings(cfg)}

    @router.get("/api/overlay/stats")
    def api_overlay_stats():
        import psutil
        now = time.monotonic()
        with cpu_lock:
            if cpu_cache["ts"] is None or now - cpu_cache["ts"] >= 1.0:
                cpu_cache["val"] = round(psutil.cpu_percent(interval=None))
                cpu_cache["ts"] = now
            cpu = cpu_cache["val"]
        b = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None  # None su un PC fisso
        return {**_timing(launcher.running()),  # HUD e scheda Prestazioni condividono il campione CPU (~1 s)
                "cpu": cpu, "ram": round(psutil.virtual_memory().percent),
                "battery": {"percent": round(b.percent), "plugged": bool(b.power_plugged)} if b else None}

    @router.post("/api/overlay/screenshot")
    def api_overlay_screenshot():
        was = ov.visible
        if was:  # nasconde l'overlay prima dello scatto per catturare il gioco e non l'overlay stesso
            ov.hide(refocus=True)
            time.sleep(0.15)
        try:
            ok = launcher.screenshot()
        finally:
            if was:
                ov.show()
        return {"ok": bool(ok)}

    @router.post("/api/overlay/pause")
    def api_overlay_pause():
        ok = launcher.pause(focus_launcher=False)
        return {"ok": bool(ok)}

    @router.post("/api/overlay/resume")
    def api_overlay_resume():
        ok = launcher.resume()
        if ok:
            ov.hide(refocus=True)
        return {"ok": bool(ok)}

    @router.post("/api/overlay/emu")
    def api_overlay_emu(body: dict = Body(...)):
        ra = _ra(launcher.running())
        if not ra:
            raise HTTPException(409, I.tr("o.overlay.emuNone"))
        if not ra[1]:
            raise HTTPException(409, I.tr("o.overlay.emuOff"))
        if not RA.command(ra[0], body.get("action")):
            raise HTTPException(400, "action")
        return {"ok": True}

    @router.post("/api/overlay/toggle")
    def api_overlay_toggle():
        return {"ok": ov.toggle()}

    @router.post("/api/overlay/hide")
    def api_overlay_hide():
        return {"ok": ov.hide()}

    @router.post("/api/overlay/settings")
    def api_overlay_settings(body: dict = Body(...)):
        prev = OV.settings(cfg)
        try:
            cur = OV.clean(body, prev)
        except ValueError as e:
            err_keys = {"hotkey": "s.shots.hotkeyInvalid", "sound": "o.overlay.soundInvalid",
                        "hud_corner": "o.overlay.cornerInvalid"}
            raise HTTPException(400, I.tr(err_keys.get(str(e), "s.appsettings.choiceInvalid")))
        C.save_settings(cfg, app={"overlay": cur})
        cfg.app["overlay"] = cur
        ov.apply_hud()
        if cur.get("hotkey") != prev.get("hotkey"):
            ov.reload_hotkey()
        return {"settings": cur}

    return router
