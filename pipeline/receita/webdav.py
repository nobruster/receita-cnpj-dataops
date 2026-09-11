"""Cliente WebDAV do compartilhamento público da Receita Federal (Nextcloud).

Desde 2025 os dados abertos do CNPJ ficam em
``https://arquivos.receitafederal.gov.br/index.php/s/<token>``. A pasta é exposta
por WebDAV em ``/public.php/webdav`` com autenticação básica ``(token, "")``;
cada competência é uma subpasta ``AAAA-MM/`` com 37 arquivos ``.zip``.

O servidor é lento e derruba conexões com frequência, então o download:

* retoma do byte onde parou (``Range``), inclusive entre execuções (``.part``);
* trata o servidor ignorando ``Range`` (responde 200) recomeçando do zero;
* considera "travado" um stream sem bytes por ``rfb_stall_timeout`` segundos;
* valida tamanho e integridade do zip antes de promover ``.part`` -> ``.zip``.

Proxy corporativo: o httpx respeita ``HTTPS_PROXY``/``NO_PROXY`` do ambiente e
``rfb_ca_bundle`` aceita a CA de inspeção TLS.
"""

from __future__ import annotations

import json
import logging
import time
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree as ET

import httpx

from pipeline.config import Settings, get_settings
from pipeline.errors import CorruptZipError, MissingFilesError
from pipeline.receita.layout import COMPETENCIA_RE, EXPECTED_FILES, validate_competencia

log = logging.getLogger("pipeline.webdav")

DAV_NS = {"d": "DAV:"}
PROPFIND_BODY = (
    '<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:prop>'
    "<d:getcontentlength/><d:getetag/><d:getlastmodified/><d:resourcetype/>"
    "</d:prop></d:propfind>"
)
CHUNK = 1024 * 1024


@dataclass(frozen=True, slots=True)
class RemoteFile:
    name: str
    size: int
    etag: str
    last_modified: str


def _client(settings: Settings) -> httpx.Client:
    verify: bool | str = settings.rfb_ca_bundle or settings.rfb_verify_ssl
    return httpx.Client(
        auth=(settings.rfb_share_token, ""),
        verify=verify,
        timeout=httpx.Timeout(settings.rfb_stall_timeout, connect=settings.rfb_connect_timeout),
        follow_redirects=True,
        headers={"User-Agent": "receita-cnpj-dataops/0.1"},
    )


def _propfind(client: httpx.Client, url: str) -> list[dict]:
    resp = client.request(
        "PROPFIND", url, headers={"Depth": "1", "Content-Type": "application/xml"}, content=PROPFIND_BODY
    )
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    out: list[dict] = []
    for r in root.findall("d:response", DAV_NS):
        href = r.findtext("d:href", default="", namespaces=DAV_NS)
        prop = r.find("d:propstat/d:prop", DAV_NS)
        if prop is None:
            continue
        is_dir = prop.find("d:resourcetype/d:collection", DAV_NS) is not None
        out.append(
            {
                "href": unquote(href),
                "is_dir": is_dir,
                "size": int(prop.findtext("d:getcontentlength", default="0", namespaces=DAV_NS) or 0),
                "etag": (prop.findtext("d:getetag", default="", namespaces=DAV_NS) or "").strip('"'),
                "last_modified": prop.findtext("d:getlastmodified", default="", namespaces=DAV_NS) or "",
            }
        )
    return out


def list_competencias(settings: Settings | None = None) -> list[str]:
    """Competências publicadas (``AAAA-MM``), em ordem crescente."""
    s = settings or get_settings()
    with _client(s) as c:
        entries = _propfind(c, s.rfb_webdav_url.rstrip("/") + "/")
    comps = {e["href"].rstrip("/").rsplit("/", 1)[-1] for e in entries if e["is_dir"]}
    return sorted(x for x in comps if COMPETENCIA_RE.match(x))


def latest_competencia(settings: Settings | None = None) -> str:
    comps = list_competencias(settings)
    if not comps:
        raise RuntimeError("nenhuma competência encontrada no WebDAV da Receita")
    return comps[-1]


def list_files(competencia: str, settings: Settings | None = None) -> list[RemoteFile]:
    s = settings or get_settings()
    validate_competencia(competencia)
    with _client(s) as c:
        entries = _propfind(c, f"{s.rfb_webdav_url.rstrip('/')}/{competencia}/")
    files = []
    for e in entries:
        name = e["href"].rstrip("/").rsplit("/", 1)[-1]
        if not e["is_dir"] and name.lower().endswith(".zip"):
            files.append(RemoteFile(name, e["size"], e["etag"], e["last_modified"]))
    return sorted(files, key=lambda f: f.name)


def check_complete(competencia: str, files: list[RemoteFile]) -> None:
    missing = sorted(set(EXPECTED_FILES) - {f.name for f in files})
    if missing:
        err = MissingFilesError(f"competência {competencia}: faltam {', '.join(missing)}",
                                competencia=competencia, arquivos=",".join(missing))
        log.error(err.contract_line())
        raise err


def verify_zip(path: Path) -> None:
    """Valida estrutura e CRC do zip (lê o arquivo inteiro: segundos por GB)."""
    try:
        with zipfile.ZipFile(path) as z:
            bad = z.testzip()
    except zipfile.BadZipFile as exc:
        raise CorruptZipError(f"{path.name}: zip inválido ({exc})", arquivo=path.name) from exc
    if bad is not None:
        raise CorruptZipError(f"{path.name}: CRC inválido no membro {bad}", arquivo=path.name)


def download_file(
    competencia: str,
    remote: RemoteFile,
    dest_dir: Path,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
) -> Path:
    """Baixa um arquivo com retomada. Idempotente: pula se já estiver completo."""
    s = settings or get_settings()
    dest_dir.mkdir(parents=True, exist_ok=True)
    final = dest_dir / remote.name
    part = dest_dir / (remote.name + ".part")
    if final.exists() and final.stat().st_size == remote.size:
        return final

    url = f"{s.rfb_webdav_url.rstrip('/')}/{competencia}/{remote.name}"
    own_client = client is None
    c = client or _client(s)
    try:
        for attempt in range(1, s.download_retries + 1):
            offset = part.stat().st_size if part.exists() else 0
            if remote.size and offset >= remote.size:
                break
            headers = {"Accept-Encoding": "identity"}
            if offset:
                headers["Range"] = f"bytes={offset}-"
            try:
                with c.stream("GET", url, headers=headers) as resp:
                    if resp.status_code == 416:  # já temos tudo
                        break
                    resp.raise_for_status()
                    mode = "ab"
                    if offset and resp.status_code == 200:
                        log.warning("%s: servidor ignorou Range; recomeçando do zero", remote.name)
                        mode = "wb"
                    with part.open(mode) as fh:
                        for chunk in resp.iter_bytes(CHUNK):
                            fh.write(chunk)
                if not remote.size or part.stat().st_size >= remote.size:
                    break
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                wait = min(300, 5 * 2 ** (attempt - 1))
                log.warning("%s: tentativa %d/%d falhou (%s); nova tentativa em %ss",
                            remote.name, attempt, s.download_retries, exc, wait)
                time.sleep(wait)
        else:
            raise RuntimeError(f"{remote.name}: download não concluiu após {s.download_retries} tentativas")
    finally:
        if own_client:
            c.close()

    got = part.stat().st_size if part.exists() else 0
    if remote.size and got != remote.size:
        raise RuntimeError(f"{remote.name}: tamanho {got} != esperado {remote.size}")
    verify_zip(part)
    part.replace(final)
    return final


def write_manifest(competencia: str, files: list[RemoteFile], dest_dir: Path) -> Path:
    path = dest_dir / "_manifest.json"
    payload = {
        "competencia": competencia,
        "gerado_em": datetime.now(UTC).isoformat(),
        "arquivos": [asdict(f) for f in files],
        "bytes_total": sum(f.size for f in files),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def published_at(files: list[RemoteFile]) -> datetime | None:
    """Data de publicação estimada = maior Last-Modified entre os arquivos."""
    stamps = []
    for f in files:
        try:
            stamps.append(parsedate_to_datetime(f.last_modified))
        except (TypeError, ValueError):
            continue
    return max(stamps) if stamps else None
