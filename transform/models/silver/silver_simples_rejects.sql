select reject_rule, * exclude (reject_rule) from {{ ref('silver_simples_classificado') }} where reject_rule is not null
