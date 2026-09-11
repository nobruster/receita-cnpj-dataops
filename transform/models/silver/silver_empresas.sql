{{ config(materialized='view') }}
select * exclude (reject_rule) from {{ ref('silver_empresas_classificado') }} where reject_rule is null
