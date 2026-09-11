# Especificação técnica — Plataforma DataOps do CNPJ

> Entrada do **Passo 2 (Structure)** do Converge. Deriva do `engineering-brief.md` (o *quê*) e das decisões do projeto (Airflow + DuckDB; OpenAI na fase 2). Os critérios de aceite são os do brief (AC-1..AC-8).

## 1. Dois sistemas lógicos

O sistema tem **dois sistemas lógicos distintos**:

- **Backbone de dados (Camadas 1–5, determinístico).** Verificado por asserção.
- **Motor de DataOps autônomo — Sentinel (Camada 6, probabilístico).** Pontuado contra verdade de referência. **Fase 2** (decisão D-3 do brief).

A dependência é de mão única: o Sentinel lê o que o backbone produz e o backbone nunca depende do Sentinel.

## 2. Camadas

### Camada 1 — Fonte
- Repositório SERPRO+ da Receita: compartilhamento Nextcloud público, via WebDAV `/public.php/webdav` com usuário = token. Uma pasta `AAAA-MM` por competência.
- **Contrato do arquivo:** 37 zips (Empresas0–9, Estabelecimentos0–9, Socios0–9, Simples e 6 domínios). Cada zip contém 1 CSV sem cabeçalho, com `;`, aspas `"` e ISO-8859-1 (na prática aparecem bytes cp1252). Layout conforme `cnpj-metadados.pdf`.
- **Landing:** `/data/landing/AAAA-MM/` com `_manifest.json` (tamanho, etag, last-modified).

### Camada 2 — Ingestão (Airflow 3.3, LocalExecutor)
- A DAG `receita_cnpj_mensal` roda diariamente e só trabalha se houver competência nova, ou se uma competência for forçada por parâmetro.
- **Download:** paralelo, retoma por `Range`, detecta download travado e valida CRC do zip.
- **Carga raw no DuckDB:** fiel ao arquivo, tudo VARCHAR, uma competência por vez. O layout é checado antes da carga e o encoding tem fallback.
- **Contrato de falha:** a linha `PIPELINE_FAILURE key=<failure_key> ...` em `/data/logs/pipeline.log` e um incidente `origin='pipeline'` no ledger.

### Camada 3 — Transformação (dbt-duckdb)
- **bronze** (views): nomes estáveis e tipagem tolerante.
- **silver:**
  - `*_classificado` com `reject_rule`; `reject_rule` é o `failure_key`;
  - `*` com as linhas aceitas;
  - `*_rejects` com a quarentena.
- **gold:** ficha, sócios, rede societária, CNAE secundário, painel de prospecção e resumo da competência.
- **Seeds:** domínios que a Receita não publica.

### Camada 4 — Warehouse e histórico
- **DuckDB** `/data/warehouse/cnpj.duckdb` com um único escritor, garantido por um pool de 1 vaga no Airflow.
- **Arquivo histórico (AC-8):** cada competência concluída exporta o silver aceito para Parquet em `/data/history/competencia=AAAA-MM/<entidade>.parquet`, com retenção de 12 competências. A comparação entre duas competências é feita por consulta sobre o Parquet, sem precisar do raw.

### Camada 5 — Consumo
- **PostgreSQL:** as tabelas gold escolhidas são publicadas por `COPY` em streaming, com troca atômica. `gold_resumo_competencia` acumula histórico.
- **Consultas curadas:** biblioteca de intenções somente leitura (ficha, quadro, rede, prospecção, painel, resumo). É a base do AC-5.
- **Servidor MCP sobre as intenções:** fase 2.

### Camada 6 — Monitoramento
- **v1 — monitores determinísticos:**
  - volume versus a competência anterior;
  - explosão de quarentena por regra;
  - órfãos de domínio monitorados;
  - erros de leitura;
  - **fonte indisponível** e **publicação atrasada**.

  Todos abrem incidentes no ledger `ops`.
- **Fase 2 — Sentinel CrewAI:**
  - gerente (`gpt-5.6-terra`) e especialistas (`gpt-5.6-luna`);
  - gatilho por polling do ledger, fluxo determinístico para cascatas e pontuação contra `origin='chaos'`.

## 3. Ledger `ops` (PostgreSQL)
| Tabela | Conteúdo |
|---|---|
| `competencias` | Status por competência (`descoberta → baixando → baixada → carregada → transformada → publicada | falhou`), **`detectado_em`**, `publicada_em`, `iniciado_em`, `finalizado_em` e bytes |
| `dq_metrics` | Métricas por competência e entidade |
| `incidents` | `failure_key`, `origin` (pipeline, monitor ou chaos), evidência e status |
| `diagnoses` | Veredito do Sentinel e nota (fase 2) |

## 4. Interfaces do backbone para o Sentinel (somente leitura)
| ID | Superfície |
|---|---|
| I1 | `pipeline.log` |
| I2 | `run_results.json` do dbt |
| I3 | DuckDB silver/gold, aberto read-only a cada chamada |
| I4 | `ops.dq_metrics` e `ops.incidents` (sem chaos) |
| I5 | Histórico de post-mortems e `ops.diagnoses` |

## 5. Implantação
- Docker Compose com os serviços `postgres`, `airflow-init`, `airflow-setup`, `airflow-apiserver`, `airflow-scheduler` e `airflow-dag-processor`.
- **Perfil `fase2`:** `sentinel` e `mcp`. **Perfil `ollama`:** LLM local opcional.
- Volume de dados `/data`, nomeado ou por bind.

## 6. Requisitos não funcionais
- **Idempotência (AC-6):** reprocessar gera as mesmas contagens. O raw é recriado, o dbt é recriado e as métricas usam upsert.
- **Recursos:** `DUCKDB_MEMORY_LIMIT` e `DUCKDB_THREADS`, com spill em `/data/work/duckdb_tmp`.
- **Retenção:**
  - zips no landing: 2 competências;
  - histórico Parquet: 12 competências.
- **Segurança:** segredos só no `.env`; SQL parametrizado; leitores somente leitura.

## 7. Mapa AC → componente
| AC | Componente(s) |
|---|---|
| AC-1 | C2 carga + `raw_load_log` |
| AC-2 | C2 + C3 (tempos em `ops.competencias`) |
| AC-3 | C1 descoberta (`detectado_em`) → conclusão |
| AC-4 | C3 silver + teste `no_reject_leaks_to_gold` |
| AC-5 | C5 consultas curadas |
| AC-6 | C2–C3 + eval de reprocessamento |
| AC-7 | C1/C2 falhas de pipeline + C6 monitores, provados pelo chaos |
| AC-8 | C4 arquivo histórico Parquet |
