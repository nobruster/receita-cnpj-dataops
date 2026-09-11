"""Layout oficial dos dados abertos do CNPJ.

Fonte: https://www.gov.br/receitafederal/dados/cnpj-metadados.pdf
Formato físico: CSV sem cabeçalho, separador ``;``, aspas ``"``, ISO-8859-1.

Este módulo é a ÚNICA fonte da verdade sobre nomes de arquivos e colunas. O
loader (raw), os modelos dbt (bronze) e o injetor de falhas (chaos) leem daqui,
então uma mudança de layout da Receita se corrige num lugar só.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Entity:
    name: str  # nome da tabela raw_<name>
    file_prefix: str  # prefixo do .zip na Receita
    partitioned: bool  # True => 10 arquivos (Prefixo0.zip .. Prefixo9.zip)
    columns: tuple[str, ...]

    @property
    def expected_files(self) -> tuple[str, ...]:
        if self.partitioned:
            return tuple(f"{self.file_prefix}{i}.zip" for i in range(10))
        return (f"{self.file_prefix}.zip",)


DOMAIN_COLUMNS = ("codigo", "descricao")

ENTITIES: dict[str, Entity] = {
    e.name: e
    for e in (
        Entity(
            "empresas",
            "Empresas",
            True,
            (
                "cnpj_basico",
                "razao_social",
                "natureza_juridica",
                "qualificacao_responsavel",
                "capital_social",
                "porte",
                "ente_federativo_responsavel",
            ),
        ),
        Entity(
            "estabelecimentos",
            "Estabelecimentos",
            True,
            (
                "cnpj_basico",
                "cnpj_ordem",
                "cnpj_dv",
                "identificador_matriz_filial",
                "nome_fantasia",
                "situacao_cadastral",
                "data_situacao_cadastral",
                "motivo_situacao_cadastral",
                "nome_cidade_exterior",
                "pais",
                "data_inicio_atividade",
                "cnae_fiscal_principal",
                "cnae_fiscal_secundaria",
                "tipo_logradouro",
                "logradouro",
                "numero",
                "complemento",
                "bairro",
                "cep",
                "uf",
                "municipio",
                "ddd_1",
                "telefone_1",
                "ddd_2",
                "telefone_2",
                "ddd_fax",
                "fax",
                "correio_eletronico",
                "situacao_especial",
                "data_situacao_especial",
            ),
        ),
        Entity(
            "socios",
            "Socios",
            True,
            (
                "cnpj_basico",
                "identificador_socio",
                "nome_socio",
                "cnpj_cpf_socio",
                "qualificacao_socio",
                "data_entrada_sociedade",
                "pais",
                "representante_legal",
                "nome_representante",
                "qualificacao_representante",
                "faixa_etaria",
            ),
        ),
        Entity(
            "simples",
            "Simples",
            False,
            (
                "cnpj_basico",
                "opcao_simples",
                "data_opcao_simples",
                "data_exclusao_simples",
                "opcao_mei",
                "data_opcao_mei",
                "data_exclusao_mei",
            ),
        ),
        Entity("cnaes", "Cnaes", False, DOMAIN_COLUMNS),
        Entity("motivos", "Motivos", False, DOMAIN_COLUMNS),
        Entity("municipios", "Municipios", False, DOMAIN_COLUMNS),
        Entity("naturezas", "Naturezas", False, DOMAIN_COLUMNS),
        Entity("paises", "Paises", False, DOMAIN_COLUMNS),
        Entity("qualificacoes", "Qualificacoes", False, DOMAIN_COLUMNS),
    )
}

# Ordem de carga: domínios primeiro (pequenos), fatos depois.
LOAD_ORDER: tuple[str, ...] = (
    "cnaes",
    "motivos",
    "municipios",
    "naturezas",
    "paises",
    "qualificacoes",
    "simples",
    "empresas",
    "socios",
    "estabelecimentos",
)

EXPECTED_FILES: frozenset[str] = frozenset(f for e in ENTITIES.values() for f in e.expected_files)

_FILE_RE = re.compile(r"^(?P<prefix>[A-Za-z]+?)(?P<part>\d)?\.zip$")
COMPETENCIA_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def entity_for_file(filename: str) -> Entity | None:
    """Mapeia ``Estabelecimentos3.zip`` -> Entity('estabelecimentos'). ``None`` se desconhecido."""
    m = _FILE_RE.match(filename)
    if not m:
        return None
    for ent in ENTITIES.values():
        if ent.file_prefix.lower() == m.group("prefix").lower():
            if ent.partitioned != (m.group("part") is not None):
                return None
            return ent
    return None


def validate_competencia(value: str) -> str:
    if not COMPETENCIA_RE.match(value):
        raise ValueError(f"competência inválida: {value!r} (esperado AAAA-MM)")
    return value
