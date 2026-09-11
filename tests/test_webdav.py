"""Cliente WebDAV contra um servidor falso (httpx.MockTransport)."""

import io
import zipfile

import httpx
import pytest

from pipeline.config import Settings
from pipeline.errors import MissingFilesError
from pipeline.receita import webdav

BASE = "https://rfb.test/public.php/webdav"


def _xml(entries):
    parts = []
    for href, size, is_dir in entries:
        rt = "<d:resourcetype><d:collection/></d:resourcetype>" if is_dir else "<d:resourcetype/>"
        parts.append(f"<d:response><d:href>{href}</d:href><d:propstat><d:prop>{rt}"
                     f"<d:getcontentlength>{size}</d:getcontentlength><d:getetag>\"e\"</d:getetag>"
                     "<d:getlastmodified>Sun, 10 Aug 2026 10:00:00 GMT</d:getlastmodified>"
                     "</d:prop></d:propstat></d:response>")
    return f'<?xml version="1.0"?><d:multistatus xmlns:d="DAV:">{"".join(parts)}</d:multistatus>'.encode()


def _zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("x.csv", '"1";"a"\n' * 1000)
    return buf.getvalue()


PAYLOAD = _zip_bytes()


def handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if request.method == "PROPFIND" and path.endswith("/webdav/"):
        return httpx.Response(207, content=_xml([("/public.php/webdav/", 0, True),
                                                  ("/public.php/webdav/2026-07/", 0, True),
                                                  ("/public.php/webdav/2026-08/", 0, True)]))
    if request.method == "PROPFIND":
        return httpx.Response(207, content=_xml([("/public.php/webdav/2026-08/", 0, True),
                                                  ("/public.php/webdav/2026-08/Cnaes.zip", len(PAYLOAD), False)]))
    rng = request.headers.get("Range")
    if rng:  # retomada
        start = int(rng.split("=")[1].rstrip("-"))
        return httpx.Response(206, content=PAYLOAD[start:])
    return httpx.Response(200, content=PAYLOAD)


@pytest.fixture
def settings(monkeypatch):
    s = Settings(rfb_webdav_url=BASE, download_retries=2)
    real = httpx.Client

    def fake_client(_s):
        return real(transport=httpx.MockTransport(handler), auth=("t", ""))

    monkeypatch.setattr(webdav, "_client", fake_client)
    return s


def test_lista_competencias(settings):
    assert webdav.list_competencias(settings) == ["2026-07", "2026-08"]
    assert webdav.latest_competencia(settings) == "2026-08"


def test_competencia_incompleta(settings):
    files = webdav.list_files("2026-08", settings)
    assert [f.name for f in files] == ["Cnaes.zip"]
    with pytest.raises(MissingFilesError):
        webdav.check_complete("2026-08", files)


def test_download_retoma_do_parcial(settings, tmp_path):
    remote = webdav.list_files("2026-08", settings)[0]
    (tmp_path / "Cnaes.zip.part").write_bytes(PAYLOAD[:100])  # download anterior interrompido
    out = webdav.download_file("2026-08", remote, tmp_path, settings)
    assert out.read_bytes() == PAYLOAD
    assert not (tmp_path / "Cnaes.zip.part").exists()
