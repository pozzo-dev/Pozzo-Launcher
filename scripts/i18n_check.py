"""Controlla i cataloghi: stesse chiavi di it.json, stessi {segnaposto} e stessi tag HTML. Esce con 1 se c'e' qualcosa che non va."""
import json
import re
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parents[1] / "pozzo" / "data" / "locales"
ph = lambda s: sorted(re.findall(r"\{\w+\}", s))
tags = lambda s: sorted(re.findall(r"</?\w+", s))


def problems(only: str | None = None) -> list[str]:
    src = json.loads((DIR / "it.json").read_text(encoding="utf-8"))
    out = []
    for f in sorted(DIR.glob("*.json")):
        if f.stem == "it" or (only and f.stem != only):
            continue
        cat = json.loads(f.read_text(encoding="utf-8"))
        out += [f"{f.stem}: manca {k}" for k in src if k not in cat]
        out += [f"{f.stem}: chiave in piu' {k}" for k in cat if k not in src]
        for k, v in cat.items():
            if k in src and (not isinstance(v, str) or ph(v) != ph(src[k]) or tags(v) != tags(src[k])):
                out.append(f"{f.stem}: segnaposto/tag diversi in {k}")
    return out


def ext_problems(only: str | None = None, root: Path = DIR.parents[2] / "extensions") -> list[str]:
    """locales.json delle estensioni: ogni chiave dell'italiano in tutte le lingue dell'app, con gli stessi segnaposto."""
    langs = sorted(f.stem for f in DIR.glob("*.json"))
    out = []
    for f in sorted(root.glob("*/locales.json")):
        ext = f.parent.name
        try:
            loc = json.loads(f.read_text(encoding="utf-8"))
        except ValueError as e:
            out.append(f"{ext}: locales.json non valido ({e})")
            continue
        src = loc.get("it") or {}
        for lang in langs:
            if lang == "it" or (only and lang != only):
                continue
            cat = loc.get(lang) or {}
            out += [f"{ext}/{lang}: manca {k}" for k in src if k not in cat]
            out += [f"{ext}/{lang}: chiave in piu' {k}" for k in cat if k not in src]
            out += [f"{ext}/{lang}: segnaposto/tag diversi in {k}" for k, v in cat.items()
                    if k in src and (not isinstance(v, str) or ph(v) != ph(src[k]) or tags(v) != tags(src[k]))]
    return out


if __name__ == "__main__":
    bad = problems(sys.argv[1] if len(sys.argv) > 1 else None) + ext_problems(sys.argv[1] if len(sys.argv) > 1 else None)
    print("\n".join(bad) or "cataloghi ok")
    sys.exit(bool(bad))
