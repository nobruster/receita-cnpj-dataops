"""Inventário do schema gold: lista tabelas e colunas (somente leitura) e escreve a allowlist
negada por padrão em pipeline/bi/allowlist.json. O script nunca aprova coluna nem assina:
classe e assinatura são do Bruno."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from pipeline.warehouse import connect_ro

ALLOWLIST = Path(__file__).resolve().parent.parent / "pipeline" / "bi" / "allowlist.json"
CLASSES = ["identificador direto", "quase-identificador", "agregado", "sensível (art. 11)"]
EXCLUIDAS = {
    "gold_resumo_competencia": {
        "modo": "delete_copy_legado",
        "motivo": "histórico completo no DuckDB não foi confirmado; fica fora do DROP/RENAME e mantém "
                  "DELETE + COPY do publish.py, sem allowlist nem k = 5",
    },
}
NAO_PUBLICAR = {
    "razao_social": {
        "publicar": False,
        "motivo": "guarda k=5 e LGPD (decisão do Bruno, 2026-10-10, opção a)",
    },
}


def listar_colunas(con) -> dict[str, list[tuple[str, str]]]:
    rows = con.execute(
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'gold' ORDER BY table_name, ordinal_position"
    ).fetchall()
    tabelas: dict[str, list[tuple[str, str]]] = {}
    for tabela, coluna, tipo in rows:
        tabelas.setdefault(tabela, []).append((coluna, tipo))
    return tabelas


def _coluna(tipo: str) -> dict:
    return {"tipo": tipo, "classe": None, "aprovado": False}


def gerar(con) -> dict:
    esquema = listar_colunas(con)
    hash_esquema = hashlib.sha256(json.dumps(esquema, sort_keys=True).encode("utf-8")).hexdigest()
    tabelas: dict = {}
    excluidas: dict = {}
    for tabela, cols in esquema.items():
        colunas = {nome: _coluna(tipo) for nome, tipo in cols}
        if tabela in EXCLUIDAS:
            excluidas[tabela] = {**EXCLUIDAS[tabela], "colunas": colunas}
        else:
            tabelas[tabela] = {"colunas": colunas}
    for tabela, info in EXCLUIDAS.items():
        excluidas.setdefault(tabela, {**info, "colunas": {}})
    return {
        "versao": 1,
        "template": False,
        "esquema_hash": hash_esquema,
        "assinatura": {"por": "", "em": ""},
        "classes": CLASSES,
        "tabelas": tabelas,
        "excluidas": excluidas,
        "nao_publicar": NAO_PUBLICAR,
    }


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    destino = Path(args[0]) if args else ALLOWLIST
    con = connect_ro()
    try:
        dados = gerar(con)
    finally:
        con.close()
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"allowlist escrita em {destino} ({len(dados['tabelas'])} tabelas, "
          f"{len(dados['excluidas'])} excluídas); nenhuma coluna aprovada")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
