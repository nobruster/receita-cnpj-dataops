select
    upper({{ txt('cnpj_basico') }})                   as cnpj_basico,
    {{ txt('identificador_socio') }}                  as identificador_socio,
    {{ txt('nome_socio') }}                           as nome_socio,
    {{ txt('cnpj_cpf_socio') }}                       as cnpj_cpf_socio,
    lpad({{ txt('qualificacao_socio') }}, 2, '0')     as qualificacao_socio,
    {{ rfb_date('data_entrada_sociedade') }}          as data_entrada_sociedade,
    {{ rfb_date_invalida('data_entrada_sociedade') }} as _data_entrada_invalida,
    lpad({{ txt('pais') }}, 3, '0')                   as pais,
    -- '***000000**' = sem representante legal (97% das linhas); vira NULL
    nullif({{ txt('representante_legal') }}, '***000000**') as representante_legal,
    {{ txt('nome_representante') }}                   as nome_representante,
    nullif(lpad({{ txt('qualificacao_representante') }}, 2, '0'), '00') as qualificacao_representante,
    {{ txt('faixa_etaria') }}                         as faixa_etaria,
    _arquivo, _competencia, _carregado_em
from {{ source('raw', 'raw_socios') }}
