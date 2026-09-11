select
    lpad({{ txt('codigo') }}, 2, '0') as codigo,
    {{ txt('descricao') }}            as descricao,
    _arquivo, _competencia
from {{ source('raw', 'raw_motivos') }}
