"""Trilha de publicação em ``ops.runs``.

Recebe o cursor da transação do publicar (nunca abre conexão própria), para que a linha
de sucesso entre ou saia junto com o swap. Grava só metadados: nenhum valor de célula.
"""
from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

SQL_GRAVAR = (
    "INSERT INTO ops.runs "
    "(tabela, run_id, contagem, duracao_ms, menor_n, allowlist_hash, motivo_recusa) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s) "
    "ON CONFLICT (tabela, run_id) DO NOTHING"
)


def run_id_padrao() -> str:
    """Identificador estável no dia: um retry do Airflow cai na mesma chave única."""
    return date.today().isoformat()


def hash_allowlist(caminho: Path | str) -> str | None:
    try:
        return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()
    except OSError:
        return None


def menor_n(con, tabela: str, quase_ids: list[str]) -> int | None:
    """Menor contagem entre as células dos quase-identificadores (None se não houver ou falhar)."""
    if not quase_ids:
        return None
    lista = ", ".join('"' + c.replace('"', '""') + '"' for c in quase_ids)
    try:
        return con.execute(
            f"SELECT min(n) FROM (SELECT count(*) AS n FROM gold.{tabela} GROUP BY {lista}) g"  # noqa: S608
        ).fetchone()[0]
    except Exception:  # não propaga a mensagem original (pode conter valores)
        return None


def gravar(
    cur,
    tabela: str,
    contagem: int | None,
    duracao_ms: int | None,
    menor: int | None,
    allowlist_hash: str | None,
    run_id: str | None = None,
    motivo_recusa: str | None = None,
) -> None:
    """Grava uma linha em ops.runs pelo cursor da transação em curso."""
    cur.execute(
        SQL_GRAVAR,
        (tabela, run_id or run_id_padrao(), contagem, duracao_ms, menor, allowlist_hash, motivo_recusa),
    )
