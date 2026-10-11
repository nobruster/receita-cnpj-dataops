"""T-014: corte do publicador antigo (estático: lê os arquivos, sem Postgres).

Escrito manualmente (oráculo de autoria humana): o executor não cria arquivos congelados.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SQL = RAIZ / "sql" / "003_cutover_dono.sql"
SCRIPT = RAIZ / "scripts" / "verificar_m1_m5.py"
EVIDENCIA = RAIZ / "docs" / "evidencia-prd.md"
HISTORICO = "gold_resumo_competencia"


def _sql() -> str:
    assert SQL.is_file(), "sql/003_cutover_dono.sql ausente"
    return SQL.read_text(encoding="utf-8")


def test_sql_nao_transfere_historico():
    for linha in _sql().splitlines():
        if re.search(r"OWNER\s+TO", linha, re.IGNORECASE):
            assert HISTORICO not in linha, f"SQL transfere o dono do histórico: {linha}"


def test_sql_dono():
    assert "OWNER TO publisher" in _sql()


def test_sql_grant_historico():
    assert f"GRANT SELECT ON gold.{HISTORICO}" in _sql()


def test_script_somente_leitura():
    assert SCRIPT.is_file(), "scripts/verificar_m1_m5.py ausente"
    fonte = SCRIPT.read_text(encoding="utf-8").upper()
    for proibido in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "CREATE ", "ALTER ", "TRUNCATE ", "COPY "):
        assert proibido not in fonte, f"script com escrita/DDL: {proibido.strip()}"


def test_evidencia_existe():
    assert EVIDENCIA.is_file() and EVIDENCIA.stat().st_size > 0, "docs/evidencia-prd.md ausente ou vazio"
