{#
  Classifica cada estabelecimento: reject_rule = primeira regra violada (ou NULL).
  O valor de reject_rule É o failure_key do Sentinel — é assim que o Data Profiler
  liga uma linha quarentenada a um diagnóstico (decisão U3 do ws-3: quarentena, não descarte).
#}
with base as (
    select
        b.*,
        row_number() over (partition by b.cnpj order by b._arquivo) as _ordem_dup
    from {{ ref('bronze_estabelecimentos') }} b
),

classificado as (
    select
        base.*,
        case
            when not coalesce(regexp_full_match(cnpj_basico, '[0-9A-Z]{8}')
                              and regexp_full_match(cnpj_ordem, '[0-9A-Z]{4}')
                              and regexp_full_match(cnpj_dv, '[0-9]{2}'), false) then 'invalid_cnpj'
            when cnpj_dv <> {{ cnpj_dv('cnpj_basico || cnpj_ordem') }} then 'invalid_cnpj'
            when _ordem_dup > 1 then 'duplicate_key'
            when _data_inicio_invalida or _data_situacao_invalida then 'invalid_date'
            when coalesce(identificador_matriz_filial, '') not in ('1', '2')
              or coalesce(situacao_cadastral, '') not in (select codigo from {{ ref('dom_situacao_cadastral') }})
              or coalesce(uf, '') not in (select codigo from {{ ref('dom_uf') }}) then 'invalid_domain'
            when {{ mojibake("coalesce(nome_fantasia, '') || coalesce(logradouro, '') || coalesce(bairro, '')") }}
                then 'encoding_mojibake'
        end as reject_rule
    from base
)

select
    c.* exclude (_ordem_dup),
    -- órfãos NÃO são rejeitados: a Receita publica códigos ausentes do próprio
    -- domínio (ex.: motivo 32, alguns países). Viram flag + métrica monitorada.
    (c.cnae_fiscal_principal is not null and cnae.codigo is null) as _orphan_cnae,
    (c.municipio is not null and mun.codigo is null)              as _orphan_municipio,
    (c.motivo_situacao_cadastral is not null and mot.codigo is null) as _orphan_motivo,
    (c.pais is not null and pai.codigo is null)                   as _orphan_pais
from classificado c
left join {{ ref('silver_dom_cnaes') }}      cnae on cnae.codigo = c.cnae_fiscal_principal
left join {{ ref('silver_dom_municipios') }} mun  on mun.codigo  = c.municipio
left join {{ ref('silver_dom_motivos') }}    mot  on mot.codigo  = c.motivo_situacao_cadastral
left join {{ ref('silver_dom_paises') }}     pai  on pai.codigo  = c.pais
