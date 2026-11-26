"""0.21.0: /img serve solo file dentro la cache anche se il percorso salvato nel database utente e' ostile."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from pozzo.app.routes import images  # noqa: E402


def test_img_refuses_paths_outside_cache():
    root = Path(tempfile.mkdtemp())
    cache = root / "cache"
    (cache / "media").mkdir(parents=True)
    (cache / "media" / "ok.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 50)
    (root / "secret.txt").write_text("segreto")
    media = {"cover": "media/ok.jpg"}
    user = SimpleNamespace(media_overrides=lambda key: dict(media))
    lib = SimpleNamespace(get=lambda gid: {"key": "k", "title": "t", "media": {}})
    ctx = SimpleNamespace(cfg=SimpleNamespace(cache=cache), lib=lib, state=None, thumbs_dir=root / "th", user=user)
    app = FastAPI()
    app.include_router(images.build_router(ctx))
    c = TestClient(app)
    assert c.get("/img/1/cover").status_code == 200
    for evil in ("../secret.txt", str(root / "secret.txt")):
        media["cover"] = evil
        assert c.get("/img/1/cover").status_code == 404, evil
