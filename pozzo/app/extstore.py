"""Store delle estensioni: elenco da una o piu' fonti, installazione e rimozione nella cartella plugin dell'utente.

Una FONTE e' un `index.json` raggiungibile da un link. Lo stesso formato serve a tre casi:

    {"extensions": [{"id", "name", "version", "description", "author", "min_app",
                     "base": "./",                       # cartella dei file, relativa all'indice (o URL assoluto)
                     "files": {"plugin.toml": "<sha256>", ...}}],
     "repos": [{"repo": "utente/repo", "ref": "v1.0"},  # store: estensioni che vivono in altri repository
               {"url": "https://.../index.json"}]}

  - repository di un'estensione: un solo elemento in "extensions", con base "./";
  - store: un elenco di "repos", ognuno col proprio index.json (al tag indicato, cosi' lo store approva una versione);
  - indice classico: piu' elementi in "extensions" (extensions/index.json del repository dell'app).

Si installano solo file elencati nell'indice e solo se TUTTI hanno lo sha256 giusto: un backend.py gira con i permessi
dell'app, quindi niente file non dichiarati, niente sottocartelle, niente hash sbagliati.

Fonti: la prima e' sempre lo store ufficiale (OFFICIAL); le altre le aggiunge l'utente con un link GitHub o all'index.json
(app.extensions_sources in settings.json). app.extensions_index sostituisce lo store ufficiale, anche con un percorso
locale, per provare le estensioni prima del push.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from urllib.parse import urljoin

import httpx

from .. import __version__
from ..updates import parse
from . import extensions as X

STORE_ID = X.STORE_ID  # lo store stesso: incluso nell'app, non si disattiva ne' si rimuove
# lo store ufficiale e' un repository a parte, con index.json alla radice e una cartella per estensione
# (sorgenti in extensions/ di questo repository; si ripubblica copiando i file elencati nell'indice)
OFFICIAL = "https://raw.githubusercontent.com/erpaffo/pozzo-store-extension/HEAD/index.json"
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_FILE = re.compile(r"^[A-Za-z0-9_-][A-Za-z0-9_.-]{0,99}$")
_GITHUB = re.compile(r"^https://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?(?:/tree/([\w./-]+?))?/?$")
_REPO = re.compile(r"^[\w.-]+/[\w.-]+$")
_REF = re.compile(r"^[\w./-]{1,100}$")
MAX_FILE = 5 * 1024 * 1024
MAX_SOURCES = 20
MAX_REPOS = 200


def raw_index(repo: str, ref: str = "HEAD") -> str:
    return f"https://raw.githubusercontent.com/{repo}/{ref}/index.json"


def index_link(link: str) -> str:
    """Indirizzo dell'index.json di un link: repository GitHub (anche /tree/<ref>) oppure un .json diretto (https)."""
    link = link.strip()
    m = _GITHUB.match(link)
    if m:
        return raw_index(f"{m.group(1)}/{m.group(2)}", m.group(3) or "HEAD")
    if link.startswith("https://") and link.split("?")[0].endswith(".json"):
        return link
    raise ValueError("link non valido: serve un repository GitHub (https://github.com/utente/repo) "
                     "o l'indirizzo https di un index.json")


def release_index() -> str:
    """Estensioni uscite insieme a questa versione dell'app (extensions/index.json al suo tag)."""
    from ..updates import REPO
    return f"https://raw.githubusercontent.com/{REPO}/v{__version__}/extensions/index.json"


def sources(cfg) -> list[dict]:
    """Fonti in ordine: lo store ufficiale (o quello di prova), le estensioni della release, poi quelle dell'utente."""
    first = cfg.app.get("extensions_index") or OFFICIAL
    out = [{"link": first, "official": True}]
    if first == OFFICIAL:  # lo store e' un repository a parte e puo' restare indietro rispetto all'app
        out.append({"link": release_index(), "official": True, "release": True})
    links = {s["link"] for s in out}
    out += [{"link": s, "official": False} for s in cfg.app.get("extensions_sources") or [] if s not in links]
    return out


def _get(url: str) -> bytes:
    if not url.startswith(("http://", "https://")):
        return Path(url).read_bytes()
    # indice e file sono codice che girera': in chiaro chiunque sulla rete potrebbe sostituirli (sha256 compresi)
    if not url.startswith("https://"):
        raise ValueError(f"serve un indirizzo https: {url}")
    with httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": f"PozzoLauncher/{__version__}"}) as c:
        r = c.get(url)
        if r.url.scheme != "https":  # redirect verso http
            raise ValueError(f"serve un indirizzo https: {r.url}")
        r.raise_for_status()
        if len(r.content) > MAX_FILE:
            raise ValueError(f"file troppo grande: {url}")
        return r.content


def _join(base: str, rel: str) -> str:
    """Come urljoin, anche per un indice su disco: `rel` e' relativo alla cartella di `base`."""
    if base.startswith(("http://", "https://")) or rel.startswith(("http://", "https://")):
        return urljoin(base, rel)
    b = Path(base) if base.endswith(("/", "\\")) else Path(base).parent
    return str(b / rel) + ("/" if rel.endswith("/") else "")


def _entries(data: dict, url: str, pinned: bool = True) -> list[dict]:
    """pinned: gli sha256 dei file sono fissati dalla fonte stessa (non da un indice che il suo autore puo' cambiare)."""
    out = []
    for e in data.get("extensions") or []:
        if isinstance(e, dict) and _ID.match(str(e.get("id", ""))) and e["id"] != STORE_ID and isinstance(e.get("files"), dict):
            out.append({**e, "base": _join(url, str(e.get("base") or e["id"] + "/")), "pinned": pinned})
    return out


def fetch_source(link: str) -> tuple[list[dict], list[str]]:
    """(estensioni, errori) di una fonte. Le voci "repos" di uno store si seguono un livello solo: un repository
    irraggiungibile non toglie gli altri, finisce negli errori."""
    url = link if not link.startswith("https://") else index_link(link)
    data = json.loads(_get(url))
    if not isinstance(data, dict):
        raise ValueError("indice non valido")
    out, errors = _entries(data, url), []
    for r in (data.get("repos") or [])[:MAX_REPOS]:
        try:
            if not isinstance(r, dict):
                raise ValueError("voce non valida")
            if r.get("url"):
                sub = str(r["url"])
                sub = sub if not sub.startswith(("http://", "https://")) else index_link(sub)
                if not sub.startswith(("http://", "https://")):
                    sub = _join(url, sub)  # percorso relativo allo store (indice su disco o sullo stesso sito)
            elif _REPO.match(str(r.get("repo", ""))) and _REF.match(str(r.get("ref") or "HEAD")):
                sub = raw_index(r["repo"], r.get("ref") or "HEAD")
            else:
                raise ValueError("voce senza repo o url")
            raw = _get(sub)
            # lo store fissa l'indice del repository col suo sha256: un tag spostato o un url cambiato non passa
            pin = str(r.get("sha256") or "").lower()
            if pin and hashlib.sha256(raw).hexdigest() != pin:
                raise ValueError("index.json diverso da quello approvato dallo store (sha256)")
            out += _entries(json.loads(raw), sub, pinned=bool(pin))
        except Exception as e:
            errors.append(f"{r.get('repo') or r.get('url') if isinstance(r, dict) else r}: {e}")
    return out, errors


def fetch_all(cfg) -> tuple[list[dict], list[dict]]:
    """Estensioni di tutte le fonti (a parita' di id vince la prima fonte, cioe' lo store ufficiale) e stato delle fonti."""
    items, seen, report = [], {}, []
    for s in sources(cfg):
        try:
            found, errors = fetch_source(s["link"])
        except Exception as e:
            found, errors = [], [f"{type(e).__name__}: {e}"]
        for e in found:
            e = {**e, "source": s["link"], "official": s["official"]}
            if e["id"] not in seen:
                seen[e["id"]] = len(items)
                items.append(e)
            else:  # tra le fonti ufficiali vince la versione piu' nuova (store o release); una di terzi non scavalca mai
                prev = items[seen[e["id"]]]
                if s["official"] and prev["official"] and compatible(e) and _ver(e.get("version")) > _ver(prev.get("version")):
                    items[seen[e["id"]]] = e
        report.append({**s, "count": len(found), "errors": errors})
    return items, report


def is_linked(d: Path) -> bool:
    """Cartella collegata (symlink o junction) ai sorgenti: e' la copia di sviluppo, lo store non la tocca."""
    return d.is_symlink() or (hasattr(d, "is_junction") and d.is_junction())


def compatible(e: dict) -> bool:
    return parse(str(e.get("min_app") or "0")) <= parse(__version__)


def _ver(v) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", str(v or ""))) or (0,)


def catalog(cfg) -> dict:
    """Estensioni delle fonti con lo stato rispetto a quelle installate."""
    installed = {p["id"]: p for p in X.list_plugins(cfg)}
    found, report = fetch_all(cfg)
    items = []
    repo_ext = Path(__file__).resolve().parent.parent.parent / "extensions"
    for e in found:
        p = installed.get(e["id"])
        d = Path(p["dir"]) if p else None
        state = ("incompatible" if not compatible(e) and not p
                 else "available" if not p
                 else "update" if _ver(e.get("version")) > _ver(p["version"]) and compatible(e)
                 else "installed")
        m = {}
        if repo_ext.is_dir() and (repo_ext / e["id"] / "plugin.toml").exists():
            try:
                import tomllib
                m = tomllib.loads((repo_ext / e["id"] / "plugin.toml").read_text(encoding="utf-8")).get("plugin", {})
            except Exception:
                pass
        item = {k: e.get(k) or m.get(k) for k in ("id", "name", "version", "description", "author", "min_app", "source", "official",
                                                  "icon", "screenshot", "screenshots", "long_description", "how_it_works", "features", "base", "featured")}
        # testi nella lingua dell'interfaccia: dall'indice (i18n) o, se c'e', dal locales.json della copia locale
        tr = X.pick_lang(e["i18n"], X.ext_lang()) if isinstance(e.get("i18n"), dict) else {}
        if not tr and (repo_ext / e["id"]).is_dir():
            loc = X.pick_lang(X.ext_locales(repo_ext / e["id"]), X.ext_lang())
            tr = {k: loc[f"plugin.{k}"] for k in ("name", "description", "long_description", "how_it_works", "features")
                  if isinstance(loc.get(f"plugin.{k}"), str)}
            if "features" in tr:
                tr["features"] = [x for x in tr["features"].split("\n") if x.strip()]
        item.update({k: v for k, v in tr.items() if v})
        raw = e["permissions"] if "permissions" in e else m.get("permissions")  # l'indice verificato prima del repository locale
        perms = [x for x in raw if isinstance(x, str)] if isinstance(raw, list) else []
        item.update({"permissions": perms, "permissions_unknown": raw is None,
                     "permissions_labels": X.describe_permissions(perms)})
        item["files"] = list(e.get("files", {}).keys()) if isinstance(e.get("files"), dict) else []
        # permessi della versione installata: l'aggiornamento chiede conferma solo per quelli nuovi
        item["installed_permissions"] = p["permissions"] if p and not p["permissions_unknown"] else None
        item.update({"state": state, "installed_version": p["version"] if p else None,
                     "dev": bool(d and is_linked(d)), "enabled": bool(p and p["enabled"])})
        items.append(item)
    return {"items": items, "sources": report, "app_version": __version__}


def add_source(cfg, link: str) -> list[str]:
    """Aggiunge una fonte (repository di un'estensione o altro store) dopo aver controllato che risponda."""
    from .. import config as C
    url = index_link(link)
    found, _ = fetch_source(link.strip())
    if not found:
        raise ValueError("a quel link non ci sono estensioni (index.json vuoto o senza estensioni valide)")
    cur = list(cfg.app.get("extensions_sources") or [])
    link = link.strip().rstrip("/")
    if link in cur or url in (index_link(s) for s in cur if s.startswith("https://")) or link == OFFICIAL:
        raise ValueError("fonte gia' presente")
    if len(cur) >= MAX_SOURCES:
        raise ValueError(f"al massimo {MAX_SOURCES} fonti")
    cur.append(link)
    C.save_settings(cfg, app={"extensions_sources": cur})
    cfg.app["extensions_sources"] = cur
    return cur


def remove_source(cfg, link: str) -> list[str]:
    from .. import config as C
    cur = [s for s in cfg.app.get("extensions_sources") or [] if s != link]
    if len(cur) == len(cfg.app.get("extensions_sources") or []):
        raise ValueError("fonte non trovata (lo store ufficiale non si rimuove)")
    C.save_settings(cfg, app={"extensions_sources": cur})
    cfg.app["extensions_sources"] = cur
    return cur


def install(cfg, ext_id: str, source: str | None = None) -> dict:
    if source and source not in (s["link"] for s in sources(cfg)):
        raise ValueError("fonte sconosciuta: aggiungila prima allo store")
    found, report = (fetch_source(source)[0], []) if source else fetch_all(cfg)
    e = next((x for x in found if x["id"] == ext_id), None)
    # store ufficiale irraggiungibile: una fonte di terzi non deve prendere il posto di un'estensione gia' nota
    if e and not source and not e.get("official") and any(r["official"] and not r.get("release") and r["errors"] for r in report)             and any(p["id"] == ext_id for p in X.list_plugins(cfg)):
        raise ValueError("store ufficiale non raggiungibile: non installo/aggiorno questa estensione da una fonte di terzi")
    if e is None:
        raise ValueError(f"estensione non trovata nelle fonti: {ext_id}")
    if not compatible(e):
        raise ValueError(f"«{e.get('name', ext_id)}» richiede PozzoLauncher {e['min_app']} o successivo (hai {__version__})")
    files = e["files"]
    if "plugin.toml" not in files or not all(_FILE.match(str(n)) for n in files):
        raise ValueError("indice non valido: nomi di file non ammessi o plugin.toml mancante")
    root = X.user_dir(cfg, "plugins")
    dest = root / ext_id
    if is_linked(dest):
        raise ValueError("questa estensione e' collegata alla cartella di sviluppo: aggiornala da li'")
    # tutto in memoria e verificato prima di toccare il disco: un file sbagliato non lascia un'installazione a meta'
    blobs = {}
    for name, sha in files.items():
        b = _get(_join(e["base"], name))
        if hashlib.sha256(b).hexdigest() != str(sha).lower():
            raise ValueError(f"{name}: il contenuto non corrisponde all'indice (sha256 diverso), installazione annullata")
        blobs[name] = b
    tmp, old = root / f".{ext_id}.tmp", root / f".{ext_id}.old"
    for d in (tmp, old):
        shutil.rmtree(d, ignore_errors=True)
    tmp.mkdir()
    for name, b in blobs.items():
        (tmp / name).write_bytes(b)
    if dest.exists():
        dest.rename(old)
    tmp.rename(dest)
    shutil.rmtree(old, ignore_errors=True)
    return {"ok": True, "id": ext_id, "version": e.get("version"), "restart": True}


def auto_update(cfg, log=print) -> list[str]:
    """Aggiorna da sole le estensioni installate quando una fonte ufficiale (store o release dell'app) ne ha una
    versione piu' nuova. Una versione che chiede permessi nuovi aspetta la conferma nello store. Solo voci "pinned": codice
    che gira senza che nessuno lo guardi deve essere quello approvato dallo store, non l'ultimo pubblicato dall'autore.
    Restituisce gli id aggiornati."""
    if not cfg.app.get("extensions_auto_update", True):
        return []
    plugins = X.user_dir(cfg, "plugins")
    installed = {p["id"]: p for p in X.list_plugins(cfg) if Path(p["dir"]).parent == plugins and not is_linked(Path(p["dir"]))}
    found, _ = fetch_all(cfg)
    done = []
    for e in found:
        p = installed.get(e["id"])
        if not p or not e.get("official") or not e.get("pinned") or not compatible(e) or _ver(e.get("version")) <= _ver(p["version"]):
            continue
        perms = e.get("permissions")
        new_perms = set(perms if isinstance(perms, list) else []) - set(p["permissions"] or [])
        if p["permissions_unknown"] or not isinstance(perms, list) or new_perms:
            log(f"Estensione {e['id']} {e.get('version')}: chiede permessi nuovi, aggiornala dallo store")
            continue
        try:
            install(cfg, e["id"], e["source"])
        except Exception as err:  # rete, sha256 diverso: si riprova al prossimo giro
            log(f"Estensione {e['id']}: aggiornamento automatico non riuscito: {err}")
            continue
        log(f"Estensione aggiornata da sola: {e['id']} {p['version']} -> {e.get('version')}")
        done.append(e["id"])
    return done


def remove(cfg, ext_id: str) -> dict:
    if ext_id == STORE_ID or not _ID.match(ext_id):
        raise ValueError("questa estensione non si puo' rimuovere")
    dest = X.user_dir(cfg, "plugins") / ext_id
    if is_linked(dest):
        raise ValueError("questa estensione e' collegata alla cartella di sviluppo: scollegala a mano")
    if not dest.is_dir():
        raise ValueError("estensione non installata")
    shutil.rmtree(dest)
    return {"ok": True, "id": ext_id, "restart": True}
