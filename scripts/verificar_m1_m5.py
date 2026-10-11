"""Verifica M1 a M5 no Postgres de PRD depois do corte (T-014). Somente leitura.

Conta linhas, testa SELECT como bi_reader e lista tabelas __novo; nunca altera nada
(sessões em modo somente leitura). Saída 0 se todas passam, 1 se alguma falha.

  M1  tabelas trocadas de gold pertencem a publisher
  M2  bi_reader faz SELECT em todas as tabelas de gold
  M3  histórico gold_resumo_competencia segue com dono cnpj, com linhas e legível
  M4  nenhuma tabela __novo sobrou em gold
  M5  toda tabela de gold tem contagem de linhas > 0

Senhas só por ambiente (.env): PG_PASSWORD (admin/cnpj) e BI_READER_PASSWORD.
"""
from __future__ import annotations

import os
import sys

import psycopg
from psycopg import sql

HISTORICO = "gold_resumo_competencia"
DONO_HISTORICO = "cnpj"
DONO_TROCADAS = "publisher"
SOMENTE_LEITURA = "-c default_transaction_read_only=on"


def _dsn(usuario: str, senha: str) -> str:
    host = os.environ.get("PG_HOST", "postgres")
    porta = os.environ.get("PG_PORT", "5432")
    banco = os.environ.get("PG_DB", "cnpj")
    return f"host={host} port={porta} dbname={banco} user={usuario} password={senha}"


def _conectar(usuario: str, senha: str) -> psycopg.Connection:
    return psycopg.connect(_dsn(usuario, senha), options=SOMENTE_LEITURA)


def listar_tabelas(con: psycopg.Connection) -> dict[str, str]:
    """Nome da tabela de gold -> dono."""
    with con.cursor() as cur:
        cur.execute(
            "SELECT c.relname, pg_get_userbyid(c.relowner) "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'gold' AND c.relkind IN ('r', 'p') ORDER BY c.relname"
        )
        return {nome: dono for nome, dono in cur.fetchall()}


def contar(con: psycopg.Connection, tabela: str) -> int | None:
    """Linhas lidas com o papel da conexão; None se o SELECT for negado."""
    try:
        with con.cursor() as cur:
            cur.execute(sql.SQL("SELECT count(*) FROM gold.{}").format(sql.Identifier(tabela)))
            return int(cur.fetchone()[0])
    except psycopg.errors.InsufficientPrivilege:
        con.rollback()
        return None


def verificar(admin: psycopg.Connection, leitor: psycopg.Connection) -> dict[str, tuple[bool, str]]:
    tabelas = listar_tabelas(admin)
    novas = sorted(t for t in tabelas if t.endswith("__novo"))
    publicadas = {t: d for t, d in tabelas.items() if t not in novas}
    contagens = {t: contar(leitor, t) for t in publicadas}

    fora_do_dono = sorted(
        t for t, d in publicadas.items() if t != HISTORICO and d != DONO_TROCADAS
    )
    negadas = sorted(t for t, n in contagens.items() if n is None)
    vazias = sorted(t for t, n in contagens.items() if n == 0)
    historico_ok = (
        HISTORICO in publicadas
        and publicadas[HISTORICO] == DONO_HISTORICO
        and (contagens.get(HISTORICO) or 0) > 0
    )

    return {
        "M1": (not fora_do_dono, f"fora do dono {DONO_TROCADAS}: {fora_do_dono or 'nenhuma'}"),
        "M2": (not negadas, f"bi_reader sem SELECT: {negadas or 'nenhuma'}"),
        "M3": (
            historico_ok,
            f"{HISTORICO}: dono={publicadas.get(HISTORICO)} linhas={contagens.get(HISTORICO)}",
        ),
        "M4": (not novas, f"tabelas __novo: {novas or 'nenhuma'}"),
        "M5": (not vazias and bool(publicadas), f"vazias: {vazias or 'nenhuma'}; "
               + ", ".join(f"{t}={n}" for t, n in sorted(contagens.items()))),
    }


def main() -> int:
    senha_admin = os.environ.get("PG_PASSWORD", "")
    senha_leitor = os.environ.get("BI_READER_PASSWORD", "")
    if not senha_admin or not senha_leitor:
        print("defina PG_PASSWORD e BI_READER_PASSWORD no ambiente (.env)", file=sys.stderr)
        return 2
    with _conectar("cnpj", senha_admin) as admin, _conectar("bi_reader", senha_leitor) as leitor:
        resultado = verificar(admin, leitor)
    for metrica, (ok, detalhe) in resultado.items():
        print(f"{metrica} {'PASS' if ok else 'FAIL'} - {detalhe}")
    return 0 if all(ok for ok, _ in resultado.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
