"""Estensione «Link → Store»: da una pagina che raccoglie altri siti agli store dell'app.

Endpoint (sotto /plugin-api/linkstores/):
    GET  state   console disponibili, store già configurati
    POST scan    {url, external_only} -> link raggruppati per intestazione (h2/h3)
    POST add     {url, platform, kind} -> aggiunge lo store (PC repack/direct oppure console)
"""

from fastapi import Body, HTTPException


def register(gs):
    from pozzo import catalog, platforms as P
    from pozzo.cache import Cache
    from pozzo.config import read_settings
    from pozzo.linklist import add_store, scan_page
    from pozzo.net import make_client

    def platforms_list() -> list[dict]:
        out = [{"id": pid, "name": getattr(pl, "name", pid), "pc": pid == "windows"}
               for pid, pl in P.PLATFORMS.items()]
        out.sort(key=lambda p: (not p["pc"], p["name"].lower()))
        return out

    def configured() -> tuple[dict, list]:
        s = read_settings(gs.cfg)
        catalogs: dict[str, list[str]] = {}
        for pid, value in (s.get("catalogs") or {}).items():
            urls = value.get("urls") if isinstance(value, dict) else value
            if urls:
                catalogs[pid] = [str(u) for u in urls]
        pc = [{"url": str(it.get("url") or ""), "kind": str(it.get("kind") or "direct")}
              for it in (s.get("pc_stores") or []) if isinstance(it, dict) and it.get("url")]
        return catalogs, pc

    @gs.route("state")
    def state():
        catalogs, pc = configured()
        return {"platforms": platforms_list(), "catalogs": catalogs, "pc_stores": pc}

    @gs.route("scan", methods=["POST"])
    async def scan(body: dict = Body(...)):
        url = str(body.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            raise HTTPException(400, gs.t("err.url"))
        cache = Cache(gs.cfg.cache)
        try:
            async with make_client() as client:
                page = await catalog._get_page(gs.cfg, cache, client, "windows", url, log=lambda m: None)
        except Exception as e:
            raise HTTPException(502, gs.t("err.page", errore=f"{type(e).__name__}: {e}"))
        finally:
            cache.close()
        return scan_page(page, url, external_only=bool(body.get("external_only", True)))

    @gs.route("add", methods=["POST"])
    def add(body: dict = Body(...)):
        url, platform = str(body.get("url") or "").strip(), str(body.get("platform") or "windows")
        if not url.startswith(("http://", "https://")):
            raise HTTPException(400, gs.t("err.url"))
        try:
            result = add_store(gs.cfg, url, platform, str(body.get("kind") or "direct"))
        except ValueError:  # l'indirizzo e' gia' controllato: resta la console sconosciuta
            raise HTTPException(400, gs.t("err.console", console=platform))
        result["state"] = state()
        return result
