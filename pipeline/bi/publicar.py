"""Publica 1 tabela gold da allowlist no Postgres, para o bi_reader.

Lê do DuckDB só as colunas aprovadas, em lotes (fetchmany), e envia por COPY ao
``gold.<t>__novo`` sem arquivo intermediário. Tudo numa única transação, pela conexão do
publisher: se algo falha antes do COMMIT, a tabela antiga continua intacta (ADR-001).
A troca (DROP, RENAME e GRANT SELECT ao bi_reader) acontece com lock_timeout.
"""
from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable

import json
from pathlib import Path

import duckdb
import psycopg

from pipeline.bi import guarda, runs
from pipeline.bi.allowlist import ALLOWLIST, colunas_aprovadas
from pipeline.config import Settings, get_settings
from pipeline.publish import HISTORY_TABLES, INDEXES, _pg_type

log = logging.getLogger("pipeline.bi.publicar")

LOCK_TIMEOUT = "60s"
LEITOR = "bi_reader"
LOTE = 50_000
_TIMEOUT_RE = re.compile(r"^\d+(ms|s|min)?$")


def _caminho_allowlist():
    """Allowlist usada por colunas_aprovadas (partial com ``caminho`` nos testes), senão a versionada."""
    return getattr(colunas_aprovadas, "keywords", {}).get("caminho", ALLOWLIST)


def _tipos(con: duckdb.DuckDBPyConnection, tabela: str, colunas: list[str]) -> list[tuple[str, str]]:
    por_nome = dict(con.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'gold' AND table_name = ?", [tabela]
    ).fetchall())
    return [(c, por_nome[c]) for c in colunas]


def publicar_tabela(
    con: duckdb.DuckDBPyConnection,
    tabela: str,
    settings: Settings | None = None,
    lock_timeout: str = LOCK_TIMEOUT,
    antes_do_rename: Callable[[], None] | None = None,
    run_id: str | None = None,
    caminho: Path | str | None = None,
) -> int:
    """Publica ``gold.<tabela>`` e devolve a contagem de linhas publicadas."""
    if tabela in HISTORY_TABLES:  # recusa antes de qualquer DDL
        raise ValueError(f"tabela {tabela} é excluída da troca (HISTORY_TABLES)")
    if not _TIMEOUT_RE.match(lock_timeout):
        raise ValueError(f"lock_timeout inválido: {lock_timeout!r}")

    s = settings or get_settings()
    schema = s.publish_schema
    if caminho is not None:
        colunas = colunas_aprovadas(con, tabela, caminho)
    else:
        colunas = colunas_aprovadas(con, tabela)
        caminho = _caminho_allowlist()
    esperado = con.execute(f"SELECT count(*) FROM gold.{tabela}").fetchone()[0]  # noqa: S608
    ddl = ", ".join(f'"{c}" {_pg_type(ty)}' for c, ty in _tipos(con, tabela, colunas))
    nomes = ", ".join(f'"{c}"' for c in colunas)
    novo = f'{schema}."{tabela}__novo"'
    final = f'{schema}."{tabela}"'

    declaradas, quase_ids = guarda.quase_identificadores(tabela, caminho)
    guarda.verificar(con, tabela, colunas, declaradas, quase_ids)  # aborta antes de qualquer escrita no Postgres
    menor = runs.menor_n(con, tabela, [c for c in colunas if c in quase_ids])
    inicio = time.monotonic()

    with psycopg.connect(s.publisher_dsn) as pg, pg.cursor() as cur:  # uma transação
        cur.execute(f"DROP TABLE IF EXISTS {novo}")
        cur.execute(f"CREATE TABLE {novo} ({ddl})")
        origem = con.execute(f"SELECT {nomes} FROM gold.{tabela}")  # noqa: S608
        with cur.copy(f"COPY {novo} ({nomes}) FROM STDIN") as cp:
            while lote := origem.fetchmany(LOTE):
                for linha in lote:
                    cp.write_row(linha)
        for col in INDEXES.get(tabela, []):
            if col in colunas:
                cur.execute(f'CREATE INDEX ON {novo} ("{col}")')
        obtido = cur.execute(f"SELECT count(*) FROM {novo}").fetchone()[0]
        if obtido != esperado:
            raise RuntimeError(f"contagem diverge em {tabela}: duckdb={esperado} postgres={obtido}")

        cur.execute(f"SET LOCAL lock_timeout = '{lock_timeout}'")
        cur.execute(f"DROP TABLE IF EXISTS {final}")
        if antes_do_rename is not None:
            antes_do_rename()
        cur.execute(f'ALTER TABLE {novo} RENAME TO "{tabela}"')
        cur.execute(f"GRANT SELECT ON {final} TO {LEITOR}")
        runs.gravar(  # mesma transação do swap: rollback não deixa linha de sucesso
            cur, tabela, obtido, int((time.monotonic() - inicio) * 1000), menor,
            runs.hash_allowlist(caminho), run_id,
        )
    log.info("publicado %s.%s: %s linhas", schema, tabela, f"{obtido:,}")
    return obtido


def publicar_todas(
    con: duckdb.DuckDBPyConnection,
    settings: Settings | None = None,
    caminho: Path | str = ALLOWLIST,
    lock_timeout: str = LOCK_TIMEOUT,
) -> dict[str, int]:
    """Publica cada tabela aprovada da allowlist, uma transação por tabela.

    Tabelas excluídas ficam fora (com log). Se uma falha, as demais seguem e o erro é levantado no
    fim; as já trocadas permanecem publicadas.
    """
    try:
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("allowlist ilegível") from exc

    for nome in sorted(dados.get("excluidas") or {}):
        log.info("tabela %s excluída da allowlist: fica fora da publicação", nome)

    excluidas = set(dados.get("excluidas") or {})
    publicadas: dict[str, int] = {}
    falhas: dict[str, Exception] = {}
    for tabela in sorted(t for t in (dados.get("tabelas") or {}) if t not in excluidas):
        try:
            publicadas[tabela] = publicar_tabela(
                con, tabela, settings=settings, lock_timeout=lock_timeout, caminho=caminho
            )
        except Exception as exc:  # noqa: BLE001 - isola a falha por tabela
            log.error("falha ao publicar %s: %s", tabela, type(exc).__name__)
            falhas[tabela] = exc
    if falhas:
        raise RuntimeError(
            f"falha em {len(falhas)} tabela(s): {', '.join(sorted(falhas))}; "
            f"publicadas: {', '.join(sorted(publicadas)) or 'nenhuma'}"
        ) from next(iter(falhas.values()))
    return publicadas
