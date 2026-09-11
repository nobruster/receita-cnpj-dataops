# ADR-0002 — Sentinel: crew hierárquico via OpenAI, gatilho por polling, nota contra verdade

- **Status:** aceito (2026-09-11)

## Decisões

1. **LLM: OpenAI API** (decisão do projeto), com tiering herdado da referência: gerente `gpt-5.6-terra`, especialistas `gpt-5.6-luna`. Configurável; `ollama` e `none` suportados sem mudar código.
2. **Soberania:** só o Sentinel sai para a internet; as ferramentas devolvem agregados, logs e no máximo 3 chaves de exemplo por regra. Telemetria do CrewAI desligada.
3. **Gatilho por polling de `ops.incidents`** (não callback do Airflow): a maioria das falhas não derruba a DAG (quarentena), e o gatilho lê o mesmo ledger que o oráculo, mantendo gatilho e nota consistentes. Um caso = incidentes abertos de uma competência cuja DAG terminou.
4. **Roteamento:** 2+ chaves observadas → Flow determinístico de cascata; 1 chave → crew; sem LLM → Flow determinístico; falha do crew → `no-run` (nunca nota inventada).
5. **Verdade de referência escondida:** incidentes `origin='chaos'` nunca aparecem nas ferramentas; só o oráculo os lê.
6. **Pontuação:** exato 1,0 · alias 0,7 · cascata 0,5 + 0,5 × acerto · erro 0; evidência pontuada à parte (pega "chave certa com evidência inventada").
7. **Único caminho de volta ao A é o patch proposto**, gravado para revisão humana; correções destrutivas (`duplicate_key`, `volume_drop`) ligam `human_input`.

## Consequências

- Com chave de API, cada incidente custa algumas chamadas (baixo). Sem chave, a plataforma continua detectando e diagnosticando pelo caminho determinístico.
- A suíte e2e prova a fiação com o caminho determinístico; a qualidade do LLM é medida separadamente (`ops.diagnoses` com rota `crew`).
