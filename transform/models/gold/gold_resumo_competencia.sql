-- Uma linha por competência: o "placar" do mês (também usado nos comparativos).
select
    '{{ var("competencia") }}'                                                        as competencia,
    (select count(*) from {{ ref('silver_empresas') }})                               as empresas,
    (select count(*) from {{ ref('silver_estabelecimentos') }})                       as estabelecimentos,
    (select count(*) from {{ ref('silver_estabelecimentos') }} where situacao_cadastral = '02') as estabelecimentos_ativos,
    (select count(*) from {{ ref('silver_estabelecimentos') }} where situacao_cadastral = '08') as estabelecimentos_baixados,
    (select count(*) from {{ ref('silver_socios') }})                                 as socios,
    (select count(*) from {{ ref('silver_simples') }} where opcao_simples = 'S')      as optantes_simples,
    (select count(*) from {{ ref('silver_simples') }} where opcao_mei = 'S')          as optantes_mei,
    (select count(*) from {{ ref('silver_estabelecimentos_rejects') }})               as rejeitados_estabelecimentos,
    (select count(*) from {{ ref('silver_empresas_rejects') }})                       as rejeitados_empresas,
    (select count(*) from {{ ref('silver_socios_rejects') }})                         as rejeitados_socios,
    (select count(*) from {{ ref('silver_simples_rejects') }})                        as rejeitados_simples,
    now()                                                                             as gerado_em
