# Evidência PRD: corte do publicador antigo e M1–M5

Modelo a preencher pelo Bruno depois da execução real em PRD. Os evals da T-014 só provam o conteúdo dos arquivos; a prova do corte e de M1 a M5 é este documento preenchido. Prazo: 2026-10-17. Sem segredos neste arquivo.

## Execução

| Campo | Valor |
|---|---|
| Data/hora (UTC) | |
| Executor | Bruno |
| Commit do repositório | |
| Ambiente | PRD |

## Passos do corte (runbook seção 4)

- [ ] DAG antiga pausada e sem execuções em andamento
- [ ] `.env` com `PUBLISH_TABLES=gold_resumo_competencia`
- [ ] `sql/003_cutover_dono.sql` aplicado com psql (saída dos NOTICE abaixo)
- [ ] DAG nova `publicar_gold_bi` ligada e executada (run id: )

Saída do psql (003):

```
(colar aqui)
```

## Verificação M1–M5

Comando: `python scripts/verificar_m1_m5.py` (somente leitura; `PG_PASSWORD` e `BI_READER_PASSWORD` do `.env`).

| Métrica | Critério | Resultado (PASS/FAIL) | Detalhe |
|---|---|---|---|
| M1 | tabelas trocadas de gold pertencem a `publisher` | | |
| M2 | `bi_reader` faz SELECT em todas as tabelas de gold | | |
| M3 | `gold_resumo_competencia` segue com dono `cnpj`, com linhas e legível | | |
| M4 | nenhuma tabela `__novo` em gold | | |
| M5 | toda tabela de gold com contagem de linhas > 0 | | |

Saída completa do script:

```
(colar aqui)
```

## Histórico preservado

| Item | Antes do corte | Depois do corte |
|---|---|---|
| Linhas de `gold.gold_resumo_competencia` | | |
| Dono de `gold.gold_resumo_competencia` | cnpj | cnpj |

## Rollback

Sem versão anterior no Postgres depois do COMMIT: o rollback é reprocessar a partir do DuckDB. Registre aqui se foi necessário: ____

## Aceite

- Aceito por: ____
- Data: ____
