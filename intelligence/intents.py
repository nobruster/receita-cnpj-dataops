"""Intenções curadas sobre o gold — o LLM escolhe a intenção, nunca escreve SQL.

Cada intenção é um SELECT estático com parâmetros ligados (``?``), só em tabelas
gold, com LIMIT. O warehouse é aberto em modo somente leitura a cada chamada e
fechado em seguida (não segura o arquivo e não bloqueia a DAG).
"""

from __future__ import annotations

import time
from typing import Any

import duckdb

from pipeline.receita import cnpj as cnpjlib
from pipeline.warehouse import connect_ro

MAX_LIMIT = 200


def _query(sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    for tentativa in range(3):
        try:
            con = connect_ro()
            break
        except duckdb.IOException:
            if tentativa == 2:
                raise RuntimeError("warehouse em processamento pela DAG mensal; tente em alguns minutos") from None
            time.sleep(2)
    try:
        cur = con.execute(sql, params or [])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
    finally:
        con.close()


def ficha_cnpj(cnpj: str) -> dict[str, Any]:
    """Ficha cadastral (crédito/risco). Aceita CNPJ completo (com ou sem máscara) ou raiz de 8."""
    c = cnpjlib.normalize(cnpj)
    if len(c) == 14:
        if not cnpjlib.is_valid(c):
            return {"erro": f"CNPJ inválido (DV não confere): {cnpj}"}
        rows = _query("SELECT * FROM gold.gold_empresa_detalhe WHERE cnpj = ?", [c])
    elif len(c) == 8:
        rows = _query("SELECT * FROM gold.gold_empresa_detalhe WHERE cnpj_basico = ? ORDER BY cnpj LIMIT 50", [c])
    else:
        return {"erro": "informe o CNPJ (14 posições) ou a raiz (8 posições)"}
    if not rows:
        return {"encontrado": False, "cnpj": c}
    return {"encontrado": True, "estabelecimentos": rows}


def quadro_societario(cnpj_basico: str) -> list[dict[str, Any]]:
    """Sócios da empresa (KYC). CPF de pessoa física vem mascarado pela Receita."""
    raiz = cnpjlib.normalize(cnpj_basico)[:8]
    return _query(
        "SELECT tipo_socio, nome_socio, cnpj_cpf_socio, qualificacao_socio_descricao, data_entrada_sociedade, "
        "faixa_etaria_descricao, pais_nome FROM gold.gold_socios_detalhe WHERE cnpj_basico = ? "
        "ORDER BY data_entrada_sociedade LIMIT 200", [raiz])


def rede_societaria(cnpj_basico: str) -> dict[str, list[dict[str, Any]]]:
    """Empresas ligadas por participação societária PJ (KYC/PLD): quem é sócia e em quem ela investe."""
    raiz = cnpjlib.normalize(cnpj_basico)[:8]
    socias = _query(
        "SELECT cnpj_socio, razao_social_socio, qualificacao_socio_descricao, data_entrada_sociedade "
        "FROM gold.gold_rede_societaria WHERE cnpj_basico_investida = ? LIMIT 200", [raiz])
    investidas = _query(
        "SELECT cnpj_basico_investida, razao_social_investida, qualificacao_socio_descricao, data_entrada_sociedade "
        "FROM gold.gold_rede_societaria WHERE cnpj_basico_socio = ? LIMIT 200", [raiz])
    return {"empresas_socias": socias, "empresas_investidas": investidas}


def prospectar(cnae: str | None = None, uf: str | None = None, municipio: str | None = None,
               porte: str | None = None, simples: str | None = None, aberta_ha_meses: int | None = None,
               limite: int = 100) -> list[dict[str, Any]]:
    """Estabelecimentos ATIVOS por CNAE principal, UF, município (nome), porte, Simples e abertura recente."""
    where, params = ["situacao_cadastral = '02'"], []
    if cnae:
        where.append("cnae_fiscal_principal = ?")
        params.append(cnpjlib.normalize(cnae))
    if uf:
        where.append("uf = ?")
        params.append(uf.upper())
    if municipio:
        where.append("municipio_nome = ?")
        params.append(municipio.upper())
    if porte:
        where.append("porte_descricao = ?")
        params.append(porte.upper())
    if simples:
        where.append("opcao_simples = ?")
        params.append(simples.upper()[:1])
    if aberta_ha_meses:
        where.append("data_inicio_atividade >= current_date - to_months(?)")
        params.append(int(aberta_ha_meses))
    lim = max(1, min(int(limite), MAX_LIMIT))
    return _query(
        "SELECT cnpj, razao_social, nome_fantasia, cnae_principal_descricao, municipio_nome, uf, porte_descricao, "
        "opcao_simples, data_inicio_atividade, correio_eletronico FROM gold.gold_empresa_detalhe WHERE "
        + " AND ".join(where) + f" ORDER BY data_inicio_atividade DESC LIMIT {lim}", params)


def painel(uf: str | None = None, cnae: str | None = None, limite: int = 50) -> list[dict[str, Any]]:
    """Agregado de ativos por município e CNAE (visão de mercado)."""
    where, params = ["1=1"], []
    if uf:
        where.append("uf = ?")
        params.append(uf.upper())
    if cnae:
        where.append("cnae_fiscal_principal = ?")
        params.append(cnpjlib.normalize(cnae))
    lim = max(1, min(int(limite), MAX_LIMIT))
    return _query(
        "SELECT uf, municipio_nome, cnae_fiscal_principal, cnae_principal_descricao, "
        "sum(estabelecimentos_ativos) AS ativos, sum(aberturas_12m) AS aberturas_12m "
        "FROM gold.gold_painel_prospeccao WHERE " + " AND ".join(where)
        + f" GROUP BY ALL ORDER BY ativos DESC LIMIT {lim}", params)


def resumo_competencia() -> list[dict[str, Any]]:
    """Placar da competência carregada (empresas, ativos, rejeitados...)."""
    return _query("SELECT * FROM gold.gold_resumo_competencia")


def schema_info() -> dict[str, list[str]]:
    rows = _query(
        "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'gold' "
        "ORDER BY table_name, ordinal_position")
    out: dict[str, list[str]] = {}
    for r in rows:
        out.setdefault(r["table_name"], []).append(r["column_name"])
    return out


def diferenca_competencias(anterior: str, atual: str, cnpj_basico: str | None = None,
                           limite: int = 100) -> dict[str, Any]:
    """AC-8: o que mudou entre duas competências do histórico (situação cadastral e quadro societário).

    Lê só o Parquet do histórico (não trava o warehouse). ``cnpj_basico`` restringe a uma empresa (KYC).
    """
    from pipeline import history

    lim = max(1, min(int(limite), MAX_LIMIT))
    ea, eb = history.read_sql("estabelecimentos", anterior), history.read_sql("estabelecimentos", atual)
    sa, sb = history.read_sql("socios", anterior), history.read_sql("socios", atual)
    filtro, params = "", []
    if cnpj_basico:
        filtro = " AND x.cnpj_basico = ?"
        params = [cnpjlib.normalize(cnpj_basico)[:8]]
    chave_socio = "x.cnpj_basico, x.nome_socio, x.cnpj_cpf_socio, x.qualificacao_socio"
    con = duckdb.connect()
    try:
        def q(sql: str) -> list[dict[str, Any]]:
            cur = con.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]

        mudancas = q(
            f"SELECT x.cnpj, a.situacao_cadastral AS situacao_anterior, x.situacao_cadastral AS situacao_atual, "
            f"x.data_situacao_cadastral FROM {eb} x JOIN {ea} a USING (cnpj) "
            f"WHERE a.situacao_cadastral IS DISTINCT FROM x.situacao_cadastral{filtro} ORDER BY x.cnpj LIMIT {lim}")
        novos = q(f"SELECT x.cnpj, x.data_inicio_atividade FROM {eb} x ANTI JOIN {ea} a USING (cnpj) "
                  f"WHERE true{filtro} ORDER BY x.cnpj LIMIT {lim}")
        entradas = q(f"SELECT {chave_socio} FROM {sb} x ANTI JOIN {sa} a "
                     f"USING (cnpj_basico, nome_socio, cnpj_cpf_socio, qualificacao_socio) WHERE true{filtro} "
                     f"ORDER BY 1, 2 LIMIT {lim}")
        saidas = q(f"SELECT {chave_socio} FROM {sa} x ANTI JOIN {sb} b "
                   f"USING (cnpj_basico, nome_socio, cnpj_cpf_socio, qualificacao_socio) WHERE true{filtro} "
                   f"ORDER BY 1, 2 LIMIT {lim}")
    finally:
        con.close()
    return {"anterior": anterior, "atual": atual, "mudancas_situacao": mudancas, "estabelecimentos_novos": novos,
            "socios_entraram": entradas, "socios_sairam": saidas}
