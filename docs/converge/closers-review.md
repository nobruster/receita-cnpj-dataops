# Gate dos closers (T-20260911-06)

> Regra R11: reviewer → simplifier → fix → documenter. Nenhum achado fica sem destino.
> Reviewer independente: subagente `general-purpose` em contexto novo, lendo o repositório inteiro
> depois de T-01..T-05. Cada achado virou **FIX** (com teste de regressão quando testável) ou **ACEITO**
> (risco registrado com dono).

## Resultado

| # | Sev. | Achado | Destino | Onde | Prova |
|---|---|---|---|---|---|
| 1 | alto | SQL de consulta (usuário e LLM) lia qualquer arquivo do container (`read_text('/proc/self/environ')`, `read_csv_auto`, `FROM 'arq.parquet'`, tabela depois de vírgula) | FIX | `warehouse.connect_ro` com `enable_external_access=False` + `lock_configuration=True`; `sql_guard` confere tabelas pelo parser (`duckdb.get_table_names(qualified=True)`) e bloqueia `read_*`, `query`, `glob`, `getenv` | `test_revisao::test_leitura_sem_acesso_a_arquivos` |
| 2 | alto | Leitor aberto derrubava a tarefa que escreve | FIX | `connect_rw` e `steps.dbt` esperam o lock até `DUCKDB_LOCK_WAIT_S` (600 s); depois, `WarehouseBusyError` com mensagem clara | `test_endurecimento::test_escritor_espera_leitor_soltar`, `::test_segundo_escritor_recebe_mensagem_clara` |
| 3 | alto | Sentinel diagnosticava caso em andamento; `mark_incidents` escrevia em `ops.incidents` (viola R3) | FIX | `competencias.atualizado_em`; o gatilho exige `atualizado_em >= max(detected_at)`; "diagnosticado" passa a ser **citado em `ops.diagnoses`** (`ops.UNDIAGNOSED`); `mark_incidents` removido | `test_revisao::test_sentinel_nao_pega_caso_em_andamento` |
| 4 | médio-alto | `.part` corrompido nunca era descartado → `corrupt_zip` eterno | FIX | ETag salvo em `.part.etag`; `.part` de outra versão ou maior que o remoto é descartado; CRC/tamanho falhou → apaga e baixa inteiro uma vez | `test_webdav::test_part_de_outra_versao_e_descartado`, `::test_part_corrompido_do_mesmo_tamanho_e_rebaixado` |
| 5 | médio | dbt ignorava o teto de 60% da RAM (O6) | FIX | `steps.dbt` passa `effective_memory_limit` ao dbt | `test_endurecimento::test_teto_de_memoria_reduz_nunca_aumenta` |
| 6 | médio | Exceção genérica (httpx, psycopg, lock) não virava incidente e travava o status | FIX | `@step` captura tudo: `PipelineFailure` → sua chave; `WarehouseBusyError` → `warehouse_busy`; resto → `pipeline_error`; status `falhou` | `test_revisao::test_falha_generica_vira_incidente_e_status_final` |
| 7 | médio | `evals --reprocessar` podia rodar entre tarefas da DAG e marcar `falhou` | FIX | SKIP se houver qualquer status não final (fora `fonte`), sem métricas ou se não for a última; erro de dbt vira linha FAIL, não muda status | `test_evals::test_reprocessar_*` |
| 8 | médio | Forçar competência antiga deixava gold/Postgres parados no mês velho | FIX | `discover(force)` recusa competência anterior à última processada; meses antigos só pelo histórico Parquet (`diferenca`) | `test_revisao::test_forcar_competencia_antiga_e_recusado` |
| 9 | médio | Publicação não atômica, sem `lock_timeout`, quebrava com coluna nova | FIX | `publish_all`: uma transação, `SET LOCAL lock_timeout='60s'`, tabelas `__novo` + troca no fim; `gold_resumo_competencia` ganha colunas novas | `test_revisao::test_publicacao_em_uma_transacao_e_colunas_novas` |
| 10 | médio | MCP HTTP sem autenticação exposto na LAN | FIX | todas as portas em `127.0.0.1` (Postgres 5433, Airflow 8080, MCP 8000) | revisão do `docker-compose.yml` |
| 11 | médio | `query_warehouse` mandava até 50 linhas de qualquer coluna ao LLM | FIX | limite de 20 linhas + denylist `PII_COLUMNS` (e-mail, telefones, nome/CPF de sócio, endereço). A consulta roda sobre views **sem** essas colunas (`warehouse.connect_ro_masked`); o bloqueio só por nome era contornável com `SELECT g FROM gold.x g` (linha inteira como STRUCT), achado no documenter | `test_revisao::test_llm_nao_alcanca_coluna_pessoal` |
| 12 | médio | `cnpj.ps1 rodar AAAA-MM` gerava JSON inválido no PowerShell 5.1 | FIX | o JSON é montado **dentro** do container (`json.dumps`), competência via variável de ambiente | a validar no PC (tarefa #15) |
| 13 | baixo-médio | Teste dbt `no_reject_leaks_to_gold` (AC-4) nunca rodava por seleção cautelosa | FIX | seleção da camada gold inclui o teste explicitamente | `test_revisao::test_teste_de_vazamento_do_gold_roda_no_dbt` |
| 14 | baixo | Rerun reabria incidentes duplicados | FIX | `ops.open_incident_once` (não duplica enquanto houver um não diagnosticado) | `test_revisao::test_monitor_nao_duplica_incidente` |
| 15 | baixo | Contradições de doc (fase 2 no GUIA, 9 vs 11 tarefas, limpeza manual do landing, AC-8 sem superfície, Makefile) | FIX | GUIA/README reescritos; `diferenca_competencias` no MCP e na CLI (`cnpj.ps1 diferenca`), DuckDB em memória com `memory_limit` e `temp_directory`; Makefile lê `.env` | `test_historico::test_diferenca_mostra_baixas_e_socio_novo`; eval-3 do T-06 |
| 16 | baixo | `landing_retention=0` mantinha tudo; AC-3 falso após reprocessar; `$` aceitava `\n`; `chown` podia derrubar o `up` | FIX | retenção mínima 1; `mark_detected(reset=True)` no forçado; `COMPETENCIA_RE.fullmatch`; `chown ... \|\| echo aviso` | `test_endurecimento::test_retencao_do_landing` |

Nenhum achado foi **ACEITO** sem correção. Continuam como riscos aceitos (vindos de P1/P4, não do reviewer):

- **AC-3 e servidor lento:** se a Receita entregar em média menos de ~95 KB/s, os 24 h estouram por causa externa. O eval mede e reporta (dono: Bruno).
- **D-2 / LGPD:** campos de contato mantidos como a Receita publica. Mitigado para o LLM pelo achado 11 (dono: Bruno).
- **Falha persistente:** abre um incidente por dia de execução até ser corrigida (é o alerta desejado da AC-7).

## Simplifier

- `mark_incidents` removido (o estado vive em `ops.diagnoses`).
- `publish_table` virou atalho de `publish_all`.
- A leitura com retry ficou só em `sql_guard.open_ro`, usada pelo MCP, pelo Sentinel e pela CLI `consulta`.
- Com as views mascaradas, a regra "sem `SELECT *`" do Sentinel deixou de ser necessária e saiu.

## Não verificado neste ambiente

- `docker compose up --build` em Docker real e download real da Receita (rede bloqueada no container de nuvem): tarefa #15, no PC do usuário.
