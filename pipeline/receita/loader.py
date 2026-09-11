"""Carga raw: zips da Receita -> DuckDB ``raw.raw_<entidade>`` (fiel ao defeito).

Regras (herdadas da decisão U2 do ws-3, "a ingestão é dona do raw"):

* O raw espelha o arquivo 1:1. Tudo é VARCHAR, nada é corrigido aqui; quem
  decide o que é defeito é o silver (dbt), que manda linhas ruins para
  ``silver_*_rejects`` em vez de descartá-las.
* O raw guarda UMA competência por vez (``CREATE OR REPLACE``). Histórico de
  volumes fica no ledger ``ops.dq_metrics`` (PostgreSQL) e o histórico de dados,
  se desejado, no export Parquet por competência.
* Cada linha recebe ``_arquivo``, ``_competencia`` e ``_carregado_em``.

Proteções:

* ``LayoutDriftError`` — antes de carregar, as primeiras linhas de cada CSV são
  lidas com o módulo ``csv`` e a quantidade de campos é comparada ao layout. O
  DuckDB em ``strict_mode=false`` truncaria colunas extras em silêncio, então
  essa checagem é o que pega mudança de layout da Receita.
* Erros de parsing restantes são capturados com ``store_rejects`` e contados em
  ``raw.raw_load_log`` (não derrubam a carga).
* Toda falha é registrada com uma linha estável ``PIPELINE_FAILURE key=<chave>``
  no log — a superfície I1 que o agente Log Analyst (Sentinel) lê.
"""

from __future__ import annotations

import csv
import logging
import shutil
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from pipeline.errors import CorruptZipError, LayoutDriftError, MissingFilesError
from pipeline.receita.layout import ENTITIES, EXPECTED_FILES, LOAD_ORDER, Entity, entity_for_file

log = logging.getLogger("pipeline.loader")

RAW = "raw"
SAMPLE_LINES = 5000


@dataclass(slots=True)
class FileLoad:
    entidade: str
    arquivo: str
    linhas: int
    erros_parse: int
    bytes_csv: int
    segundos: float


def check_landing(landing: Path, competencia: str) -> None:
    """Os 37 arquivos precisam estar no landing antes de qualquer carga."""
    missing = sorted(EXPECTED_FILES - {p.name for p in landing.glob("*.zip")})
    if missing:
        err = MissingFilesError(f"{competencia}: faltam {', '.join(missing)}",
                                competencia=competencia, arquivos=",".join(missing))
        log.error(err.contract_line())
        raise err


def _extract_member(zip_path: Path, work_dir: Path, competencia: str) -> Path:
    out = work_dir / f"{zip_path.stem}.csv"
    try:
        with zipfile.ZipFile(zip_path) as z:
            members = [m for m in z.infolist() if not m.is_dir()]
            if len(members) != 1:
                raise zipfile.BadZipFile(f"esperado 1 CSV no zip, encontrado {len(members)}")
            with z.open(members[0]) as src, out.open("wb") as dst:
                shutil.copyfileobj(src, dst, length=8 * 1024 * 1024)
    except (zipfile.BadZipFile, EOFError, OSError) as exc:
        out.unlink(missing_ok=True)
        err = CorruptZipError(f"{zip_path.name}: zip inválido ({exc})", competencia=competencia,
                              arquivo=zip_path.name)
        log.error(err.contract_line())
        raise err from exc
    return out


def check_layout(csv_path: Path, entity: Entity, arquivo: str, competencia: str = "") -> None:
    """Moda do nº de campos nas primeiras linhas precisa bater com o layout."""
    counts: Counter[int] = Counter()
    with csv_path.open("r", encoding="latin-1", newline="") as fh:
        reader = csv.reader(fh, delimiter=";", quotechar='"')
        for i, row in enumerate(reader):
            if i >= SAMPLE_LINES:
                break
            counts[len(row)] += 1
    if not counts:
        return  # arquivo vazio: o monitor de volume trata
    modal = counts.most_common(1)[0][0]
    if modal != len(entity.columns):
        err = LayoutDriftError(
            f"{arquivo}: layout mudou — esperado {len(entity.columns)} campos, encontrado {modal}",
            competencia=competencia, arquivo=arquivo, esperado=len(entity.columns), encontrado=modal)
        log.error(err.contract_line())
        raise err


def _create_raw_table(con: duckdb.DuckDBPyConnection, entity: Entity) -> None:
    cols = ", ".join(f'"{c}" VARCHAR' for c in entity.columns)
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {RAW}")
    con.execute(
        f"CREATE OR REPLACE TABLE {RAW}.raw_{entity.name} ({cols}, "
        "_arquivo VARCHAR, _competencia VARCHAR, _carregado_em TIMESTAMPTZ)"
    )


def _ensure_log(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {RAW}")
    con.execute(
        f"""CREATE TABLE IF NOT EXISTS {RAW}.raw_load_log (
            competencia VARCHAR, entidade VARCHAR, arquivo VARCHAR, linhas BIGINT,
            erros_parse BIGINT, bytes_csv BIGINT, segundos DOUBLE, carregado_em TIMESTAMPTZ)"""
    )


def _insert(con: duckdb.DuckDBPyConnection, path: Path, entity: Entity, arquivo: str, competencia: str,
            encoding: str) -> None:
    columns = "{" + ", ".join(f"'{c}': 'VARCHAR'" for c in entity.columns) + "}"
    con.execute(
        f"""INSERT INTO {RAW}.raw_{entity.name}
            SELECT *, ?, ?, now() FROM read_csv(?, columns={columns}, header=false, delim=';',
                quote='"', escape='"', encoding='{encoding}', strict_mode=false,
                store_rejects=true, max_line_size=4000000)""",
        [arquivo, competencia, str(path)],
    )


def _transcode(src: Path) -> Path:
    dst = src.with_suffix(".utf8.csv")
    with src.open("r", encoding="latin-1", newline="") as fi, dst.open("w", encoding="utf-8", newline="") as fo:
        while chunk := fi.read(16 * 1024 * 1024):
            fo.write(chunk)
    return dst


def load_csv(
    con: duckdb.DuckDBPyConnection, csv_path: Path, entity: Entity, arquivo: str, competencia: str
) -> FileLoad:
    started = datetime.now(UTC)
    check_layout(csv_path, entity, arquivo, competencia)
    before = con.execute(f"SELECT count(*) FROM {RAW}.raw_{entity.name}").fetchone()[0]
    try:
        _insert(con, csv_path, entity, arquivo, competencia, "latin-1")
    except duckdb.InvalidInputException as exc:
        if "encoded" not in str(exc):
            raise
        # O decodificador latin-1 do DuckDB recusa bytes 0x80-0x9F (comuns quando o
        # arquivo na verdade veio em cp1252). O Python decodifica latin-1 sem perda:
        # transcodifica para UTF-8 e recarrega. Mais lento, mas não perde linha.
        log.warning("%s: bytes fora do latin-1 estrito; transcodificando para UTF-8", arquivo)
        utf8 = _transcode(csv_path)
        try:
            _insert(con, utf8, entity, arquivo, competencia, "utf-8")
        finally:
            utf8.unlink(missing_ok=True)
    after = con.execute(f"SELECT count(*) FROM {RAW}.raw_{entity.name}").fetchone()[0]
    erros = con.execute("SELECT count(*) FROM reject_errors").fetchone()[0]
    con.execute("DELETE FROM reject_errors; DELETE FROM reject_scans;")
    secs = (datetime.now(UTC) - started).total_seconds()
    fl = FileLoad(entity.name, arquivo, after - before, erros, csv_path.stat().st_size, secs)
    con.execute(
        f"INSERT INTO {RAW}.raw_load_log VALUES (?, ?, ?, ?, ?, ?, ?, now())",
        [competencia, fl.entidade, fl.arquivo, fl.linhas, fl.erros_parse, fl.bytes_csv, fl.segundos],
    )
    return fl


def load_entity(
    con: duckdb.DuckDBPyConnection, entity_name: str, landing: Path, work_dir: Path, competencia: str
) -> list[FileLoad]:
    """(Re)carrega todos os zips de uma entidade para ``raw.raw_<entidade>``."""
    entity = ENTITIES[entity_name]
    _ensure_log(con)
    con.execute(f"DELETE FROM {RAW}.raw_load_log WHERE competencia = ? AND entidade = ?",
                [competencia, entity.name])
    _create_raw_table(con, entity)
    work_dir.mkdir(parents=True, exist_ok=True)
    loads: list[FileLoad] = []
    for arquivo in entity.expected_files:
        zip_path = landing / arquivo
        if not zip_path.exists():
            check_landing(landing, competencia)
        csv_path = _extract_member(zip_path, work_dir, competencia)
        try:
            fl = load_csv(con, csv_path, entity, arquivo, competencia)
            log.info("raw_%s <- %s: %s linhas (%s erros de parsing) em %.1fs",
                     entity.name, arquivo, f"{fl.linhas:,}", fl.erros_parse, fl.segundos)
            loads.append(fl)
        finally:
            csv_path.unlink(missing_ok=True)
    return loads


def load_all(con: duckdb.DuckDBPyConnection, landing: Path, work_dir: Path, competencia: str) -> list[FileLoad]:
    check_landing(landing, competencia)
    out: list[FileLoad] = []
    for name in LOAD_ORDER:
        out.extend(load_entity(con, name, landing, work_dir, competencia))
    return out


def unknown_files(landing: Path) -> list[str]:
    """Arquivos no landing que o layout não conhece (sinal de mudança na Receita)."""
    return sorted(p.name for p in landing.glob("*.zip") if entity_for_file(p.name) is None)
