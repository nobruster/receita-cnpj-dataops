{{ config(materialized='view') }}
select * exclude (reject_rule)
from {{ ref('silver_estabelecimentos_classificado') }}
where reject_rule is null
