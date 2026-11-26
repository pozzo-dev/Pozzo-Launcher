"""Fix 0.21.0 della pipeline. Esegui: python tests/test_pipeline_021.py"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402
from rich.progress import Progress  # noqa: E402

from pozzo import config, pipeline, platforms as P  # noqa: E402
from pozzo.cache import Cache  # noqa: E402
from pozzo.scanner import Game  # noqa: E402
from pozzo.sources.base import Source  # noqa: E402


class FakeLibretro(Source):
    name = "libretro"
    provides: set = set()

    def name_first(self, games):
        # come hash_games: salva gli hash in cache, poi identifica
        for g in games:
            if not g.needs_hash:  # la seconda chiamata (3b) non rilegge: come hash_games
                continue
            g.crc = "AABBCCDD"
            self.cache.put_file(str(g.path), g.size, g.mtime, {"crc": "AABBCCDD", "md5": "m", "sha1": "s"})
            g.dat_crc = "11223344"
        return list(games)


def test_name_first_keeps_hashes():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = config.Config(cache=Path(tmp) / "cache", output=Path(tmp) / "out")
        cache = Cache(cfg.cache)
        g = Game(Path(tmp) / "Foo.sfc", P.get("snes"), 10, 5.0)
        g.needs_hash = True
        old = dict(pipeline.SOURCES)
        pipeline.SOURCES["libretro"] = FakeLibretro
        pipeline.make_client = lambda: httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
        try:
            async def go():
                with Progress(disable=True) as prog:
                    await pipeline.scrape(cfg, cache, [g], ["libretro"], False, prog, lambda *a: None)
            asyncio.run(go())
        finally:
            pipeline.SOURCES.clear()
            pipeline.SOURCES.update(old)
        row = cache.get_file(str(g.path), 10, 5.0)
        assert row and row.get("crc") == "AABBCCDD" and row.get("sha1") == "s", row
        assert row.get("dat_crc") == "11223344", row
        cache.close()


if __name__ == "__main__":
    test_name_first_keeps_hashes()
    print("ok")
