with base as (
    select b.*, row_number() over (partition by b.cnpj_basico order by b._arquivo) as _ordem_dup
    from {{ ref('bronze_empresas') }} b
),

classificado as (
    select
        base.*,
        case
            when not coalesce(regexp_full_match(cnpj_basico, '[0-9A-Z]{8}'), false) then 'invalid_cnpj'
            when _ordem_dup > 1 then 'duplicate_key'
            when capital_social_raw is not null and (capital_social is null or capital_social < 0)
                then 'invalid_capital'
            when (porte is not null and porte not in (select codigo from {{ ref('dom_porte') }}))
              or not coalesce(regexp_full_match(natureza_juridica, '[0-9]{4}'), false) then 'invalid_domain'
            when {{ mojibake("coalesce(razao_social, '')") }} then 'encoding_mojibake'
        end as reject_rule
    from base
)

select
    c.* exclude (_ordem_dup),
    coalesce(c.capital_social = 999999999999, false)              as _capital_sentinela,
    (c.natureza_juridica is not null and nat.codigo is null)       as _orphan_natureza
from classificado c
left join {{ ref('silver_dom_naturezas') }} nat on nat.codigo = c.natureza_juridica
