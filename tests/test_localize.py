"""Regioni e lingue preferite per copertine e Wikipedia (pozzo/localize.py) e pulizia del titolo per la ricerca web.

Esegui: python tests/test_localize.py
"""
import os
import sys
from types import SimpleNamespace as N

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pozzo.localize import regions_for, wiki_langs  # noqa: E402
from pozzo.sources.wikipedia import EDITION, NOT_COVER, Wikipedia  # noqa: E402

CFG = N(languages=["it", "en"], regions=["eu", "us", "wor", "jp"])


def test_regioni():
    assert regions_for(N(stem="Zelda"), CFG)[:2] == ["it", "eu"], "senza tag: la lingua dell'utente prima"
    assert regions_for(N(stem="Zelda (Europe)"), CFG)[:2] == ["it", "eu"], "Europe non dice l'edizione"
    assert regions_for(N(stem="Zelda (USA)"), CFG)[0] == "us", "una regione sola: la sua edizione"
    assert regions_for(N(stem="Zelda (Germany)"), CFG)[0] == "de"
    assert regions_for(N(stem="Zelda"), N(languages=["en"], regions=["eu"])) == ["eu"], "solo inglese: internazionale"


def test_lingue_wikipedia():
    assert wiki_langs(N(stem="A (Germany)"), CFG, ["it", "en", "de"]) == ["de", "it", "en"]
    assert wiki_langs(N(stem="A"), CFG, ["it", "en"]) == ["it", "en"]
    assert wiki_langs(N(stem="A (Brazil)"), CFG, ["it", "en"]) == ["it", "en"], "lingua senza wiki supportata: si salta"


def test_titolo_e_immagini():
    assert EDITION.sub("", "Hades Game of the Year Edition v1.2") == "Hades"
    assert EDITION.sub("", "Resident Evil 4 - Deluxe Edition") == "Resident Evil 4"
    assert EDITION.sub("", "Edition Zero") == "Edition Zero"
    assert Wikipedia._name(N(search_name="Doom Eternal v2.1")) == "Doom Eternal"
    assert NOT_COVER.search("Super_Mario_Sunshine_Logo.png") and NOT_COVER.search("x/Super_Metroid_title.png")
    assert NOT_COVER.search("x.svg") and not NOT_COVER.search("Super_Mario_Sunshine.png")


if __name__ == "__main__":
    test_regioni()
    test_lingue_wikipedia()
    test_titolo_e_immagini()
    print("TUTTI I TEST OK")
