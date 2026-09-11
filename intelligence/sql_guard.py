"""SELECT somente leitura e com lista de tabelas permitidas (usado pelo `cnpj.ps1 consulta` e pelo Sentinel).

    python -m intelligence.sql_guard "SELECT uf, count(*) FROM gold.gold_empresa_detalhe GROUP BY 1"

Duas camadas independentes: (1) a guarda de texto recusa escrita, múltiplos
comandos, funções de leitura de arquivo e tabelas fora de silver/gold/raw_load_log;
(2) o warehouse é aberto em modo somente leitura, que fisicamente não escreve.
"""

from __future__ import annotations

import json
import re
import sys
import time

import duckdb

from pipeline.warehouse import connect_ro

ALLOWED_TABLES = re.compile(r"\b(silver\.silver_\w+|gold\.gold_\w+|raw\.raw_load_log)\b", re.IGNORECASE)
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|create|alter|attach|detach|copy|export|import|install|load|pragma|set|call|"
    r"checkpoint|vacuum|read_csv|read_parquet|read_json|glob)\b",
    re.IGNORECASE,
)
MAX_ROWS = 50


def open_ro(retries: int = 5) -> duckdb.DuckDBPyConnection:
    """Abre o warehouse só-leitura; se a DAG estiver escrevendo, espera e tenta de novo."""
    last: Exception | None = None
    for i in range(retries):
        try:
            return connect_ro()
        except duckdb.IOException as exc:  # arquivo travado pelo escritor
            last = exc
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"warehouse ocupado pela DAG (tente depois): {last}")


def run_guarded_select(sql: str) -> str:
    q = sql.strip().rstrip(";")
    if ";" in q or not re.match(r"(?is)^\s*(with|select)\b", q) or FORBIDDEN.search(q):
        return "recusado: apenas um SELECT/WITH somente-leitura é permitido"
    for ref in re.findall(r"(?i)\b(?:from|join)\s+([a-z_][\w.]*)", q):
        if "." in ref and not ALLOWED_TABLES.fullmatch(ref):
            return f"recusado: tabela fora da lista permitida: {ref}"
    con = open_ro()
    try:
        cur = con.execute(f"SELECT * FROM ({q}) AS t LIMIT {MAX_ROWS}")
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    finally:
        con.close()
    return json.dumps({"colunas": cols, "linhas": rows}, default=str, ensure_ascii=False)


if __name__ == "__main__":
    print(run_guarded_select(" ".join(sys.argv[1:])))
