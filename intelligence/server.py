"""Servidor MCP da base do CNPJ.

    python -m intelligence.server            # stdio (Claude Desktop via `docker exec -i`)
    python -m intelligence.server --http     # streamable HTTP em :8000/mcp
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from intelligence import intents

mcp = FastMCP("receita-cnpj", host="0.0.0.0", port=8000)


def _j(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


@mcp.tool()
def ficha_cnpj(cnpj: str) -> str:
    """Ficha cadastral de um CNPJ (14 posições, com ou sem máscara) ou de todos os estabelecimentos
    de uma raiz (8 posições): situação, idade, porte, capital, CNAE, endereço, Simples/MEI."""
    return _j(intents.ficha_cnpj(cnpj))


@mcp.tool()
def quadro_societario(cnpj_basico: str) -> str:
    """Sócios de uma empresa (raiz de 8 posições). CPF de pessoa física vem mascarado pela Receita."""
    return _j(intents.quadro_societario(cnpj_basico))


@mcp.tool()
def rede_societaria(cnpj_basico: str) -> str:
    """Empresas que são sócias da empresa informada e empresas em que ela participa (sócio PJ)."""
    return _j(intents.rede_societaria(cnpj_basico))


@mcp.tool()
def prospectar(cnae: str | None = None, uf: str | None = None, municipio: str | None = None,
               porte: str | None = None, simples: str | None = None, aberta_ha_meses: int | None = None,
               limite: int = 100) -> str:
    """Lista estabelecimentos ATIVOS filtrando por CNAE principal (7 dígitos), UF, município (nome),
    porte (MICRO EMPRESA | EMPRESA DE PEQUENO PORTE | DEMAIS), Simples (S/N) e abertura recente (meses)."""
    return _j(intents.prospectar(cnae, uf, municipio, porte, simples, aberta_ha_meses, limite))


@mcp.tool()
def painel_mercado(uf: str | None = None, cnae: str | None = None, limite: int = 50) -> str:
    """Quantidade de estabelecimentos ativos e aberturas nos últimos 12 meses por município e CNAE."""
    return _j(intents.painel(uf, cnae, limite))


@mcp.tool()
def resumo_competencia() -> str:
    """Placar da competência carregada: empresas, estabelecimentos, ativos, baixados, sócios, rejeitados."""
    return _j(intents.resumo_competencia())


@mcp.tool()
def schema_gold() -> str:
    """Tabelas e colunas da camada gold."""
    return _j(intents.schema_info())


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--http", action="store_true")
    a = p.parse_args()
    mcp.run(transport="streamable-http" if a.http else "stdio")


if __name__ == "__main__":
    main()
