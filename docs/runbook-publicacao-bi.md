# Runbook: publicação gold para o BI

Operação da DAG diária `publicar_gold_bi` (Airflow 3) e corte do publicador antigo. Sem segredos neste texto: credenciais ficam só no `.env`.

## 1. Rodar

1. Confirme que a DAG foi carregada, sem erros de importação:
   `airflow dags list-import-errors` (a saída deve estar vazia).
2. Na UI do Airflow, despause `publicar_gold_bi` e dispare uma execução manual (Trigger).
3. Acompanhe as tarefas até `success`. A publicação usa tabela `__novo` + troca DROP/RENAME, então o BI continua lendo a tabela antiga até a troca.
4. Confira que o papel `bi_reader` consegue SELECT nas tabelas publicadas de `gold`.

## 2. Reprocessar

Para reprocessar um dia ou uma publicação que falhou:

1. Rode `airflow dags list-import-errors` para garantir que a DAG está íntegra.
2. Na UI, limpe (Clear) a execução com falha, ou dispare nova execução manual com a data lógica desejada.
3. A publicação é idempotente: reprocessar substitui a tabela inteira, sem duplicar linhas.
4. Se sobrou tabela `__novo` no schema `gold` de uma falha anterior, o próximo run a remove; confirme depois do run.

Quando todos os retries falham por lock (R2 / KO-004): não force a troca. Identifique quem segura o lock (ver seção 3), espere ou encerre essa sessão, e então reprocessar com Clear na tarefa. A tabela antiga permanece intacta e legível enquanto isso.

## 3. Diagnosticar

### Lock no Postgres
- Sintoma: tarefa falha após retries esperando lock na tabela de `gold`.
- Veja as sessões em `pg_stat_activity` e `pg_locks` para a tabela alvo. Sessões longas de BI ou do publicador antigo são as suspeitas usuais.
- Resolva liberando a sessão (de preferência esperando terminar) e reprocessar.

### PII / allowlist / k = 5
- A publicação aborta, sem escrever no Postgres, se uma coluna estiver fora da allowlist ou se alguma célula tiver contagem menor que k = 5.
- Leia o log da tarefa para ver a tabela e a coluna/célula que reprovou. Corrija a origem no DuckDB (agregação ou coluna); não relaxe a allowlist nem o k para passar.

### DuckDB ocupado
- Sintoma: erro de arquivo travado/em uso ao abrir o DuckDB.
- DuckDB aceita um único escritor. Verifique se outra DAG ou sessão manual mantém o arquivo aberto; aguarde ou encerre e reprocessar.

### Ambiente (Linux)
- `env_file`: confirme que o contêiner leu o `.env` esperado (variáveis `PUBLISH_*`).
- Donos de bind mounts: o usuário do contêiner precisa ler/escrever nos diretórios montados.
- Espaço: `df -h` (bytes) e `df -i` (inodes); disco ou inodes cheios derrubam COPY e DuckDB.

## 4. Corte do publicador antigo

Faça nesta ordem, sem pular passos:

1. **Parar a DAG antiga** (pausar e aguardar execuções em andamento terminarem).
2. **Definir no `.env`: `PUBLISH_TABLES=gold_resumo_competencia`.** Não use `PUBLISH_ENABLED=false` para o corte: isso desliga a publicação em vez de restringir as tabelas.
3. **Transferir o dono das tabelas trocadas** com `sql/003_cutover_dono.sql` (executado manualmente por quem administra o Postgres), para que a troca DROP/RENAME e o GRANT do `bi_reader` funcionem.
4. **Ligar a DAG nova** `publicar_gold_bi` e disparar uma execução; valide o SELECT do `bi_reader`.

### Aviso: caminho antigo

O caminho antigo **não tem allowlist nem k = 5**. Não o religue depois do corte, e não o use para republicar tabelas com dados de pessoas. O histórico existente não é apagado pelo corte.

### Rollback do corte
Pause a DAG nova e consulte o responsável antes de religiar a antiga, lembrando o aviso acima.
