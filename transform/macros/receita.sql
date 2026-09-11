{#
  Macros de normalização do layout da Receita.
  Todas geram SQL inline (DuckDB) — nada de UDF, para rodar igual em qualquer versão.
#}

{# Texto: trim e vazio -> NULL #}
{% macro txt(col) -%}
    nullif(trim({{ col }}), '')
{%- endmacro %}

{# Data AAAAMMDD; '0', '00000000' e vazio viram NULL (placeholder da Receita, não é defeito) #}
{% macro rfb_date(col) -%}
    case when nullif(trim({{ col }}), '') is null or trim({{ col }}) in ('0', '00000000') then null
         else try_strptime(trim({{ col }}), '%Y%m%d')::date end
{%- endmacro %}

{# TRUE quando existe valor real que não é data válida entre 1900-01-01 e hoje #}
{% macro rfb_date_invalida(col) -%}
    (nullif(trim({{ col }}), '') is not null and trim({{ col }}) not in ('0', '00000000')
     and ({{ rfb_date(col) }} is null
          or {{ rfb_date(col) }} < date '1900-01-01'
          or {{ rfb_date(col) }} > current_date))
{%- endmacro %}

{# Valor monetário "1.234,56" -> DECIMAL(18,2); NULL se não converter #}
{% macro rfb_money(col) -%}
    try_cast(replace(replace(trim({{ col }}), '.', ''), ',', '.') as decimal(18, 2))
{%- endmacro %}

{# Detecta UTF-8 lido como latin-1 (ex.: "Ã£" no lugar de "ã") #}
{% macro mojibake(col) -%}
    coalesce(regexp_matches({{ col }}, '[ÃÂ][\x{80}-\x{BF}]'), false)
{%- endmacro %}

{#
  Dígito verificador do CNPJ (numérico e alfanumérico — IN RFB 2.229/2024).
  Cada caractere vale ascii(c) - 48 (0-9 => 0..9, A-Z => 17..42); módulo 11,
  pesos 5,4,3,2,9,8,7,6,5,4,3,2 (DV1) e 6,5,4,3,2,9,8,7,6,5,4,3,2 (DV2).
  Recebe a expressão da base de 12 caracteres (cnpj_basico || cnpj_ordem).
#}
{% macro cnpj_dv(base) -%}
    {%- set w1 = [5,4,3,2,9,8,7,6,5,4,3,2] -%}
    {%- set w2 = [6,5,4,3,2,9,8,7,6,5,4,3] -%}
    {%- set s1 -%}({% for w in w1 %}(ascii(substr({{ base }}, {{ loop.index }}, 1)) - 48) * {{ w }}{% if not loop.last %} + {% endif %}{% endfor %}){%- endset -%}
    {%- set d1 -%}(case when {{ s1 }} % 11 < 2 then 0 else 11 - ({{ s1 }} % 11) end){%- endset -%}
    {%- set s2 -%}({% for w in w2 %}(ascii(substr({{ base }}, {{ loop.index }}, 1)) - 48) * {{ w }} + {% endfor %}{{ d1 }} * 2){%- endset -%}
    (cast({{ d1 }} as varchar) || cast(case when {{ s2 }} % 11 < 2 then 0 else 11 - ({{ s2 }} % 11) end as varchar))
{%- endmacro %}
