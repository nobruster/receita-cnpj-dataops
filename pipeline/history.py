"""C4a — arquivo histórico mensal em Parquet (AC-8, decisão D-1).

Ao concluir cada competência, o silver ACEITO de cada entidade vira
``/data/history/competencia=AAAA-MM/<entidade>.parquet`` (zstd). Retenção: as
``RETENCAO`` competências mais recentes. Sem carga retroativa: o histórico se forma
a partir da primeira execução (só a última competência é processada).

O Parquet é legível sem o warehouse (``read_parquet``), então a comparação entre
meses não depende do raw nem de travar o DuckDB principal.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import duckdb

from pipeline.config import Settings, get_settings
from pipeline.receita.layout import COMPETENCIA_RE

log = logging.getLogger("pipeline.history")

RETENCAO = 12
ENTIDADES: tuple[str, ...] = ("empresas", "estabelecimentos", "socios", "simples")


def history_dir(settings: Settings | None = None) -> Path:
    return (settings or get_settings()).data_dir / "history"


def partition(competencia: str, settings: Settings | None = None) -> Path:
    return history_dir(settings) / f"competencia={competencia}"


def archive(con: duckdb.DuckDBPyConnection, competencia: str, settings: Settings | None = None) -> dict[str, int]:
    """Exporta o silver aceito da competência (idempotente: sobrescreve a partição)."""
    dest = partition(competencia, settings)
    tmp = dest.with_name(dest.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    linhas = {}
    for ent in ENTIDADES:
        path = tmp / f"{ent}.parquet"
        con.execute(f"COPY (SELECT * FROM silver.silver_{ent}) TO '{path.as_posix()}' "
                    "(FORMAT parquet, COMPRESSION zstd)")
        linhas[ent] = con.execute(f"SELECT count(*) FROM read_parquet('{path.as_posix()}')").fetchone()[0]
    shutil.rmtree(dest, ignore_errors=True)
    tmp.rename(dest)
    log.info("histórico %s arquivado: %s", competencia, linhas)
    return linhas


def arquivadas(settings: Settings | None = None) -> list[str]:
    base = history_dir(settings)
    if not base.exists():
        return []
    comps = [p.name.split("=", 1)[1] for p in base.glob("competencia=*") if p.is_dir()]
    return sorted(c for c in comps if COMPETENCIA_RE.match(c))


def apply_retention(keep: int = RETENCAO, settings: Settings | None = None) -> list[str]:
    """Remove as competências mais antigas além de ``keep``. Devolve as removidas."""
    comps = arquivadas(settings)
    removidas = comps[:-keep] if len(comps) > keep else []
    for c in removidas:
        shutil.rmtree(partition(c, settings), ignore_errors=True)
        log.info("histórico %s removido (retenção de %d)", c, keep)
    return removidas


def read_sql(entidade: str, competencia: str, settings: Settings | None = None) -> str:
    """Expressão ``read_parquet(...)`` para uma entidade de uma competência arquivada."""
    if entidade not in ENTIDADES or not COMPETENCIA_RE.match(competencia):
        raise ValueError(f"entidade/competência inválida: {entidade} {competencia}")
    path = partition(competencia, settings) / f"{entidade}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"competência {competencia} não está no histórico ({path})")
    return f"read_parquet('{path.as_posix()}')"
