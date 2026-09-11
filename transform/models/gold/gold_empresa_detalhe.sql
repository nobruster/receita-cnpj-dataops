{#
  Ficha completa: uma linha por estabelecimento (grão = CNPJ de 14 posições).
  Base dos casos de uso de crédito/risco e prospecção. Só linhas aceitas no silver.
#}
with socios_por_empresa as (
    select cnpj_basico, count(*) as qtd_socios
    from {{ ref('silver_socios') }}
    group by 1
),

estab_por_empresa as (
    select cnpj_basico, count(*) as qtd_estabelecimentos
    from {{ ref('silver_estabelecimentos') }}
    group by 1
)

select
    e.cnpj,
    e.cnpj_basico,
    e.cnpj_ordem,
    e.cnpj_dv,
    emp.razao_social,
    e.nome_fantasia,
    e.identificador_matriz_filial,
    mf.descricao                                   as matriz_filial,
    e.situacao_cadastral,
    sit.descricao                                  as situacao_cadastral_descricao,
    e.data_situacao_cadastral,
    e.motivo_situacao_cadastral,
    mot.descricao                                  as motivo_situacao_descricao,
    e.data_inicio_atividade,
    date_diff('month', e.data_inicio_atividade, current_date) / 12.0 as idade_anos,
    e.cnae_fiscal_principal,
    cnae.descricao                                 as cnae_principal_descricao,
    e.cnae_fiscal_secundaria,
    emp.natureza_juridica,
    nat.descricao                                  as natureza_juridica_descricao,
    emp.porte,
    por.descricao                                  as porte_descricao,
    emp.capital_social,
    emp._capital_sentinela                         as capital_sentinela,
    coalesce(s.opcao_simples, 'N')                 as opcao_simples,
    s.data_opcao_simples,
    s.data_exclusao_simples,
    coalesce(s.opcao_mei, 'N')                     as opcao_mei,
    e.tipo_logradouro,
    e.logradouro,
    e.numero,
    e.complemento,
    e.bairro,
    e.cep,
    e.uf,
    e.municipio,
    mun.descricao                                  as municipio_nome,
    e.pais,
    pai.descricao                                  as pais_nome,
    e.nome_cidade_exterior,
    e.ddd_1, e.telefone_1, e.ddd_2, e.telefone_2,
    e.correio_eletronico,
    e.situacao_especial,
    e.data_situacao_especial,
    coalesce(ee.qtd_estabelecimentos, 0)           as qtd_estabelecimentos_empresa,
    coalesce(sp.qtd_socios, 0)                     as qtd_socios_empresa,
    e._arquivo                                     as arquivo_origem,
    e._competencia                                 as competencia
from {{ ref('silver_estabelecimentos') }} e
left join {{ ref('silver_empresas') }}           emp  on emp.cnpj_basico = e.cnpj_basico
left join {{ ref('silver_simples') }}            s    on s.cnpj_basico   = e.cnpj_basico
left join estab_por_empresa                      ee   on ee.cnpj_basico  = e.cnpj_basico
left join socios_por_empresa                     sp   on sp.cnpj_basico  = e.cnpj_basico
left join {{ ref('dom_matriz_filial') }}         mf   on mf.codigo  = e.identificador_matriz_filial
left join {{ ref('dom_situacao_cadastral') }}    sit  on sit.codigo = e.situacao_cadastral
left join {{ ref('silver_dom_motivos') }}        mot  on mot.codigo = e.motivo_situacao_cadastral
left join {{ ref('silver_dom_cnaes') }}          cnae on cnae.codigo = e.cnae_fiscal_principal
left join {{ ref('silver_dom_naturezas') }}      nat  on nat.codigo = emp.natureza_juridica
left join {{ ref('dom_porte') }}                 por  on por.codigo = emp.porte
left join {{ ref('silver_dom_municipios') }}     mun  on mun.codigo = e.municipio
left join {{ ref('silver_dom_paises') }}         pai  on pai.codigo = e.pais
