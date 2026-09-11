with base as (
    select b.*, row_number() over (partition by b.cnpj_basico order by b._arquivo) as _ordem_dup
    from {{ ref('bronze_simples') }} b
)

select
    base.* exclude (_ordem_dup),
    case
        when not coalesce(regexp_full_match(cnpj_basico, '[0-9A-Z]{8}'), false) then 'invalid_cnpj'
        when _ordem_dup > 1 then 'duplicate_key'
        when coalesce(opcao_simples, 'N') not in ('S', 'N') or coalesce(opcao_mei, 'N') not in ('S', 'N')
            then 'invalid_domain'
        when _data_invalida then 'invalid_date'
    end as reject_rule
from base
