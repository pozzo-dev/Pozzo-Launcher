"""Verifica offline degli hash delle ROM rispetto ai DAT libretro già caricati."""

from __future__ import annotations


def report(games, indexes: dict) -> dict:
    """Costruisce il report senza leggere file: usa esclusivamente gli hash di Game."""
    items = []
    counts = {"verificata": 0, "sconosciuta": 0, "nessun DAT": 0}
    for game in games:
        index = indexes.get(game.platform.id)
        result = index.verify(game) if index else {
            "status": "nessun DAT", "name": "", "match_by": "", "hash_kind": ""
        }
        counts[result["status"]] += 1
        items.append({
            "platform": game.platform.id,
            "file": game.path.name,
            **result,
            "crc": game.crc,
            "md5": game.md5,
            "sha1": game.sha1,
        })
    return {"total": len(items), **counts, "items": items}
