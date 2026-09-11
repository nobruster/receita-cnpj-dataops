# Passo 2 · Structure — entendimento aterrado no repositório

> No método original, o Passo 2 não gera arquivo: o entendimento fica na sessão. Aqui ele foi executado por um agente, e o próprio método manda que um passo sem ninguém acompanhando **emita o mapa como arquivo** ("have it emit the component map as a file so the next step has an input"). É este arquivo.

## 1. O sistema, de ponta a ponta
1. **Descoberta e download.** Todo dia a DAG pergunta ao WebDAV do SERPRO+ qual é a última competência. Se ela ainda não foi concluída, baixa os 37 zips para o landing, com retomada e validação de CRC.
2. **Carga raw.** A carga lê cada zip, checa o layout e grava o raw no DuckDB (texto puro, uma competência).
3. **Medalhão.** O dbt tipa (bronze), classifica toda linha e separa a quarentena (silver) e monta as tabelas de consumo (gold).
4. **Monitores.** Medem a competência contra a anterior e abrem incidentes.
5. **Publicação.** As tabelas escolhidas vão para o Postgres.
6. **Fase 2.** O Sentinel lê incidentes e superfícies e diagnostica.

## 2. Spec × repositório × brief — o que morderia se decompuséssemos como está

| # | Lacuna | Evidência no repositório | Critério afetado |
|---|---|---|---|
| G1 | **Não existe arquivo histórico.** O raw guarda 1 competência e só as métricas têm histórico | `loader._create_raw_table` usa `CREATE OR REPLACE`; não há export Parquet | **AC-8** sem cobertura |
| G2 | **O frescor é medido da publicação, não da detecção.** Não existe `detectado_em` | `evals.py` usa `publicada_em`; `discover` não grava a hora | **AC-3** mede outra coisa |
| G3 | **Fonte fora do ar não vira incidente.** `discover` não é `@step`, então um erro de rede só falha a tarefa | `steps.discover` sem tratamento | **AC-7** incompleto ("fonte fora do ar") |
| G4 | **A idempotência não é medida.** Nenhum eval reprocessa e compara | `evals.py` não tem AC-6 | **AC-6** sem prova |
| G5 | **Escopo:** Sentinel e MCP sobem por padrão no compose, mas o brief os tira do v1 (D-3) | `docker-compose.yml` sem profile | Escopo |
| G6 | **A retenção de zips no landing é manual.** ~6 GB/mês acumulam | GUIA seção 6 | RNF de retenção |
| G7 | Os ACs do BRD (8) e do brief (8) têm **números diferentes**. O brief manda (AC-5 = consulta, AC-6 = reprocessamento etc.) | BRD seção 8 × brief seção 05 | Rastreabilidade |

## 3. Mapa de componentes, dependências e ordem de build

```text
C0 Fundação (compose, .env, config, ledger ops)
 └─ C1 Fonte (layout, WebDAV, descoberta)          ── depende de C0
     └─ C2 Ingestão (download, landing, raw, DAG)    ── depende de C1
         └─ C3 Transformação (bronze/silver/gold)     ── depende de C2
             ├─ C4 Warehouse + C4a Arquivo histórico  ── depende de C3
             ├─ C6 Monitores de qualidade              ── depende de C3 (+ histórico de métricas)
             └─ C5 Consumo (Postgres, consultas)       ── depende de C3/C4
C7 Chaos (amostra + falhas)  ── depende de C1 (layout); prova C2/C3/C6 (AC-7)
─────────────────────────────────────────────── fase 2
B  Sentinel (crew, fluxo, gatilho, nota)  ── lê I1–I5; depende de C2, C3, C6, C7
C5m Servidor MCP                         ── depende de C5
```

**Ordem:** C0 → C1 → C2 → C3 → (C4/C4a, C6, C5 em paralelo) → C7 → [fase 2] B, C5m.

## 4. Pendências sinalizadas (seguem para o Passo 3)
- G1–G6 viram itens de plano no `sketch/`.
- G7 é resolvido declarando o **brief como fonte dos ACs** e ajustando o BRD.
