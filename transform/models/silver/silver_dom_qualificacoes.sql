-- Domínio deduplicado por código (evita multiplicar linhas nos joins do gold)
select codigo, descricao, _competencia
from {{ ref('bronze_qualificacoes') }}
where codigo is not null
qualify row_number() over (partition by codigo order by descricao) = 1
