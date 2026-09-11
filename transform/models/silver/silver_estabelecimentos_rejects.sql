-- Quarentena: guardada para auditoria e para o Data Profiler do Sentinel.
select reject_rule, * exclude (reject_rule)
from {{ ref('silver_estabelecimentos_classificado') }}
where reject_rule is not null
