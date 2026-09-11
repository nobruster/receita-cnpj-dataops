-- Uma linha por (estabelecimento, CNAE secundário): prospecção por atividade secundária.
with explodido as (
    select cnpj, cnpj_basico, uf, municipio, trim(unnest(string_split(cnae_fiscal_secundaria, ','))) as cnae
    from {{ ref('silver_estabelecimentos') }}
    where cnae_fiscal_secundaria is not null
)
select x.cnpj, x.cnpj_basico, x.uf, x.municipio, x.cnae, c.descricao as cnae_descricao
from explodido x
left join {{ ref('silver_dom_cnaes') }} c on c.codigo = x.cnae
where x.cnae <> ''
