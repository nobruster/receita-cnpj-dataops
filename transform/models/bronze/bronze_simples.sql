select
    upper({{ txt('cnpj_basico') }})                   as cnpj_basico,
    upper({{ txt('opcao_simples') }})                 as opcao_simples,
    {{ rfb_date('data_opcao_simples') }}              as data_opcao_simples,
    {{ rfb_date('data_exclusao_simples') }}           as data_exclusao_simples,
    upper({{ txt('opcao_mei') }})                     as opcao_mei,
    {{ rfb_date('data_opcao_mei') }}                  as data_opcao_mei,
    {{ rfb_date('data_exclusao_mei') }}               as data_exclusao_mei,
    ({{ rfb_date_invalida('data_opcao_simples') }} or {{ rfb_date_invalida('data_exclusao_simples') }}
     or {{ rfb_date_invalida('data_opcao_mei') }} or {{ rfb_date_invalida('data_exclusao_mei') }}) as _data_invalida,
    _arquivo, _competencia, _carregado_em
from {{ source('raw', 'raw_simples') }}
