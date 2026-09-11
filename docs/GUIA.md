# Guia passo a passo — Plataforma DataOps do CNPJ

Este guia leva do zero até a plataforma processando **a última competência publicada** pela Receita (sem carga retroativa). O v1 é o backbone. O Sentinel (agentes) e o MCP são **fase 2**: ficam no profile `fase2` do compose (ADR-0003). Ele também registra **como o sistema foi construído** seguindo o método Converge (seção 10), para você reproduzir ou estender.

> Convenção: os comandos `.\cnpj.ps1 ...` rodam no **PowerShell**, na pasta do projeto. No Linux/WSL, use `make ...` (mesmos nomes).
>
> Se o PowerShell bloquear o script, libere scripts locais uma vez: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

---

## 1. Pré-requisitos

| Item | Mínimo | Recomendado |
|---|---|---|
| Windows | 10 22H2 / 11 com **WSL2** | Windows 11 |
| Docker Desktop | Backend WSL2 | Última versão |
| RAM entregue ao Docker | 12 GB | 24 GB+ |
| CPU entregue ao Docker | 4 | 8 |
| Disco livre (SSD) | 150 GB | 300 GB |
| Chave OpenAI | Opcional (sem ela o Sentinel usa o fluxo determinístico) | — |

**Memória do WSL2.** Por padrão o WSL usa só metade da RAM. Crie `%UserProfile%\.wslconfig`:

```ini
[wsl2]
memory=24GB
processors=8
swap=8GB
```

Depois rode `wsl --shutdown` e reabra o Docker Desktop.

**Rede (só no build e no download):** Docker Hub, PyPI, `raw.githubusercontent.com` (constraints do Airflow) e `arquivos.receitafederal.gov.br`. Atrás de proxy corporativo, configure o proxy no Docker Desktop (*Settings → Resources → Proxies*) e `HTTPS_PROXY` no `.env`.

> **Licença:** o Docker Desktop é gratuito para uso pessoal. Se o projeto for para uma empresa grande, use Docker Engine em Linux, Rancher Desktop ou Podman (o `docker-compose.yml` é o mesmo).

---

## 2. Obter o projeto

Copie a pasta `receita-cnpj-dataops` para um disco com espaço (ex.: `D:\projetos\receita-cnpj-dataops`) e, se quiser versionar:

```powershell
cd D:\projetos\receita-cnpj-dataops
git init; git add .; git commit -m "Plataforma DataOps do CNPJ"
```

O `.gitignore` já exclui o `.env` e os dados.

---

## 3. Configurar o `.env`

```powershell
copy .env.example .env
notepad .env
```

| Variável | O que ajustar |
|---|---|
| `POSTGRES_ADMIN_PASSWORD`, `PG_PASSWORD`, `AIRFLOW_DB_PASSWORD`, `AIRFLOW_ADMIN_PASSWORD` | Senhas próprias |
| `AIRFLOW_JWT_SECRET` | Um GUID longo: `[guid]::NewGuid().ToString("N")` |
| `OPENAI_API_KEY` | Sua chave (o Sentinel usa `gpt-5.6-luna` nos especialistas e `gpt-5.6-terra` no gerente) |
| `DUCKDB_MEMORY_LIMIT` | ~50% da RAM do Docker (ex.: `12GB` com 24 GB) |
| `DUCKDB_THREADS` | Número de CPUs do Docker |
| `CNPJ_DATA` | Deixe `cnpj_data` (volume rápido) ou um caminho como `D:/cnpj-data` para ver os arquivos no Explorer (mais lento) |
| `OFFLINE_MODE` | `true` só no teste de fumaça (seção 5) |
| `PUBLISH_TABLES` | Tabelas gold copiadas para o Postgres. Acrescente `gold_empresa_detalhe` se o Power BI precisar da ficha completa (tabela grande) |

---

## 4. Subir a plataforma

```powershell
.\cnpj.ps1 up
docker compose ps
```

O primeiro build leva de 5 a 15 minutos. Containers esperados:

| Serviço | Papel |
|---|---|
| `postgres` | Metadado do Airflow + banco `cnpj` (ledger `ops` e gold publicado). Porta **5433** no Windows |
| `airflow-init` / `airflow-setup` | Executam uma vez: migração, usuário admin, pool `duckdb_writer`, schema `ops` |
| `airflow-apiserver` | Interface em **http://localhost:8080** |
| `airflow-scheduler` | Executa as tarefas (LocalExecutor) |
| `airflow-dag-processor` | Lê a pasta `dags/` |
| `sentinel` *(fase 2)* | Gatilho do Sentinel (verifica `ops.incidents` a cada 60 s). Só sobe com `.\cnpj.ps1 fase2` |
| `mcp` *(fase 2)* | Servidor MCP em **http://localhost:8000/mcp**. Só sobe com `.\cnpj.ps1 fase2` |

Todas as portas ficam presas a `127.0.0.1` (Airflow, Postgres, MCP): nada fica exposto na rede.

Entre no Airflow com `AIRFLOW_ADMIN_USER` / `AIRFLOW_ADMIN_PASSWORD`. A DAG **`receita_cnpj_mensal`** aparece pausada.

---

## 5. Teste de fumaça (sem internet, ~5 minutos)

Valida tudo com uma amostra sintética no formato exato da Receita.

1. Coloque `OFFLINE_MODE=true` no `.env` e rode `docker compose up -d` para aplicar. Os comandos `amostra`, `injetar` e `falhas` usam a imagem da fase 2, que é construída na primeira chamada.
2. Gere uma competência "anterior" e processe:
   ```powershell
   .\cnpj.ps1 amostra 2026-07
   .\cnpj.ps1 rodar 2026-07
   ```
   No Airflow as 11 tarefas devem ficar verdes. `.\cnpj.ps1 status` mostra `2026-07 | publicada` e **nenhum incidente**: os defeitos conhecidos da fonte, como motivo 32 e UF EX, não viram incidente.
3. Gere o mês seguinte com uma falha em cascata e processe:
   ```powershell
   .\cnpj.ps1 amostra 2026-08
   .\cnpj.ps1 injetar multi_failure_cascade 2026-08
   .\cnpj.ps1 rodar 2026-08
   ```
   Os monitores abrem 3 incidentes (`invalid_cnpj`, `orphan_socio`, `volume_drop`). Se a fase 2 estiver ativa (`.\cnpj.ps1 fase2`), o Sentinel diagnostica em até 1 minuto **depois que a DAG termina** e dá a nota.
4. Confira:
   ```powershell
   .\cnpj.ps1 status   # ops.diagnoses: multi_failure_cascade, score_tier=cascade, match_score=1
   .\cnpj.ps1 evals              # AC-1..AC-8 (AC-7 é provado pela suíte de falhas simuladas)
   .\cnpj.ps1 evals reprocessar  # mede também o AC-6: recarrega a última competência e compara
   ```
5. *(Fase 2)* Teste uma falha isolada com o crew de IA (precisa de `OPENAI_API_KEY` e `.\cnpj.ps1 fase2`):
   ```powershell
   .\cnpj.ps1 amostra 2026-08
   .\cnpj.ps1 injetar orphan_socio 2026-08
   .\cnpj.ps1 rodar 2026-08      # reprocessar a última competência é permitido; meses anteriores não
   .\cnpj.ps1 logs sentinel     # procure a linha [SCORECARD]
   ```
   Os arquivos do crew ficam em `/data/sentinel/proposed` e `/data/sentinel/postmortems`:
   ```powershell
   docker compose --profile fase2 exec sentinel ls /data/sentinel/postmortems
   ```

Lista de falhas: `.\cnpj.ps1 falhas`.

---

## 6. Primeira carga real

1. Limpe o ambiente de teste: `.\cnpj.ps1 limpar-teste` (digite `SIM`).
2. Coloque `OFFLINE_MODE=false` no `.env` e rode `docker compose up -d`.
3. Dispare: `.\cnpj.ps1 rodar`. Sem mês, a DAG descobre a última competência publicada.
4. Acompanhe no Airflow:
   - `baixar`: ~6 GB. O tempo depende da sua rede e do servidor da Receita, que costuma ser lento. Se cair, a tarefa retoma de onde parou.
   - `carregar_raw` e `dbt_*`: dezenas de minutos a poucas horas, conforme CPU, RAM e disco.
5. Depois de concluída: `.\cnpj.ps1 evals`. A primeira execução real é a **linha de base** dos tempos do BRD (AC-2 e AC-3).

**Espaço em disco:**
- os zips ficam em `/data/landing/AAAA-MM` (~6 GB por competência). A tarefa `limpar_landing` mantém automaticamente só as 2 mais recentes (`LANDING_RETENTION`);
- o histórico Parquet fica em `/data/history/competencia=AAAA-MM/`. A tarefa `arquivar_historico` mantém 12 competências (AC-8).

```powershell
docker compose exec airflow-scheduler sh -c "ls /data/landing /data/history; du -sh /data/*"
```

---

## 7. Operação do dia a dia

- **Automático:** com a DAG ativa, ela roda todo dia às 06:00. Só trabalha quando a Receita publica uma competência nova.
- **Reprocessar:** Airflow → *Trigger DAG* → `{"competencia": "2026-08"}`, ou `.\cnpj.ps1 rodar 2026-08`. Só vale para a **última** competência concluída ou uma mais nova. Meses antigos são consultados no histórico:
  ```powershell
  .\cnpj.ps1 diferenca 2026-07 2026-08            # o que mudou entre dois meses
  .\cnpj.ps1 diferenca 2026-07 2026-08 12345678   # só uma empresa (KYC)
  ```
- **Falha de fonte:** servidor da Receita fora do ar vira incidente `source_unavailable`, e competência nova que não aparece em 45 dias vira `stale_release`. Os dois ficam na pseudo-competência `fonte` em `.\cnpj.ps1 status`.
- **Leituras x escrita:** uma consulta aberta nunca derruba a DAG. O escritor espera até `DUCKDB_LOCK_WAIT_S` (padrão 600 s) pelo leitor.
- **Falhou?**
  1. Veja o incidente (`.\cnpj.ps1 status`) e o diagnóstico do Sentinel.
  2. Leia o patch proposto em `/data/sentinel/proposed`. Ele **nunca é aplicado sozinho**.
  3. Corrija e clique em *Clear* na tarefa que falhou.
- **Incidentes típicos:**

| Chave | Significado | Ação usual |
|---|---|---|
| `missing_file` | A Receita publicou a pasta incompleta | Aguardar e reprocessar |
| `corrupt_zip` | Download truncado | Apagar o zip e reprocessar (retoma sozinho) |
| `layout_drift` | A Receita mudou colunas | Atualizar `pipeline/receita/layout.py` e o bronze |
| `volume_drop` | Entrega parcial | Aguardar republicação e reprocessar |
| `invalid_cnpj`, `invalid_date`, ... | Explosão de rejeições | Investigar `silver_*_rejects` |

---

## 8. Consumir os dados

### Power BI → PostgreSQL
Conecte em servidor `localhost:5433`, banco `cnpj`, schema `gold`, com usuário e senha `PG_USER` / `PG_PASSWORD`. Por padrão ficam publicadas:

- `gold_resumo_competencia` (histórico mês a mês);
- `gold_painel_prospeccao` (ativos por UF, município, CNAE, porte e Simples);
- `gold_rede_societaria`.

### MCP no Claude Desktop *(fase 2)*
Suba a fase 2 (`.\cnpj.ps1 fase2`) e, em *Settings → Developer → Edit Config* (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "receita-cnpj": {
      "command": "docker",
      "args": ["compose", "-f", "D:/projetos/receita-cnpj-dataops/docker-compose.yml",
               "--profile", "fase2", "exec", "-T", "mcp", "python", "-m", "intelligence.server"]
    }
  }
}
```

Reinicie o Claude Desktop e pergunte, por exemplo:

- "Me dá a ficha do CNPJ 12.ABC.345/01DE-35."
- "Quem são os sócios da raiz 12345678 e com quais empresas ela se relaciona?"
- "Liste restaurantes ativos no DF abertos nos últimos 6 meses."

As ferramentas disponíveis são `ficha_cnpj`, `quadro_societario`, `rede_societaria`, `prospectar`, `painel_mercado`, `diferenca_competencias`, `resumo_competencia` e `schema_gold`. Todas são somente leitura, com limite de linhas.

### SQL direto no DuckDB
`.\cnpj.ps1 consulta "SELECT uf, count(*) FROM gold.gold_empresa_detalhe GROUP BY 1"`. O comando aceita só tabelas gold, silver e `raw_load_log` (conferidas pelo parser do DuckDB) e abre o banco **sem acesso a arquivos do container**, então nem SQL malicioso consegue ler o `.env`.

> Enquanto a DAG escreve no DuckDB, as leituras esperam alguns segundos e tentam de novo. O DuckDB aceita um único processo escritor por vez.

---

## 9. O Sentinel

- **Quando roda:** o container `sentinel` verifica `ops.incidents` a cada 60 s e só pega competências cuja DAG já terminou.
- **Roteamento:**
  - 1 incidente → **crew hierárquico** (gerente + Log Analyst + Data Profiler + Data Engineer + Incident Commander);
  - 2 ou mais → **fluxo determinístico de cascata**;
  - sem chave da OpenAI → fluxo determinístico;
  - API fora do ar → `no-run` registrado. O Sentinel nunca inventa nota.
- **Custo:** só roda quando há incidente. Os especialistas usam o modelo barato e só o gerente usa o mais forte.
- **O que vai para a OpenAI:** logs, contagens, até 3 CNPJs de exemplo por regra de quarentena e consultas ad hoc de no máximo 20 linhas. Colunas de contato e de sócio (e-mail, telefone, endereço, nome/CPF de sócio) e `SELECT *` são **bloqueados** para o agente. Para zero chamadas externas, use Ollama:
  ```text
  SENTINEL_LLM_PROVIDER=ollama
  SENTINEL_LLM_MODEL=ollama/qwen2.5:14b
  SENTINEL_MANAGER_MODEL=ollama/qwen2.5:14b
  ```
  Suba com `docker compose --profile ollama up -d` e baixe o modelo com `docker compose exec ollama ollama pull qwen2.5:14b`.
- **Nota:** cada caso injetado pelo chaos é pontuado em `ops.diagnoses`:
  - `exact` = 1,0;
  - `cascade` = 0,5 + 0,5 × acerto dos membros;
  - `miss` = 0.

  A nota de **evidência** mostra se o agente citou a superfície certa.

---

## 10. Como o sistema foi construído (e como estender)

### 10.1 Da arquitetura de referência para a Receita

| ws-3 (e-commerce) | Este projeto (Receita) | Por quê |
|---|---|---|
| Postgres transacional como fonte | WebDAV do SERPRO+ (37 zips/mês) | A fonte é arquivo, não banco |
| Dagster | **Airflow 3** (pool `duckdb_writer`) | Decisão do projeto; a vazão vem do DuckDB |
| Ingestão incremental por CDC | Snapshot mensal por competência | A Receita publica fotos mensais completas |
| `injected_incidents` | `ops.incidents` (`origin` chaos/monitor/pipeline) | Um ledger para verdade, monitores e falhas |
| 14 falhas de pedidos | 12 falhas da Receita + cascata | Falhas reais do dado do CNPJ |
| `BACKBONE_RUN_FAILURE` | `PIPELINE_FAILURE key=...` + `DQ_FINDING` | Superfície I1 do Log Analyst |
| gpt-4o / gpt-4o-mini | `gpt-5.6-terra` / `gpt-5.6-luna` | Mesma divisão por tier, modelos atuais |

### 10.2 Ordem de construção (fases do BRD)

1. **Fundação.** `docker-compose.yml`, `.env`, `pipeline/config.py`, `pipeline/ops.py` (ledger).
2. **Ingestão.**
   - `pipeline/receita/layout.py`: fonte única do layout.
   - `webdav.py`: descoberta e download.
   - `loader.py`: raw, layout e encoding.
   - `dags/receita_cnpj.py`.
3. **Medalhão.**
   - `transform/`: macros de data, dinheiro, mojibake e DV do CNPJ; bronze; silver `_classificado` → silver + `_rejects`; gold.
   - `pipeline/quality.py`: monitores.
4. **Consumo.** `pipeline/publish.py` (Postgres) e `intelligence/` (MCP).
5. **Sentinel.**
   - `chaos/`: amostra e falhas.
   - `sentinel/`: ferramentas, crew, fluxo, pontuação e gatilho.
6. **Prova.** `tests/` (67 testes, com e2e por falha e regressões da revisão) e `pipeline/evals.py` (AC medidos).

### 10.2.1 O método Converge (como este repositório foi feito)
| Passo | Artefato |
|---|---|
| BRD | `docs/business-requirements-document.md` / `.pdf` |
| P1 · Intent (sem tecnologia, interrogatório D-1..D-3) | `docs/engineering-brief.pdf` / `.md` |
| P2 · Structure (spec aterrada no código, lacunas G1–G7) | `docs/tech-spec.md`, `docs/converge/p2-structure-grounding.md` |
| P3 · Decomposition (dois planos pela costura A/B) | `sketch/receita-backbone.md`, `sketch/sentinel-engine.md` |
| P4 · Consensus (adversário com outro modelo, 7 objeções) | `docs/converge/p4-consensus.md`, ADR-0003 |
| Tasks (Task-Spec v2.1 com evals bash) | `tasks/T-20260911-*.md` (validar com `.claude/skills/task-spec/scripts/validate-task-spec.sh`) |
| Build com a frota de agentes | `.claude/agents` (airflow/dbt/duckdb/mcp/crewai + closers), `.claude/kb` |
| Closers (reviewer independente → correções → docs) | `docs/converge/closers-review.md` |

### 10.3 Receitas de extensão

- **Nova regra de qualidade:**
  1. Acrescente um `WHEN ... THEN 'nova_regra'` no `silver_*_classificado.sql`.
  2. Inclua o valor em `accepted_values` (`silver/schema.yml`).
  3. Crie a falha correspondente em `chaos/failures.py`, com injetor e superfície.
  4. O teste e2e passa a cobri-la automaticamente.
- **Novo modelo gold:** crie o `.sql` em `transform/models/gold/`. Para publicar no Postgres, acrescente-o a `PUBLISH_TABLES`.
- **Nova pergunta no MCP:** crie a função em `intelligence/intents.py` (SQL estático, parâmetros com `?`, `LIMIT`) e o `@mcp.tool()` em `server.py`.
- **A Receita mudou o layout:**
  1. Ajuste `ENTITIES` em `layout.py` (a carga raw se ajusta sozinha).
  2. Ajuste o bronze.
  3. Rode `uv run pytest`.

---

## 11. Solução de problemas

| Sintoma | Causa provável | Solução |
|---|---|---|
| `descobrir` falha com 403/timeout | Proxy ou firewall | `HTTPS_PROXY` e `RFB_CA_BUNDLE` no `.env`; teste o link do compartilhamento no navegador |
| Tarefas presas em *scheduled* | Pool `duckdb_writer` não existe | `docker compose run --rm airflow-setup` |
| `IOException: Could not set lock` | Dois escritores no DuckDB | Não rode `pipeline.run` manual com a DAG ativa; espere a DAG terminar |
| `Out of Memory` no dbt | `DUCKDB_MEMORY_LIMIT` alto demais para o Docker | Reduza o limite ou aumente o `.wslconfig` |
| Tudo lento com `CNPJ_DATA=D:/...` | Bind mount do Windows | Volte para `CNPJ_DATA=cnpj_data` |
| `layout_drift` numa carga real | A Receita mudou colunas | Seção 10.3 |
| Sentinel sempre `deterministic-flow` | Sem `OPENAI_API_KEY` | Preencha a chave e rode `.\cnpj.ps1 fase2` |
| `rodar AAAA-MM` recusado ("anterior à última") | Reprocessar mês antigo faria o consumo regredir | Use `.\cnpj.ps1 diferenca` sobre o histórico |
| Tarefa falhou com `warehouse_busy` | Outro processo segurou o DuckDB por mais de `DUCKDB_LOCK_WAIT_S` | Feche consultas longas e clique em *Clear* na tarefa |
| Login do Airflow falha | Usuário não criado | `docker compose run --rm airflow-init` |

---

## 12. Referências

- Layout oficial: https://www.gov.br/receitafederal/dados/cnpj-metadados.pdf
- Compartilhamento da Receita (SERPRO+): https://arquivos.receitafederal.gov.br/index.php/s/<RFB_SHARE_TOKEN>
- Arquitetura de referência: https://github.com/owshq-mec/ws-3-crew-ai-multi-agent
- Auditoria de qualidade usada como base: https://github.com/caiopizzol/cnpj-data-pipeline (`docs/data-audit.md`)
- CNPJ alfanumérico (IN RFB nº 2.229/2024): https://agenciagov.ebc.com.br/noticias/202410/receita-federal-anuncia-que-cnpj-tera-letras-e-numeros-a-partir-de-julho-de-2026
