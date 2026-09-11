# Regras de operação dos agentes (adaptadas do ws-3 para a Receita)

Números (matriz de concordância, limiares) em `.claude/doctrine.yaml`. Este arquivo é o contrato em prosa.

- **R1 · Papéis.** Arquitetos (`*-architect`) planejam, sem Bash e sem código de produção; desenvolvedores (`*-developer`) entregam código + testes. Tarefa com os dois: arquiteto primeiro.
- **R2 · Aterrar toda afirmação.** Antes de afirmar API/flag de uma tecnologia, ler o KB (`.claude/kb/<tech>/`), depois documentação oficial. Versões fixadas neste repo: Airflow 3.3.1, DuckDB 1.5.5, dbt-core 1.12 / dbt-duckdb 1.11, CrewAI 1.15, MCP 1.28.
- **R3 · Mão única.** O Sentinel (B) lê o backbone (A) somente leitura pelas interfaces I1–I5. A nunca importa `sentinel`. As únicas escritas de B: `ops.diagnoses` e `/data/sentinel/`.
- **R4 · Respeitar decisões.** D-1 (histórico 12 meses), D-2 (contatos mantidos — risco aceito), D-3 (Sentinel/MCP fase 2), U2 (a carga é dona do raw), U3 (defeito visível no silver). Não reabrir em silêncio: registrar em ADR.
- **R5 · Verificar pelo tipo.** A por asserção ligada a um AC do brief (AC-1..AC-8). B por nota contra `origin='chaos'` (F2-1). Nunca declarar B "correto".
- **R6 · Mapa falha → detecção é vinculante.** Toda falha em `chaos/failures.py` tem detector e superfície; o e2e cobre todas.
- **R7 · Chaos reversível.** Todo ciclo injetar → detectar → pontuar parte de amostra limpa (`chaos.cli reset`).
- **R8 · Segredos e SQL.** Nada de segredo no código; SQL parametrizado; identificadores só de constantes internas (`layout.py`).
- **R9 · Um escritor.** Toda escrita no DuckDB passa por `connect_rw` e, no Airflow, pelo pool `duckdb_writer`.
- **R10 · Tasks antes de código.** Mudança não trivial nasce como `tasks/T-*.md` (task-spec) com evals bash; `validate-task-spec.sh` antes de executar; o Exit Check é a prova de pronto.
- **R11 · Closers antes de concluir.** reviewer → simplifier → fix → documenter; achado sem destino bloqueia.
