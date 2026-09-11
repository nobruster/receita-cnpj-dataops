export const meta = {
  name: 'build-sentinel-fase2',
  description: 'Constrói o Componente B (sketch/sentinel-engine.md) contra o backbone já vivo: crew hierárquico A1-A5, gatilho B1, Flow determinístico de cascata e pontuação contra o oráculo ops.incidents origin=chaos, cobrindo as 13 falhas de chaos/failures.py. Termina com e2e injetar->detectar->pontuar e o gate dos closers (review -> simplify -> fix -> document).',
  phases: [
    { title: 'Design', detail: 'crewai-architect: topologia do crew, rubrica de pontuação, gatilho B1, mapa das 13 falhas' },
    { title: 'Base', detail: 'A1 Manager + A2 Log Analyst + A3 Data Profiler + scoring' },
    { title: 'Resolve', detail: 'A4 Data Engineer (patch proposto, nunca aplicado) + A5 Incident Commander + gatilho B1' },
    { title: 'Verify', detail: 'e2e injetar->detectar->pontuar contra o pipeline real, todas as falhas + cascata' },
    { title: 'Gate', detail: 'review -> simplify -> fix -> document até limpar' },
  ],
}

const REPO = '/opt/airflow/project' // no container; localmente, a raiz do repo

const GROUND = [
  'REPO: ' + REPO + '. venv: .venv/bin/python, .venv/bin/pytest. Sempre exporte PYTHONPATH=<raiz>, DATA_DIR e PG_* (ledger ops). CrewAI 1.15.21.',
  '',
  'CRÍTICO — DuckDB tem UM ESCRITOR. Toda escrita passa por pipeline.warehouse.connect_rw (espera a trava até DUCKDB_LOCK_WAIT_S) e, no Airflow, pelo pool duckdb_writer. Leitores abrem read-only por chamada via intelligence.sql_guard.open_ro. Não rode a DAG e um build do Sentinel ao mesmo tempo no mesmo DATA_DIR.',
  '',
  'R5 — O COMPONENTE B É PROBABILÍSTICO: verifique por NOTA contra a verdade de referência (a chave diagnosticada bate com ops.incidents origin=\'chaos\'?), nunca afirmando que a saída está "correta". O oráculo é o ledger ops.',
  'R3 — MÃO ÚNICA: B lê A somente leitura pelas interfaces I1-I5. A nunca importa sentinel. As únicas escritas de B são ops.diagnoses e /data/sentinel/{proposed,postmortems}. B NÃO escreve em ops.incidents.',
  'VERDADE ESCONDIDA: nenhuma ferramenta do Sentinel pode ler origin=\'chaos\'.',
  'LGPD: o que vai ao LLM passa por query_warehouse — 20 linhas e views sem colunas pessoais (warehouse.connect_ro_masked). Não afrouxe isso.',
  '',
  'O QUE JÁ EXISTE em sentinel/ (estenda, não reescreva): crew.py (SentinelCrew, CrewBase, HUMAN_GATED_FAILURES), flow.py (SentinelFlow, cascata), scoring.py (exato 1.0 / alias 0.7 / cascata 0.5+0.5*overlap / miss 0 / no-run), trigger.py (polling, ops.UNDIAGNOSED), tools/ (readers, writers, history), config/agents.yaml e tasks.yaml em português, knowledge/runbook.md.',
  '',
  'INTERFACES QUE B CONSOME (sketch/sentinel-engine.md I1-I5): I1 /data/logs/pipeline.log, I2 /data/dbt/target/run_results.json, I3 DuckDB silver_*_rejects + flags + gold (read-only), I4 ops.dq_metrics + ops.incidents (sem chaos), I5 post-mortems + ops.diagnoses.',
  '',
  'PROVA: uv run pytest -q tests/test_e2e.py tests/sentinel -q com PG_* apontando para um Postgres de teste; a nota média (F2-1) precisa ficar >= 0.8 no relatório de pipeline.evals.',
].join('\n')

const DIMENSOES = [
  { key: 'crew', prompt: GROUND + '\n\nTarefa: revise e complete o crew hierárquico A1-A5 (agents.yaml/tasks.yaml + crew.py), garantindo guardrail com output_pydantic, human_input nas falhas destrutivas e knowledge/RAG no runbook para orphan_domain.' },
  { key: 'flow', prompt: GROUND + '\n\nTarefa: revise o Flow determinístico (cascata e caminho sem LLM) e o gatilho B1 (pending_cases, UNDIAGNOSED, atualizado_em >= max(detected_at)).' },
  { key: 'scoring', prompt: GROUND + '\n\nTarefa: revise a rubrica de pontuação e a camada de evidência; garanta que "no-run" nunca vira nota inventada.' },
]

const results = await pipeline(
  DIMENSOES,
  d => agent(d.prompt, { label: `build:${d.key}`, phase: 'Base' }),
  saida => parallel([
    () => agent(GROUND + '\n\nVerifique com e2e real: injete cada falha de chaos/failures.py, rode o pipeline e pontue. Reporte falhas não detectadas.\n\nContexto: ' + saida, { label: 'verify', phase: 'Verify' }),
  ]),
)

await agent(GROUND + '\n\nGate dos closers (R11): code-reviewer -> code-simplifier -> corrigir -> code-documenter. Achado sem destino bloqueia. Atualize docs/converge/closers-review.md.', { label: 'gate', phase: 'Gate' })

return { results }
