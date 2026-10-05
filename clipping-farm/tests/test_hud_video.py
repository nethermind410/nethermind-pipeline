import hashlib
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from clipping_farm.db import DB
from clipping_farm.hud import HUDHandler


def serve(handler_type):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_type)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_hud_bootstraps_source_and_accepts_source_query(tmp_path):
    handler_type = type(
        "TestHUDHandler",
        (HUDHandler,),
        {"db_path": str(tmp_path / "hud.sqlite"), "source_id": "hud:default"},
    )
    server, thread = serve(handler_type)
    try:
        url = f"http://127.0.0.1:{server.server_port}/?source_id=hud%3Aprevious"
        with urlopen(url) as response:
            html = response.read().decode()
        assert 'let activeSourceId = "hud:previous";' in html
        assert "if(activeSourceId){ refresh(); }" in html
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_clip_endpoint_supports_byte_ranges_for_video_players(tmp_path):
    db_path = tmp_path / "hud.sqlite"
    db = DB(db_path)
    clip = tmp_path / "clip.mp4"
    data = bytes(range(256)) * 8
    clip.write_bytes(data)
    db.put_artifact(
        cache_key="clip:range-test",
        kind="video_clip",
        path=str(clip),
        content_hash=hashlib.sha256(data).hexdigest(),
        metadata={"source_id": "hud:test"},
    )
    db.cx.close()

    handler_type = type(
        "TestHUDHandler",
        (HUDHandler,),
        {"db_path": str(db_path), "source_id": "hud:test"},
    )
    server, thread = serve(handler_type)
    try:
        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/clip?cache_key=clip%3Arange-test",
            headers={"Range": "bytes=100-199"},
        )
        try:
            response = urlopen(request)
        except HTTPError as error:
            response = error
        with response:
            body = response.read()
            assert response.status == 206
            assert response.headers["Content-Range"] == f"bytes 100-199/{len(data)}"
            assert response.headers["Accept-Ranges"] == "bytes"
            assert body == data[100:200]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
