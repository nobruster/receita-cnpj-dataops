with empresas as (
    select distinct cnpj_basico from {{ ref('bronze_empresas') }} where cnpj_basico is not null
),

classificado as (
    select
        s.*,
        case
            when not coalesce(regexp_full_match(s.cnpj_basico, '[0-9A-Z]{8}'), false) then 'invalid_cnpj'
            when e.cnpj_basico is null then 'orphan_socio'
            when s._data_entrada_invalida then 'invalid_date'
            when coalesce(s.identificador_socio, '') not in ('1', '2', '3')
              or coalesce(s.faixa_etaria, '') not in (select codigo from {{ ref('dom_faixa_etaria') }})
                then 'invalid_domain'
            when {{ mojibake("coalesce(s.nome_socio, '')") }} then 'encoding_mojibake'
        end as reject_rule
    from {{ ref('bronze_socios') }} s
    left join empresas e on e.cnpj_basico = s.cnpj_basico
)

select
    c.*,
    (c.qualificacao_socio is not null and q.codigo is null) as _orphan_qualificacao
from classificado c
left join {{ ref('silver_dom_qualificacoes') }} q on q.codigo = c.qualificacao_socio
