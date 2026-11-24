"""Edizione localizzata di un gioco: quali regioni e lingue preferire per copertine e pagine Wikipedia.

Regola: se il file dichiara una regione sola (USA, Japan...) vale la sua edizione. Se e' «Europe»/«World» o non dice
nulla, si preferisce l'edizione nella lingua dell'utente (cfg.languages); solo dopo quella internazionale.
Le sorgenti ripiegano comunque sull'edizione internazionale se la localizzata non esiste.
"""

from __future__ import annotations

from .scanner import regions_of

# lingua dell'interfaccia -> codice regione delle sorgenti (ScreenScraper: it, fr, de, sp, br)
LANG_REGION = {"it": "it", "fr": "fr", "de": "de", "es": "sp", "pt-BR": "br", "pt": "br"}
# regione del file -> lingua della versione di Wikipedia dove cercare per prima
REGION_LANG = {"it": "it", "fr": "fr", "de": "de", "sp": "es", "br": "pt"}
BROAD = {"eu", "wor"}  # regioni multi-lingua: non dicono quale edizione sia


def regions_for(game, cfg) -> list[str]:
    own = regions_of(game.stem)
    local = [LANG_REGION[x] for x in (getattr(cfg, "languages", None) or []) if x in LANG_REGION]
    narrow = [r for r in own if r not in BROAD]
    order = narrow + (local if not narrow else []) + own + list(cfg.regions)
    return list(dict.fromkeys(order))


def wiki_langs(game, cfg, available) -> list[str]:
    """Versioni di Wikipedia da provare, in ordine: lingua del file, lingue dell'utente, inglese."""
    own = [REGION_LANG[r] for r in regions_of(game.stem) if r in REGION_LANG]
    order = own + list(getattr(cfg, "languages", None) or ["it", "en"]) + ["en"]
    return [x for x in dict.fromkeys(order) if x in available]
