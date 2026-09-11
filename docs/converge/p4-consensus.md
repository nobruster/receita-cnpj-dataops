# Passo 4 · Consensus — ataque adversarial e resolução

- **Adversário:** subagente com **outro modelo** (Claude Sonnet) e **sem memória** de ter escrito os planos. É o *fallback* previsto pelo método quando o Codex não está disponível. A instrução foi refutar, com "default to refuted".
- **Defesa e revisão:** o autor dos planos.
- **Verdade de referência:** `engineering-brief.md`, `tech-spec.md` e o código.
- **Regra do gate:** nada é descartado em silêncio. Cada objeção vira **FIX** (corrigido no plano e/ou no código) ou **ACCEPT** (risco aceito com dono e motivo).

## Objeções (na ordem de dano dada pelo adversário)

| # | Objeção | Decisão | Onde foi resolvida |
|---|---|---|---|
| O1 | O "AC-6" do `pipeline/evals.py` mede a nota do Sentinel (fase 2), mas o AC-6 do brief é reprocessamento idêntico. O relatório engana | **FIX** | `evals.py`: a linha do Sentinel passa a se chamar **F2-1** e entra o eval real do AC-6 (`--reprocessar`: roda de novo carga + dbt + monitores e compara as métricas). Plano B renomeado. Task T-004 |
| O2 | O AC-2 é medido a partir do início do **download** (o brief diz "com os arquivos locais"). O `baixar` com `8h × (1+3 retries)` pode passar de 30 h sozinho, o que torna o AC-3 (≤ 24 h) inatingível pelo desenho | **FIX** + **ACCEPT** parcial | Nova coluna `processamento_iniciado_em` (gravada no início da carga): AC-2 = conclusão − início do processamento; AC-3 = conclusão − `detectado_em`. `baixar` passa a `execution_timeout=6h`, `retries=2` (pior caso ~18 h de download + ≤ 4 h de processamento ≤ 24 h). **Aceito:** se o servidor da Receita sustentar menos de ~95 KB/s em média, o AC-3 falha por causa externa, e o relatório diz isso. Dono: Bruno. Task T-002 |
| O3 | Sentinel e MCP sobem por padrão, contra a decisão D-3 | **FIX** | `docker-compose.yml`: `profiles: [fase2]`. Comentário do compose, GUIA e `cnpj.ps1` atualizados. Task T-001 |
| O4 | A ordem de build põe o item mais caro (C4a, que cobre o AC-8 inteiro) atrás de correções triviais | **FIX** | Ordem revista no Plano A: **C4a primeiro**, depois G2/G3, G5, G6 e o eval do AC-6. Task T-003 |
| O5 | Escritores fora do Airflow (`pipeline.run`, `chaos.cli`) não passam pelo pool | **FIX** parcial + **ACCEPT** | O próprio DuckDB já recusa um segundo escritor (trava de arquivo), então não há corrupção possível. `connect_rw` agora traduz o `IOException` numa mensagem clara ("outro processo está escrevendo — a DAG está rodando?"). **Aceito:** rodar CLI de escrita com a DAG ativa falha em vez de esperar. Documentado no GUIA. Dono: Bruno. Task T-005 |
| O6 | A premissa de memória (P-02) não é verificada: `DUCKDB_MEMORY_LIMIT=8GB` num container com menos RAM leva a OOM silencioso | **FIX** | `warehouse._pragmas` limita o `memory_limit` efetivo a **60% da memória do container** (lida do cgroup) e loga quando reduz. Task T-005 |
| O7 | Comentário com "job Dagster" em `warehouse.py`: sinal de claim copiado da referência sem conferir | **FIX** | Comentário corrigido e varredura de "Dagster" fora dos docs de comparação. Task T-005 |

## Drifts contra os documentos

| Drift | Decisão |
|---|---|
| Tech spec (Camada 6) diz que "fonte indisponível" e "publicação atrasada" são v1, mas não há detector, e `dq_stale_days` é configuração morta | **FIX**: `source_unavailable` (discover com falha de rede) e `stale_release` (última publicação há mais de `DQ_STALE_DAYS` dias) viram incidentes `monitor`, e o chaos ganha a falha `source_unavailable` (T-002) |
| O Plano B chama a nota do Sentinel de "antigo AC-6" e reproduz a ambiguidade do G7 | **FIX**: renomeado para critério **F2-1** |
| Compose × D-3 | **FIX** (O3) |
| Medição do AC-2 | **FIX** (O2) |
| `evals.py` com "AC-6" ativo e errado | **FIX** (O1) |
| BRD (seção 8) com numeração de AC própria (G7) | **FIX**: o BRD ganha uma nota apontando o brief como fonte canônica dos ACs, e a tabela é realinhada |

## Perguntas em aberto
| Item | Dono | Bloqueia o build? |
|---|---|---|
| Velocidade real do servidor da Receita (define se o AC-3 é atingível) | Bruno: medir na primeira carga real | Não |
| Hardware real de referência (RAM e disco da máquina) para o AC-2 | Bruno | Não |
| Nota do Sentinel com LLM real (F2-1) | Bruno: fase 2, com `OPENAI_API_KEY` | Não (fora do v1) |
| Retomar a decisão D-2 (LGPD) se o uso deixar de ser pessoal | Bruno | Não |

**Gate:** nenhuma objeção ficou sem destino, e a interface I1–I5 sobreviveu (o adversário não apontou superfície faltando; `source_unavailable` entra na I1/I4). Os planos seguem para a decomposição em tasks.
