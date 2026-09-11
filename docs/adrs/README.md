# ADRs — registros de decisão arquitetural

Um ADR grava **uma decisão** que foi cara de tomar: o contexto do momento, a escolha e o que ela
custa. Não é documentação de uso (isso é o [`GUIA.md`](../GUIA.md)) nem desenho vigente (isso é a
[`ARQUITETURA.md`](../ARQUITETURA.md)). É o "por que está assim", para que ninguém — pessoa ou
agente — reabra a discussão em silêncio seis meses depois.

Regra R4 da frota: decisão registrada aqui só muda com um ADR novo.

---

## Log

| ADR | Título | Status | Decide |
|---|---|---|---|
| [0001](0001-backbone-airflow-duckdb.md) | Backbone: Airflow + DuckDB + dbt, raw fiel e quarentena | aceito (2026-09-11) | Airflow 3 no lugar de Dagster; DuckDB como motor; raw fiel ao arquivo; quarentena em vez de descarte; publicação por `COPY` com troca atômica |
| [0002](0002-sentinel-openai-polling.md) | Sentinel: crew hierárquico via OpenAI, gatilho por polling, nota contra verdade | aceito (2026-09-11) | LLM da OpenAI com dois níveis; gatilho lendo `ops.incidents`; verdade de referência escondida; rubrica de pontuação |
| [0003](0003-escopo-v1-historico-lgpd.md) | Escopo do v1, histórico mensal e risco LGPD aceito | aceito (2026-09-11) | D-3 Sentinel/MCP em fase 2; D-1 histórico Parquet de 12 meses sem carga retroativa; D-2 contatos mantidos com risco aceito; ACs canônicos são os do brief |

## Como escrever o próximo

Numere na sequência (`0004-...`), em português, e mantenha o formato curto:

```markdown
# ADR-0004 — <decisão em uma linha>

- **Status:** proposto | aceito | substituído por ADR-000X (data)
- **Contexto:** o que era verdade quando a decisão foi tomada (volume, prazo, restrição).

## Decisões
1. ...

## Consequências
- o que ficou mais fácil, o que ficou mais caro, o que passa a exigir cuidado.
```

Decisões que **não** viram ADR: escolhas reversíveis num commit (nome de variável, ordem de tarefa),
e o que já está no brief ou nas task-specs. Se a dúvida for "isso vai confundir alguém daqui a seis
meses?", vira ADR.
