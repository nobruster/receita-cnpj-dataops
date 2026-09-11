-- AC-4: nenhum CNPJ quarentenado pode aparecer no gold (teste singular: 0 linhas = passa).
select g.cnpj
from {{ ref('gold_empresa_detalhe') }} g
join {{ ref('silver_estabelecimentos_rejects') }} r on r.cnpj = g.cnpj and r.reject_rule <> 'duplicate_key'
