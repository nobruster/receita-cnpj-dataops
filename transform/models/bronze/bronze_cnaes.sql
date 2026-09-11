select
    lpad({{ txt('codigo') }}, 7, '0') as codigo,
    {{ txt('descricao') }}            as descricao,
    _arquivo, _competencia
from {{ source('raw', 'raw_cnaes') }}
