"""Barra del pannello Attivita': avanzamento dalle sotto-attivita' e loro elenco.

Esegui: PYTHONUTF8=1 python tests/test_activity_progress.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pozzo.app.routes.activity import MAX_SUBTASKS, overall, subtasks

scan = {"name": "Scansione cartelle", "total": 5000, "done": 5000}
src = {"name": "IGDB", "total": 10, "done": 1}
# prima: (5000+1)/(5010) = 99.8%; ora ogni sotto-attivita' pesa uguale
assert abs(overall([scan, src], True) - 0.55) < 1e-9
# una fonte senza totale (non ancora partita) non abbassa ne' alza la barra
assert overall([scan, src, {"name": "RAWG", "total": 0, "done": 0}], True) == overall([scan, src], True)
# tutte finite ma il lavoro e' in corso (ricostruzione libreria): barra indeterminata, non ferma al 100%
assert overall([scan, {**src, "done": 10}], True) is None
assert overall([scan], False) == 1.0  # lavoro finito: piena
assert overall([{"name": "x", "total": 0, "done": 0}], True) is None
assert overall([{"name": "x", "total": 2, "done": 5}], False) == 1.0  # mai oltre il 100%

rows = subtasks([{"name": f"  media {i}", "total": i, "done": 0} for i in range(20)])
assert len(rows) == MAX_SUBTASKS and rows[-1]["name"] == "media 19" and rows[0]["total"] == 20 - MAX_SUBTASKS
print("ok")
