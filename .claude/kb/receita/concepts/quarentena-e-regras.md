# Quarentena: `reject_rule` = `failure_key`

Silver classifica 100% das linhas; a primeira regra violada vira `reject_rule`. Regras: `invalid_cnpj`, `duplicate_key`, `invalid_date`, `invalid_domain`, `invalid_capital`, `encoding_mojibake`, `orphan_socio`. Órfãos de domínio publicado viram flag `_orphan_*` (monitorados só CNAE, município e natureza). Gold lê apenas aceitas; `tests/no_reject_leaks_to_gold.sql` prova (AC-4).

Nova regra = WHEN no `_classificado` + `accepted_values` + falha no `chaos/failures.py` (o e2e cobre sozinho).
