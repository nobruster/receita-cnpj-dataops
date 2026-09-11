-- Bronze: nomes estáveis, trim, tipagem tolerante (TRY_*). Nada é descartado aqui.
select
    upper({{ txt('cnpj_basico') }})                    as cnpj_basico,
    {{ txt('razao_social') }}                          as razao_social,
    lpad({{ txt('natureza_juridica') }}, 4, '0')       as natureza_juridica,
    lpad({{ txt('qualificacao_responsavel') }}, 2, '0') as qualificacao_responsavel,
    {{ txt('capital_social') }}                        as capital_social_raw,
    {{ rfb_money('capital_social') }}                  as capital_social,
    lpad({{ txt('porte') }}, 2, '0')                   as porte,
    {{ txt('ente_federativo_responsavel') }}           as ente_federativo_responsavel,
    _arquivo, _competencia, _carregado_em
from {{ source('raw', 'raw_empresas') }}
