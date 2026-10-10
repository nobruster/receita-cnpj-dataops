"""Gate da allowlist assinada: devolve só as colunas aprovadas de uma tabela gold, na ordem do
esquema, ou recusa. Falha fechada. Mensagens citam tabela e coluna, nunca valores."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ALLOWLIST = Path(__file__).resolve().parent / "allowlist.json"
TIPOS_COMPOSTOS = ("STRUCT", "LIST", "MAP", "UNION")


class AllowlistRecusada(Exception):
    pass


def _listar_colunas(con) -> dict[str, list[tuple[str, str]]]:
    rows = con.execute(
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'gold' ORDER BY table_name, ordinal_position"
    ).fetchall()
    tabelas: dict[str, list[tuple[str, str]]] = {}
    for tabela, coluna, tipo in rows:
        tabelas.setdefault(tabela, []).append((coluna, tipo))
    return tabelas


def hash_esquema(esquema: dict) -> str:
    return hashlib.sha256(json.dumps(esquema, sort_keys=True).encode("utf-8")).hexdigest()


def _composto(tipo: str) -> bool:
    t = str(tipo).upper().strip()
    return t.startswith(TIPOS_COMPOSTOS) or t.endswith("]")


def colunas_aprovadas(con, tabela: str, caminho: Path | str = ALLOWLIST) -> list[str]:
    try:
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AllowlistRecusada(f"allowlist ilegível para a tabela {tabela}") from exc

    if tabela in (dados.get("excluidas") or {}):
        raise AllowlistRecusada(f"tabela {tabela} fica fora da troca (excluida da allowlist)")
    entrada = (dados.get("tabelas") or {}).get(tabela)
    if entrada is None:
        raise AllowlistRecusada(f"tabela {tabela} fora da allowlist")

    ass = dados.get("assinatura") or {}
    if not ass.get("por") or not ass.get("em") or not dados.get("esquema_hash"):
        raise AllowlistRecusada(f"allowlist sem assinatura (tabela {tabela})")

    esquema = _listar_colunas(con)
    if hash_esquema(esquema) != dados["esquema_hash"]:
        raise AllowlistRecusada(f"hash do esquema diverge da assinatura (tabela {tabela})")

    reais = esquema.get(tabela)
    if not reais:
        raise AllowlistRecusada(f"tabela {tabela} ausente no esquema")

    declaradas = entrada.get("colunas") or {}
    nao_publicar = set(dados.get("nao_publicar") or {})
    aprovadas: list[str] = []
    for nome, tipo in reais:
        if _composto(tipo):
            raise AllowlistRecusada(f"coluna {tabela}.{nome} de tipo composto")
        info = declaradas.get(nome)
        if info is None:
            raise AllowlistRecusada(f"coluna {tabela}.{nome} fora da allowlist")
        if info.get("aprovado") is not True:
            continue
        if nome in nao_publicar:
            raise AllowlistRecusada(f"coluna {tabela}.{nome} está em nao_publicar")
        aprovadas.append(nome)

    if not aprovadas:
        raise AllowlistRecusada(f"tabela {tabela} sem coluna aprovada")
    return aprovadas
