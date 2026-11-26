"""Cataloghi coerenti con it.json e API delle traduzioni."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import i18n_check
from pozzo import i18n as I

assert not i18n_check.problems(), i18n_check.problems()
assert I.tr("app.language", "xx") == "Lingua"            # lingua sconosciuta -> italiano
assert I.tr("chiave.inesistente") == "chiave.inesistente"
assert I.catalog("en")["app.language"] == "Language"
assert set(I.languages()) == {"it", "en", "es", "fr", "de", "pt-BR"}
assert I.from_request("ru", None) == "en"                 # cookie di una lingua rimossa -> inglese
assert I.from_request(None, "ru-RU,ru;q=0.9") == "it"     # nessuna lingua supportata -> italiano

# Chiavi richieste per 0.21.0 (A2 overlay, A3 BP media, Claude phone, A4 desktop/mediakeys)
REQUIRED_KEYS = [
    "o.overlay.soundInvalid", "o.overlay.cornerInvalid", "o.overlay.mediaInvalid",
    "o.overlay.stopConfirm", "o.overlay.shotSaved", "o.overlay.mediaSent", "o.overlay.emuSent",
    "o.overlay.actionFailed", "o.overlay.netError", "o.overlay.notesEmpty",
    "o.overlay.volDown", "o.overlay.volUp", "o.overlay.mute",
    "o.overlay.hintTabs", "o.overlay.hintSelect", "o.overlay.hintClose",
    "c.tab.videos", "c.bpm.series", "c.bpm.ep.one", "c.bpm.ep.many",
    "c.bpm.row.continue", "c.bpm.row.film", "c.bpm.row.series", "c.bpm.row.anime", "c.bpm.row.watchlist",
    "c.bpm.seen", "c.bpm.noPlayer", "c.bpm.playError", "c.bpm.play", "c.bpm.loading",
    "c.bpm.empty.title", "c.bpm.empty.lib", "c.bpm.empty.err", "c.bpm.empty.hint",
    "c.bpm.wl.noFile", "c.bpm.season", "c.bpm.season.n",
    "s.phone.guestPinOnce", "s.phone.badOrigin",
    "h.shots.hotkey", "h.shots.hotkeyPh", "h.home.resumeGame",
    "i.media.keySent", "i.media.playerSent", "i.media.volumeUpdated",
    "i.media.noPlayer", "i.media.keysUnavailable", "i.media.controlFailed",
]
import json
import re
# ogni file di lingua letto direttamente (senza il ripiego sull'italiano): chiavi presenti, {segnaposto} uguali
ph = lambda s: sorted(re.findall(r"\{\w+\}", s))
it_cat = json.loads((I.DIR / "it.json").read_text(encoding="utf-8"))
for lang in I.languages():
    cat = json.loads((I.DIR / f"{lang}.json").read_text(encoding="utf-8"))
    for k in REQUIRED_KEYS:
        assert k in cat, f"Chiave mancante in {lang}.json: {k}"
        assert ph(cat[k]) == ph(it_cat[k]), f"Segnaposto diversi in {lang}.json: {k}"

# mediakeys.py: i messaggi usano i18n.tr (non italiano fisso)
from pozzo import mediakeys
tok = I.current.set("en")
try:
    bad = mediakeys.send("bad", platform="win32", keybd_event=lambda *a: None)
    assert not bad["ok"] and bad["message"] == I.tr("o.overlay.mediaInvalid", "en"), bad
    ok_res = mediakeys.send("play_pause", platform="win32", keybd_event=lambda *a: None)
    assert ok_res["ok"] and ok_res["message"] == I.tr("i.media.keySent", "en"), ok_res
    unavail = mediakeys.send("play_pause", platform="solaris")
    assert not unavail["ok"] and unavail["message"] == I.tr("i.media.keysUnavailable", "en"), unavail
finally:
    I.current.reset(tok)

print("ok")
