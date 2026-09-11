"""SELECT somente leitura e com lista de tabelas permitidas (usado pelo `cnpj.ps1 consulta` e pelo Sentinel).

    python -m intelligence.sql_guard "SELECT uf, count(*) FROM gold.gold_empresa_detalhe GROUP BY 1"

Três camadas independentes: (1) a guarda recusa escrita, múltiplos comandos e
funções de arquivo; (2) as tabelas citadas vêm do PARSER do DuckDB e precisam estar em
silver/gold/raw_load_log; (3) o warehouse abre somente leitura, sem acesso a arquivos
externos e com configuração travada (``connect_ro``). Com ``deny_columns`` (Sentinel -> LLM),
a consulta roda sobre views que NÃO têm as colunas pessoais (``connect_ro_masked``).
"""

from __future__ import annotations

import json
import re
import sys
import time

import duckdb

from pipeline.warehouse import connect_ro, connect_ro_masked

ALLOWED_TABLES = re.compile(r"\b(silver\.silver_\w+|gold\.gold_\w+|raw\.raw_load_log)\b", re.IGNORECASE)
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|create|alter|attach|detach|copy|export|import|install|load|pragma|set|call|"
    r"checkpoint|vacuum|read_\w+|parquet_scan|query|query_table|glob|getenv)\b",
    re.IGNORECASE,
)
MAX_ROWS = 50


def open_ro(retries: int = 5, deny_columns: tuple[str, ...] = ()) -> duckdb.DuckDBPyConnection:
    """Abre o warehouse só-leitura; se a DAG estiver escrevendo, espera e tenta de novo."""
    last: Exception | None = None
    for i in range(retries):
        try:
            return connect_ro_masked(deny_columns) if deny_columns else connect_ro()
        except duckdb.IOException as exc:  # arquivo travado pelo escritor
            last = exc
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"warehouse ocupado pela DAG (tente depois): {last}")


def referenced_tables(sql: str) -> set[str]:
    """Tabelas citadas segundo o PARSER do DuckDB (não regex): vírgulas, aspas e aliases inclusos."""
    return {t.split(" AS ")[0].replace('"', "").lower() for t in duckdb.get_table_names(sql, qualified=True)}


def run_guarded_select(sql: str, max_rows: int = MAX_ROWS, deny_columns: tuple[str, ...] = ()) -> str:
    q = sql.strip().rstrip(";")
    if ";" in q or not re.match(r"(?is)^\s*(with|select)\b", q) or FORBIDDEN.search(q):
        return "recusado: apenas um SELECT/WITH somente-leitura é permitido"
    try:
        tabelas = referenced_tables(q)
    except Exception as exc:  # SQL que nem o parser entende
        return f"recusado: SQL inválido ({exc})"
    ctes = {m.lower() for m in re.findall(r"(?i)(?:with|,)\s*([a-z_]\w*)\s+as\s*\(", q)}
    for t in tabelas:
        if t in ctes:
            continue
        if not ALLOWED_TABLES.fullmatch(t):
            return f"recusado: tabela fora da lista permitida: {t}"
    for col in deny_columns:  # mensagem clara; a proteção real são as views sem a coluna
        if re.search(rf"(?i)\b{re.escape(col)}\b", q):
            return f"recusado: esta ferramenta não devolve a coluna {col} (dado pessoal)"
    con = open_ro(deny_columns=deny_columns)
    try:
        cur = con.execute(f"SELECT * FROM ({q}) AS t LIMIT {int(max_rows)}")
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    finally:
        con.close()
    return json.dumps({"colunas": cols, "linhas": rows}, default=str, ensure_ascii=False)


if __name__ == "__main__":
    print(run_guarded_select(" ".join(sys.argv[1:])))
