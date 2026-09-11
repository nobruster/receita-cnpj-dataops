{{ config(materialized='view') }}
select * exclude (reject_rule) from {{ ref('silver_socios_classificado') }} where reject_rule is null
