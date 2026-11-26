"""Traduzioni delle estensioni: locales.json, ricaduta en -> it, gs.t lato server, testi dello store nell'indice."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from pozzo import i18n as I
from pozzo.app import extensions as X
import extensions as T  # tools/extensions.py


def make(tmp: Path) -> Path:
    d = tmp / "prova"
    d.mkdir()
    (d / "plugin.toml").write_text('[plugin]\nname = "Prova"\nversion = "1.0"\ndescription = "Descrizione"\n', encoding="utf-8")
    (d / "locales.json").write_text(json.dumps({
        "it": {"ciao": "Ciao {nome}", "solo_it": "Solo it", "plugin.name": "Prova", "plugin.features": "Uno\nDue"},
        "en": {"ciao": "Hello {nome}", "solo_en": "Only en", "plugin.name": "Test", "plugin.description": "Describe"},
        "de": {"ciao": "Hallo {nome}"},
        "rotto": "non un dizionario",
    }), encoding="utf-8")
    return d


def test_ricadute():
    with tempfile.TemporaryDirectory() as t:
        d = make(Path(t))
        de = X.ext_strings(d, "de")
        assert de["ciao"] == "Hallo {nome}" and de["solo_en"] == "Only en" and de["solo_it"] == "Solo it"
        assert X.ext_strings(d, "it")["ciao"] == "Ciao {nome}"
        assert X.ext_strings(d, "fr")["ciao"] == "Hello {nome}"  # lingua mancante: inglese
        assert "rotto" not in X.ext_locales(d)
        (d / "locales.json").write_text("{rotto", encoding="utf-8")
        assert X.ext_strings(d, "en") == {}  # file rotto: nessun testo, l'estensione mostra le chiavi
        (d / "locales.json").unlink()
        assert X.ext_strings(d, "en") == {}
    print("ok  ricadute: lingua, inglese, italiano; file rotto o assente")


def test_api_t():
    with tempfile.TemporaryDirectory() as t:
        d = make(Path(t))
        old = X.plugin_dirs
        X.plugin_dirs = lambda cfg: [Path(t)]
        try:
            api = X.PluginAPI.__new__(X.PluginAPI)
            api.cfg, api.id = None, "prova"
            assert api.t("ciao", lang="de", nome="Ada") == "Hallo Ada"
            assert api.t("manca") == "manca"
            assert api.t("ciao", lang="en") == "Hello {nome}"  # senza parametri resta il segnaposto
            assert api.t("ciao", lang="en", altro=1) == "Hello {nome}"  # parametro sbagliato: niente eccezione
            # lavori in background: la lingua dell'ultima richiesta
            I.last = "de"
            assert api.t("ciao", nome="Bo") == "Hallo Bo"
            tok = I.current.set("en")
            try:
                assert api.t("ciao", nome="Bo") == "Hello Bo"
            finally:
                I.current.reset(tok)
        finally:
            X.plugin_dirs = old
            I.last = I.SOURCE
    print("ok  gs.t lato server: lingua della richiesta o dell'ultima richiesta")


def test_indice():
    with tempfile.TemporaryDirectory() as t:
        d = make(Path(t))
        e = T.entry(d, "prova/")
        assert e["i18n"]["en"] == {"name": "Test", "description": "Describe"}
        assert e["i18n"]["it"] == {"name": "Prova", "features": ["Uno", "Due"]}
        assert "de" not in e["i18n"] and "locales.json" in e["files"]
        assert X.pick_lang(e["i18n"], "de")["name"] == "Test"
        (d / "locales.json").unlink()
        assert "i18n" not in T.entry(d, "prova/")
    print("ok  indice dello store: testi della scheda per lingua")


def test_controllo():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import i18n_check as C
    with tempfile.TemporaryDirectory() as t:
        d = make(Path(t))
        bad = C.ext_problems(root=Path(t))
        assert "prova/de: manca solo_it" in bad and "prova/fr: manca ciao" in bad
        assert "prova/en: chiave in piu' solo_en" in bad
        (d / "locales.json").write_text(json.dumps({"it": {"a": "{n} giochi"}, **{l: {"a": "{x} games"} for l in
                                                   ("de", "en", "es", "fr", "pt-BR")}}), encoding="utf-8")
        assert all("segnaposto" in x for x in C.ext_problems(root=Path(t)))
    assert C.ext_problems() == [], C.ext_problems()  # le estensioni del repository sono tradotte per intero
    print("ok  i18n_check: chiavi e segnaposto delle estensioni")


test_ricadute()
test_controllo()
test_api_t()
test_indice()
print("test_ext_i18n: OK")
