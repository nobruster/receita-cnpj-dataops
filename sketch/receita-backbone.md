# Plano A — Backbone de dados do CNPJ (Camadas 1–5 + monitores)

> **Escopo:** v1. **Revisado no Passo 4** (ver `docs/converge/p4-consensus.md`). **Natureza:** determinística; cada componente é verificado por asserção contra um AC do brief. **Ids:** ver `sketch/README.md`. Os status valem para 11/09/2026 e ficam desatualizados por natureza (o plano continua sendo a referência).

## Decisões de fronteira
- **U1 · Escopo.** Fechado (D-3): Sentinel e MCP são fase 2.
- **U2 · Dono do raw.** Fechado (ADR-0001): a carga (C2) é dona do raw. O dbt começa no bronze.
- **U3 · Costura de detecção.** Fechado (ADR-0001): o defeito fica visível no **silver**, em `*_rejects` com `reject_rule` = `failure_key`, e **nunca** no gold.

## Componentes

### C0 · Fundação — construído
- Compose, `.env`, `pipeline/config.py` e o ledger `ops` (competências, métricas, incidentes, diagnósticos).
- **Pendente:**
  - G5: `sentinel` e `mcp` passam para o profile `fase2`;
  - G2: colunas `detectado_em` e `processamento_iniciado_em`. O AC-2 é medido do início do **processamento**, não do download (O2).

### C1 · Fonte — construído, com pendência
- Layout centralizado (`layout.py`), cliente WebDAV, descoberta da última competência, CNPJ alfanumérico (`cnpj.py`) e modo offline.
- **Pendente:**
  - G3: fonte fora do ar vira incidente `source_unavailable`;
  - **atraso de publicação** vira `stale_release`: nenhuma competência nova há mais de `DQ_STALE_DAYS` dias.
- **Depende de:** C0. **Atende:** AC-3, AC-7.

### C2 · Ingestão — construída
- DAG `receita_cnpj_mensal` (9 tarefas, pool `duckdb_writer`), download com retomada, carga raw com checagem de layout, fallback de encoding e `raw_load_log`.
- **Pendente (G6):** a tarefa `limpar_landing` mantém só as 2 últimas competências de zips.
- **Timeouts (O2):** `baixar` fica com `execution_timeout=6h` e `retries=2`, ou seja, ~18 h no pior caso. Somado ao processamento de ≤ 4 h, cabe no AC-3. **Risco aceito:** servidor abaixo de ~95 KB/s em média estoura o AC-3 por causa externa.
- **Depende de:** C1. **Atende:** AC-1, AC-2, AC-7.

### C3 · Transformação — construída
- dbt: bronze, silver com classificação, quarentena e flags de órfão, gold (6 modelos), seeds de domínio e testes, incluindo `no_reject_leaks_to_gold`.
- **Depende de:** C2. **Atende:** AC-4.

### C4 · Warehouse — construído
- DuckDB com um único escritor. Leitores abrem read-only por chamada, com nova tentativa.
- **Endurecimento (O5/O6):**
  - um segundo escritor fora do Airflow falha com mensagem clara (a trava de arquivo do DuckDB impede corrupção);
  - o `memory_limit` efetivo fica em no máximo 60% da memória do container.

### C4a · Arquivo histórico — **a construir** (G1)
- **Tarefa `arquivar_historico`:** ao fim de cada competência, o silver aceito (empresas, estabelecimentos, sócios, simples) vai para `/data/history/competencia=AAAA-MM/<entidade>.parquet` (zstd).
- Retenção de 12 competências.
- **Consulta `diferenca_competencias(a, b)`:** CNPJs que mudaram de situação e sócios que entraram ou saíram.
- **Depende de:** C3. **Atende:** AC-8.

### C5 · Consumo — construído
- Publicação no Postgres (`COPY` em streaming, troca atômica) e consultas curadas (`intelligence/intents.py`), que são a base do AC-5.
- O servidor MCP é fase 2.
- **Depende de:** C3/C4. **Atende:** AC-5.

### C6 · Monitores — construídos, com pendência
- Volume versus a competência anterior, explosão de quarentena, órfãos monitorados e erros de leitura.
- **Pendente:** `source_unavailable` e `stale_release` (C1).
- **Depende de:** C3 + histórico em `ops.dq_metrics`. **Atende:** AC-7.

### C7 · Chaos — construído
- Amostra sintética no formato da Receita e 12 falhas injetáveis, com verdade gravada em `ops.incidents`.
- **Pendente:** falha `source_unavailable`, que simula WebDAV fora do ar para provar o AC-7 completo.
- Serve de prova para C2, C3 e C6.

## Ordem de build
C0 → C1 → C2 → C3 → {C4, C4a, C5, C6} → C7.

Pendências, revistas no Passo 4 (O4): **C4a (AC-8) → G2 + O2 (tempos e timeouts, AC-2/AC-3) → G3 (`source_unavailable`/`stale_release`, AC-7) → G5 (profile `fase2`) → G6 (retenção) → eval do AC-6 → endurecimento (O5, O6, O7)**. As tasks correspondentes estão em `tasks/`.

## Mapa de ACs
| AC | Prova | Status |
|---|---|---|
| AC-1 | `raw_load_log` (C2) | construído; falta rodar com uma competência real |
| AC-2 | Tempos em `ops.competencias` | construído; falta medir no real |
| AC-3 | `detectado_em → finalizado_em` | **G2 → T-002** |
| AC-4 | Teste dbt e eval | construído |
| AC-5 | Bateria de consultas curadas | construído |
| AC-6 | `pipeline.evals --reprocessar` (compara métricas antes e depois) | **G4 → T-004** |
| AC-7 | e2e do chaos com todas as falhas + `source_unavailable` | parcial (**G3 → T-002**) |
| AC-8 | Arquivo histórico e consulta de diferença | **G1 → T-003** |

## Riscos conhecidos (vão para o Passo 4)
- O volume real ainda não foi exercitado: AC-1 e AC-2 só foram medidos com amostra.
- O servidor da Receita é lento: o download de ~6 GB pode estourar a janela de 24 h (AC-3).
- A leitura concorrente durante a DAG espera o escritor terminar.
