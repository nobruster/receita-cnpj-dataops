-- Agregado leve (Power BI / prospecção): estabelecimentos ATIVOS por região, setor e perfil.
select
    uf,
    municipio,
    municipio_nome,
    cnae_fiscal_principal,
    cnae_principal_descricao,
    porte_descricao,
    opcao_simples,
    opcao_mei,
    count(*)                                                                   as estabelecimentos_ativos,
    count(*) filter (where identificador_matriz_filial = '1')                  as matrizes_ativas,
    count(*) filter (where data_inicio_atividade >= current_date - interval 12 month) as aberturas_12m,
    count(*) filter (where data_inicio_atividade >= current_date - interval 3 month)  as aberturas_3m,
    any_value(competencia)                                                     as competencia
from {{ ref('gold_empresa_detalhe') }}
where situacao_cadastral = '02'
group by all
