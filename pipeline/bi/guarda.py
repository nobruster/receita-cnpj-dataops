"""Guarda LGPD bloqueante, fail-closed, chamada por publicar.py antes de qualquer escrita no Postgres.

Aborta (GuardaRecusada) se: houver coluna fora da allowlist; o nome da coluna casar com padrão
pessoal (cpf, nome, nasc; denylist, só camada extra: a defesa real é projetar só colunas aprovadas);
ou algum grupo de quase-identificadores tiver n < K_MIN. Grupo com NULL conta como grupo; tabela
vazia não tem células e passa. Mensagens citam tabela e coluna, nunca valores.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

K_MIN = 5
QUASE_IDENTIFICADOR = "quase-identificador"
_PADRAO_PESSOAL = re.compile(r"(^|_)(cpf|nome|nasc\w*)(_|$)", re.IGNORECASE)


class GuardaRecusada(Exception):
    pass


def _aspas(coluna: str) -> str:
    return '"' + coluna.replace('"', '""') + '"'


def quase_identificadores(tabela: str, caminho: Path | str) -> tuple[set[str], set[str]]:
    """Devolve (colunas declaradas, quase-identificadores) da tabela na allowlist; falha fechada."""
    try:
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GuardaRecusada(f"allowlist ilegível para a tabela {tabela}") from exc
    entrada = (dados.get("tabelas") or {}).get(tabela)
    if entrada is None:
        raise GuardaRecusada(f"tabela {tabela} fora da allowlist")
    declaradas = entrada.get("colunas") or {}
    quase = {c for c, info in declaradas.items() if (info or {}).get("classe") == QUASE_IDENTIFICADOR}
    return set(declaradas), quase


def verificar(con, tabela: str, colunas: list[str], declaradas: set[str], quase_ids: set[str], k: int = K_MIN) -> None:
    """Levanta GuardaRecusada se a publicação de ``colunas`` de gold.<tabela> violar a guarda."""
    for c in colunas:
        if c not in declaradas:
            raise GuardaRecusada(f"coluna {tabela}.{c} fora da allowlist")
        if _PADRAO_PESSOAL.search(c):
            raise GuardaRecusada(f"coluna {tabela}.{c} com nome de padrão pessoal")

    chaves = [c for c in colunas if c in quase_ids]
    if not chaves:
        return
    lista = ", ".join(_aspas(c) for c in chaves)
    try:
        menores = con.execute(
            f"SELECT count(*) FROM (SELECT count(*) AS n FROM gold.{tabela} GROUP BY {lista}) g WHERE g.n < ?",  # noqa: S608
            [k],
        ).fetchone()[0]
    except Exception:  # fail-closed; não propaga a mensagem original (pode conter valores)
        raise GuardaRecusada(f"não foi possível verificar k em {tabela} ({', '.join(chaves)})") from None
    if menores:
        raise GuardaRecusada(
            f"tabela {tabela}: {menores} célula(s) com n < {k} nos quase-identificadores ({', '.join(chaves)})"
        )
