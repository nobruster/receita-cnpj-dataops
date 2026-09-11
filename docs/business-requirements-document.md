---
title: "Business Requirements Document: Plataforma DataOps do CNPJ"
subtitle: "Processamento on-premises de todos os arquivos abertos do CNPJ da Receita Federal, com monitoramento autônomo por agentes"
author: "Bruno Nunes — Engenharia de Dados"
date: "2026-09-11"
document_type: "BRD — Projeto de portfólio"
classification: "Público"
version: "1.0"
---

# Business Requirements Document: Plataforma DataOps do CNPJ

## Capa

**PLATAFORMA DATAOPS DOS DADOS ABERTOS DO CNPJ**

Processar 100% dos arquivos mensais do CNPJ publicados pela Receita Federal, em infraestrutura própria (Docker), transformar em dados confiáveis para **crédito e risco**, **KYC/PLD** e **prospecção comercial**, com um time de agentes de IA que vigia a qualidade e diagnostica falhas.

- **Preparado por:** Bruno Nunes (engenharia de dados)
- **Tipo:** projeto pessoal / portfólio técnico
- **Data:** 11 de setembro de 2026
- **Status:** para revisão
- **Recomendação:** executar em fases, começando pela ingestão e pelo medalhão (Fases 0–2)
- **Arquitetura de referência:** [owshq-mec/ws-3-crew-ai-multi-agent](https://github.com/owshq-mec/ws-3-crew-ai-multi-agent), adaptada para arquivos, Airflow e DuckDB

## Sumário

1. Sumário executivo
2. Situação atual
3. Problema e impacto no negócio
4. Solução proposta e capacidades
5. Análise de custo e esforço
6. Alternativas consideradas
7. Riscos e mitigação
8. Métricas de sucesso e governança
9. Roadmap de implementação
10. Partes interessadas e personas
11. Registro de premissas e restrições
12. Apêndice: arquitetura-alvo
13. Conclusão

---

## 1. Sumário executivo

### 1.1 Situação

A Receita Federal publica todo mês a base aberta do CNPJ: empresas, estabelecimentos, sócios, opção pelo Simples/MEI e seis tabelas de domínio. Hoje a publicação fica no repositório **SERPRO+** (Nextcloud), num compartilhamento público com **40 pastas mensais, de 2023-05 em diante, somando 311,7 GB**. Cada competência tem **37 arquivos zip e cerca de 6 GB compactados**. Descompactados, os CSVs passam de 80 GB.

É o dado público mais usado no Brasil para conhecer uma empresa: se está ativa, desde quando, o que faz, onde está, qual o porte e quem são os sócios. Três mudanças recentes aumentam o risco de quem consome esse dado:

- **Mudança de endereço.** O diretório antigo `dados/cnpj/dados_abertos_cnpj/` hoje responde "Page not found". Os arquivos migraram para um compartilhamento Nextcloud, acessível por WebDAV.
- **CNPJ alfanumérico.** Desde julho de 2026 (IN RFB nº 2.229/2024), novos CNPJs podem ter letras na raiz e na ordem. O dígito verificador continua numérico.
- **Inconsistências da própria fonte.** A Receita publica códigos que não existem nos domínios do mesmo mês, CEPs sem o zero à esquerda e valores-sentinela (detalhes na seção 2.3).

### 1.2 Problema

Consumir esse dado de forma confiável exige resolver ao mesmo tempo:

- **Volume:** dezenas de milhões de linhas por mês. Uma carga ingênua em banco transacional leva horas e compete com outros usos.
- **Fragilidade:** download lento e instável, mudanças de layout e de endereço, encoding ISO-8859-1.
- **Qualidade invisível:** sem regras explícitas, um CNPJ inválido, uma data impossível ou um sócio sem empresa entram calados nas análises de crédito e de compliance.
- **Operação manual:** descobrir que saiu competência nova, baixar, carregar, validar e comparar com o mês anterior depende de alguém lembrar de fazer.

### 1.3 Solução proposta

Uma plataforma **on-premises, 100% em Docker**, em duas partes, seguindo a separação da arquitetura de referência:

- **Componente A — backbone analítico (determinístico).**
  - **Airflow** detecta e baixa a última competência publicada.
  - **DuckDB** processa todo o volume.
  - **dbt** organiza o medalhão bronze → silver (com quarentena de rejeitados) → gold.
  - **PostgreSQL** guarda o controle operacional e publica as tabelas de consumo.
  - Um servidor **MCP** responde a perguntas em linguagem natural sobre o gold.
- **Componente B — Sentinel (probabilístico).** Um time **CrewAI** de cinco agentes lê os logs e as tabelas de quarentena, diagnostica incidentes, propõe correções que só são aplicadas com aprovação humana e escreve o post-mortem. O LLM é a API da OpenAI (configurável; Ollama local como alternativa). O Sentinel envia só metadados, contagens e trechos de log, nunca a base em massa.

### 1.4 Resumo do caso

| Dimensão | Hoje (processo manual/scripts) | Com a plataforma |
|---|---|---|
| Descoberta de nova competência | Manual | Automática (verificação diária) |
| Download | Script, reinício manual em falha | Retomada por `Range`, integridade de zip validada |
| Qualidade | Implícita | 100% das linhas classificadas; rejeitadas em quarentena com motivo |
| Histórico mês a mês | Inexistente | Métricas por competência no ledger `ops` |
| CNPJ alfanumérico | Não tratado | Validação de formato e DV (módulo 11 com letras) |
| Diagnóstico de falhas | Humano, reativo | Sentinel diagnostica e pontua contra verdade de referência |
| Custo | — | Licenças R$ 0 (stack open-source); só a API da OpenAI do Sentinel é paga por uso |

### 1.5 Recomendação

Executar em fases. As Fases 0–2 (fundação, ingestão e medalhão) entregam valor sozinhas: a base completa e confiável para crédito, KYC e prospecção. O Sentinel e o MCP (Fases 3–4) só entram quando a fundação estiver provada pelos critérios de aceite da seção 8, a mesma disciplina do projeto de referência ("avaliar depois que a fundação estiver provada").

---

## 2. Situação atual

### 2.1 A fonte

| Item | Valor | Evidência |
|---|---|---|
| Publicador | Receita Federal / SERPRO+ | Compartilhamento `arquivos.receitafederal.gov.br/index.php/s/<RFB_SHARE_TOKEN>` |
| Acesso técnico | WebDAV público (`/public.php/webdav`), usuário = token | Mesmo compartilhamento |
| Periodicidade | Mensal (uma pasta `AAAA-MM` por competência) | 40 pastas, de 2023-05 em diante |
| Tamanho por competência | ~5,6 a 6 GB zipados | Listagem do compartilhamento |
| Arquivos por competência | 37 (Empresas0–9, Estabelecimentos0–9, Socios0–9, Simples e 6 domínios) | Layout oficial |
| Formato | CSV sem cabeçalho, `;`, aspas `"`, ISO-8859-1 | [cnpj-metadados.pdf](https://www.gov.br/receitafederal/dados/cnpj-metadados.pdf) |
| Mascaramento | CPF de sócio com 3 primeiros e 2 últimos dígitos ocultos | Layout oficial |

### 2.2 Volumes de referência

Medições publicadas por um pipeline open-source sobre a entrega de 2026-04 ([caiopizzol/cnpj-data-pipeline](https://github.com/caiopizzol/cnpj-data-pipeline), `docs/data-audit.md`):

- **Empresas:** cerca de 67 milhões (≈50 mi microempresas, ≈15 mi "demais", ≈2 mi EPP).
- **Sócios:** cerca de 27,5 milhões. Em 97% das linhas não há representante legal.
- **Estabelecimentos:** dezenas de milhões. O número exato é medido na primeira carga (métrica `linhas` em `ops.dq_metrics`).

### 2.3 Problemas de qualidade conhecidos na fonte

Medições da mesma auditoria (entrega 2026-04). Todos são tratados como **fatos da fonte a preservar e sinalizar**, não como erros de carga:

| Caso | Ocorrência | Tratamento na plataforma |
|---|---|---|
| Motivo de situação `32` ausente do `Motivos.csv` | 18.672 estabelecimentos | Flag `_orphan_motivo` + métrica monitorada |
| País órfão (14 códigos) | 1.220 estabelecimentos | Flag `_orphan_pais` |
| UF `EX` (exterior, não documentada) | 170.865 estabelecimentos | Aceita como domínio válido |
| Capital social `999999999999` (sentinela) | 124 empresas | Flag `_capital_sentinela` |
| CEP com 7 dígitos (zero perdido) | ~0,1% das linhas | Padronização para 8 dígitos no bronze |
| Representante legal `***000000**` | 97% dos sócios | Convertido para nulo ("sem representante") |

### 2.4 Processo atual (linha de base)

- O download é feito por script Python próprio (`baixa_cnpj_rf.py`), com retomada e downloads paralelos, apontando para o endereço antigo.
- A carga no PostgreSQL via `COPY` estava planejada, sem medalhão nem regras de qualidade.
- Não há controle de quais competências foram processadas, nem comparação mês a mês.
- Os tempos atuais de ponta a ponta não foram medidos. Por isso as metas da seção 8 usam o hardware de referência, e a primeira execução estabelece a linha de base.

---

## 3. Problema e impacto no negócio

### 3.1 Problema central

Os três usos-alvo dependem de a informação da empresa estar **completa, atual e correta**. Quando um desses três falha, a decisão também falha, e em silêncio.

### 3.2 Impacto 1 — Crédito e risco

- **Sintoma:** uma empresa baixada, inapta ou aberta há poucos meses aparece como apta porque a base está desatualizada ou incompleta.
- **Impacto:** concessão para CNPJ irregular e erro na régua de risco (idade da empresa, porte e capital social são variáveis clássicas de score).
- **Requisitos:**
  - **BR-001:** processar a última competência publicada em até **24 h após a detecção**.
  - **BR-002:** expor, por CNPJ, situação cadastral, data de início, porte, capital, natureza jurídica, Simples/MEI e quantidade de estabelecimentos e de sócios.

### 3.3 Impacto 2 — KYC / PLD

- **Sintoma:** o quadro societário e as relações entre empresas (sócio pessoa jurídica) ficam espalhados em 10 arquivos de sócios sem ligação direta com as empresas.
- **Impacto:** a verificação de beneficiário final e de grupo econômico vira trabalho manual, e o risco de não detectar empresas interligadas cresce.
- **Requisitos:**
  - **BR-003:** entregar o **quadro societário completo** por CNPJ e a **rede societária PJ→PJ**, ligando empresas que são sócias de outras empresas.
  - **BR-004:** manter **rastreabilidade** de cada linha até o arquivo e a competência de origem (trilha de auditoria).

### 3.4 Impacto 3 — Prospecção comercial

- **Sintoma:** listas por setor (CNAE principal e secundário), município, porte e aberturas recentes exigem joins pesados a cada consulta.
- **Impacto:** listas lentas e desatualizadas, com empresas já baixadas no meio.
- **Requisitos:**
  - **BR-005:** consultas de prospecção por **CNAE, UF/município, porte, Simples/MEI e data de abertura** com **p95 ≤ 5 s** sobre as tabelas gold agregadas.
  - **BR-006:** consulta em **linguagem natural** (MCP) restrita a intenções curadas e somente leitura.

### 3.5 Impacto 4 — Operação e confiabilidade

- **Sintoma:** mudança de endereço, arquivo faltando, zip corrompido ou mudança de layout só são percebidos quando alguém nota o número estranho no relatório.
- **Impacto:** retrabalho e decisões tomadas sobre dados quebrados.
- **Requisitos:**
  - **BR-007:** detectar automaticamente e registrar como incidente arquivo ausente, zip corrompido, mudança de layout, queda de volume em relação ao mês anterior e aumento de rejeições.
  - **BR-008:** diagnóstico assistido por agentes, com correções **sempre sujeitas a aprovação humana** e desempenho do agente **pontuado** contra casos de verdade conhecida.
  - **BR-009:** processar os dados **100% on-premises**. Só o Sentinel faz chamadas externas (API da OpenAI), enviando **apenas metadados, contagens e trechos de log** (nunca linhas em massa), e nenhum segredo (inclusive `OPENAI_API_KEY`) fica no código.
  - **BR-010:** suportar o **CNPJ alfanumérico** em todas as camadas.

---

## 4. Solução proposta e capacidades

### 4.1 Visão por componente

| Código | Componente | Tecnologia | Responsabilidade |
|---|---|---|---|
| C1 | Fonte | SERPRO+ (WebDAV) | 37 arquivos por competência |
| C2 | Ingestão | Airflow 3 + Python | Descobrir a última competência, baixar com retomada, validar zips e carregar o raw no DuckDB |
| C3 | Transformação | dbt-duckdb | Bronze (tipagem) → silver (regras e quarentena `*_rejects`) → gold |
| C4 | Warehouse | DuckDB | Motor colunar de todo o volume, com um único processo escrevendo |
| C5 | Inteligência | FastAPI + MCP | Intenções curadas e somente leitura sobre o gold |
| C6 | Consumo SQL/BI | PostgreSQL | Publicação opcional das tabelas gold para Power BI e SQL |
| C7 | Qualidade | Monitores determinísticos | Volume mês a mês, taxa de rejeição, órfãos e frescor, gerando incidentes |
| B | Sentinel | CrewAI + OpenAI API | Diagnóstico, patch proposto (sob aprovação humana), post-mortem e pontuação |

### 4.2 Requisitos funcionais

| ID | Requisito | Atende |
|---|---|---|
| RF-01 | Descobrir a competência mais recente no WebDAV e pular as já concluídas | BR-001 |
| RF-02 | Aceitar reprocessamento forçado de uma competência específica (parâmetro da DAG) | BR-001 |
| RF-03 | Baixar os 37 arquivos com retomada, tentativas com espera crescente e validação de tamanho e CRC | BR-001, BR-007 |
| RF-04 | Carregar o raw fiel à fonte (tudo texto), com `_arquivo`, `_competencia` e `_carregado_em` | BR-004 |
| RF-05 | Detectar mudança de layout antes da carga (contagem de campos) | BR-007 |
| RF-06 | Classificar 100% das linhas no silver; rejeitadas vão para `*_rejects` com `reject_rule` | BR-007 |
| RF-07 | Validar CNPJ numérico e alfanumérico (formato e DV) | BR-010 |
| RF-08 | Gold: ficha completa por estabelecimento, sócios, CNAE secundário, rede societária, painel de prospecção e resumo da competência | BR-002, 003, 005 |
| RF-09 | Registrar métricas por competência e abrir incidentes quando um limiar é violado | BR-007 |
| RF-10 | Sentinel: diagnóstico tipado, patch proposto (nunca aplicado sozinho) e post-mortem | BR-008 |
| RF-11 | Injetor de falhas para validar o Sentinel com verdade de referência | BR-008 |
| RF-12 | MCP com intenções: ficha do CNPJ, quadro societário, rede societária, prospecção e resumo | BR-006 |

### 4.3 Requisitos não funcionais

| ID | Requisito | Meta |
|---|---|---|
| RNF-01 | On-premises | Docker Desktop (WSL2) ou Docker Engine em Linux; dados nunca saem da máquina, só o Sentinel chama a API da OpenAI |
| RNF-02 | Idempotência | Reprocessar a mesma competência produz as mesmas contagens |
| RNF-03 | Um único escritor no DuckDB | Pool `duckdb_writer` com 1 vaga no Airflow |
| RNF-04 | Segurança | Segredos só em `.env`; SQL parametrizado; MCP e Sentinel somente leitura |
| RNF-05 | Observabilidade | Logs com linha de contrato `PIPELINE_FAILURE key=...`; métricas em `ops` |
| RNF-06 | Portabilidade da fonte | URL e token da Receita configuráveis por variável de ambiente |
| RNF-07 | LGPD | Dados já mascarados pela Receita; nenhum desmascaramento; uso restrito às finalidades declaradas |

---

## 5. Análise de custo e esforço

Como é projeto de portfólio, a análise é de **custo total para operar** e **esforço para construir**, não de ROI corporativo.

### 5.1 Licenças

| Item | Licença | Custo |
|---|---|---|
| Apache Airflow | Apache 2.0 | R$ 0 |
| DuckDB | MIT | R$ 0 |
| dbt-core / dbt-duckdb | Apache 2.0 | R$ 0 |
| PostgreSQL | PostgreSQL License | R$ 0 |
| CrewAI | MIT | R$ 0 |
| OpenAI API (Sentinel) | Pago por uso | Baixo: gerente `gpt-5.6-terra` (US$ 2 / US$ 12 por 1M tokens de entrada/saída) e especialistas `gpt-5.6-luna` (US$ 0,20 / US$ 1,20). Só roda quando há incidente |
| Ollama (alternativa local) | MIT / licença do modelo | R$ 0 |
| Docker Desktop | Gratuito para uso pessoal | R$ 0 (ver risco R-08 para uso corporativo) |

### 5.2 Infraestrutura de referência (estimativa a validar na Fase 1)

| Recurso | Mínimo | Recomendado | Justificativa |
|---|---|---|---|
| CPU | 4 vCPU | 8 vCPU | DuckDB paraleliza por núcleo |
| RAM | 16 GB | 32 GB | DuckDB com `memory_limit` de 8–16 GB; +9 GB só se usar Ollama local |
| Disco SSD | 150 GB livres | 300 GB livres | Zips (~6 GB/mês), CSV temporário, warehouse, área de spill, PostgreSQL e modelos |
| Rede | Estável | — | ~6 GB por competência; o download retoma de onde parou |

### 5.3 Esforço de construção (1 pessoa, meio período)

| Fase | Escopo | Estimativa |
|---|---|---|
| 0 | Fundação: Docker, Postgres, Airflow, estrutura do repositório | 1 semana |
| 1 | Ingestão: WebDAV, download, raw, controle de competências | 1–2 semanas |
| 2 | Medalhão dbt, regras de qualidade, monitores | 2 semanas |
| 3 | Consumo: publicação no Postgres, MCP, painel | 1–2 semanas |
| 4 | Sentinel: crew, injetor de falhas, pontuação | 2 semanas |
| 5 | Endurecimento: testes de volume real, documentação e demo | 1 semana |
| **Total** | | **8–10 semanas** |

### 5.4 Benefício esperado

- **Operação:** a competência mensal passa a ser processada sem intervenção. O trabalho manual se resume a aprovar patches propostos pelo Sentinel e ler os post-mortems.
- **Portfólio:** demonstra ponta a ponta as competências mais pedidas em vagas de engenharia de dados e IA (orquestração, modelagem medalhão, qualidade de dados, MCP e sistemas multiagente avaliados contra verdade de referência).
- **Reuso:** a base gold atende os três casos de uso com o mesmo pipeline.

---

## 6. Alternativas consideradas

| Critério | A. Manter scripts + `COPY` no Postgres | B. Arquitetura de referência original (Dagster) | C. APIs comerciais de CNPJ | **D. Proposta: Airflow + DuckDB + dbt** |
|---|---|---|---|---|
| Processa 100% da base | Sim, lento | Sim | Não (consulta por CNPJ) | **Sim** |
| Desempenho no volume | Baixo (engine OLTP) | Alto (DuckDB) | N/A | **Alto (DuckDB)** |
| Qualidade explícita | Não | Sim | Caixa-preta | **Sim (quarentena)** |
| Custo recorrente | Baixo | Baixo | Por consulta | **Baixo** |
| Dependência de terceiros | Nenhuma | Nenhuma | Alta | **Nenhuma** |
| Aderência ao mercado/stack do autor | Média | Média (Dagster menos difundido) | — | **Alta (Airflow é padrão de mercado)** |
| Recomendação | ❌ Não resolve qualidade nem operação | ⚠️ Viável; troca de orquestrador por decisão do projeto | ❌ Não atende rede societária nem análise em massa | ✅ **Seguir** |

**Nota sobre a escolha do orquestrador.** A vazão no volume vem do **DuckDB** (motor colunar, vetorizado e com spill em disco), não do orquestrador. O Airflow foi escolhido por maturidade, adoção de mercado e controle de concorrência por *pools*, que resolve a regra de um único escritor do DuckDB.

---

## 7. Riscos e mitigação

### 7.1 Riscos técnicos

| ID | Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|---|
| R-01 | A Receita muda de novo o endereço ou o token | Média | Alto | URL e token no `.env`; incidente `missing_file`/falha de listagem; runbook |
| R-02 | Mudança de layout (coluna nova ou removida) | Baixa | Alto | Checagem de campos antes da carga (`layout_drift`); layout centralizado em um módulo |
| R-03 | Download instável ou lento | Alta | Médio | Retomada por `Range`, espera crescente, detecção de download travado e validação de CRC |
| R-04 | Falta de memória ou disco no processamento | Média | Alto | `memory_limit` e `temp_directory` do DuckDB; processamento arquivo a arquivo; CSV temporário apagado após carga |
| R-05 | Dois processos escrevendo no DuckDB | Média | Médio | Pool de 1 vaga; DAG com `max_active_runs=1`; leitores em modo somente leitura |
| R-06 | Diagnóstico fraco ou custo de API acima do esperado | Média | Médio | Monitores determinísticos continuam valendo; tiering de modelos (gerente forte, especialistas baratos); Sentinel só roda com incidente aberto; pontuação expõe a qualidade real |
| R-13 | Envio de dados à OpenAI | Média | Médio | Ferramentas dos agentes só devolvem agregados e amostras pequenas de dado público; `SENTINEL_LLM_PROVIDER=ollama` troca para LLM local sem mudar código |
| R-07 | CNPJ alfanumérico quebra validações | Média | Alto | Regex `[0-9A-Z]` e DV com `ascii(c) - 48` nas regras do silver |
| R-08 | Licença do Docker Desktop se o projeto virar uso corporativo | Baixa | Médio | Docker Engine em Linux, Rancher Desktop ou Podman (o compose é o mesmo) |
| R-09 | Desempenho ruim de volumes montados no Windows | Alta | Médio | Usar volumes nomeados do Docker ou manter o repositório no filesystem do WSL2 |
| R-10 | Proxy corporativo com inspeção TLS | Baixa | Médio | `HTTPS_PROXY` e `RFB_CA_BUNDLE` suportados |

### 7.2 Riscos de uso (LGPD e ética)

| ID | Risco | Mitigação |
|---|---|---|
| R-11 | Uso de dados de sócios pessoa física fora da finalidade | A base já vem mascarada pela Receita; nenhuma tentativa de desmascarar; finalidades declaradas (crédito, KYC, prospecção B2B) |
| R-12 | Prospecção indevida de pessoa física | Prospecção restrita a dados da pessoa jurídica (CNAE, local, porte) |

---

## 8. Métricas de sucesso e governança

### 8.1 Critérios de aceite (verificados por medição, nunca declarados)

> **Nota (Passo 4 do Converge):** a fonte canônica dos critérios de aceite passou a ser o `engineering-brief.md` (AC-1..AC-8), cuja numeração difere desta tabela original. A nota do Sentinel virou o critério **F2-1** da fase 2 (ADR-0003).

| AC | Prova | Meta | Como medir |
|---|---|---|---|
| **AC-1** Completude | 37/37 arquivos carregados; linhas do raw iguais às linhas do CSV | Erros de parsing ≤ 0,001% | `raw.raw_load_log` |
| **AC-2** Tempo de processamento | Carga + dbt + monitores de uma competência | ≤ 4 h no hardware recomendado | Duração da DAG no Airflow |
| **AC-3** Frescor | Da detecção da nova competência até o gold | ≤ 24 h | `ops.competencias` |
| **AC-4** Qualidade | 100% das linhas classificadas; nenhuma rejeitada chega ao gold | 0 vazamentos | Testes dbt + eval de sobrevivência de defeitos |
| **AC-5** Consulta | Intenções MCP e tabelas gold agregadas | p95 ≤ 5 s | Eval de latência |
| **AC-6** Sentinel | Casos injetados diagnosticados corretamente | Match médio ≥ 0,8 | `ops.diagnoses` (pontuação contra `origin='chaos'`) |
| **AC-7** Idempotência | Reprocessar a competência | Contagens idênticas | Comparação de `ops.dq_metrics` |
| **AC-8** Soberania dos dados | O pipeline não faz chamadas externas além da Receita; o Sentinel envia só agregados | 0 linhas de dado em massa nos prompts | Revisão das ferramentas + log de prompts |

**AC-1 é o go/no-go.** Sem completude comprovada, nenhuma camada acima é confiável.

### 8.2 KPIs de operação

| KPI | Meta (mês 3) | Fonte |
|---|---|---|
| Competências processadas sem intervenção | ≥ 90% | `ops.competencias` |
| Tempo médio até diagnóstico de incidente (MTTD) | ≤ 15 min após o fim da DAG | `ops.incidents` vs `ops.diagnoses` |
| Taxa de rejeição por entidade | Estável (±0,1 p.p. mês a mês) | `ops.dq_metrics` |

### 8.3 Governança

- **Dono do produto e do código:** Bruno Nunes.
- **Revisão:** a cada fase, com demonstração e verificação dos AC da fase.
- **Mudanças de arquitetura:** registradas como ADR em `docs/adrs/`.

---

## 9. Roadmap de implementação

### Fase 0 — Fundação (semana 1)
- **Entregas:** `docker-compose` (PostgreSQL, Airflow, Sentinel/MCP; Ollama opcional), `.env`, estrutura do repositório.
- **Critério de saída:** `docker compose up` saudável; Airflow acessível; schema `ops` criado.

### Fase 1 — Ingestão (semanas 2–3)
- **Entregas:** cliente WebDAV, download com retomada, controle de competências, carga raw e log de carga.
- **Critério de saída:** **AC-1** com uma competência real.

### Fase 2 — Medalhão e qualidade (semanas 4–5)
- **Entregas:** modelos dbt bronze/silver/gold, regras de quarentena, seeds de domínio e monitores.
- **Critério de saída:** **AC-2, AC-4 e AC-7**.

### Fase 3 — Consumo (semanas 6–7)
- **Entregas:** publicação no PostgreSQL, servidor MCP com intenções curadas, consultas de exemplo para Power BI.
- **Critério de saída:** **AC-5**.

### Fase 4 — Sentinel (semanas 8–9)
- **Entregas:** crew hierárquico de 5 agentes, ferramentas somente leitura, injetor de falhas, gatilho e pontuação.
- **Critério de saída:** **AC-6 e AC-8**.

### Fase 5 — Endurecimento e demo (semana 10)
- **Entregas:** execução com duas competências reais seguidas, guia de operação e vídeo/demo.
- **Critério de saída:** **AC-3** e KPIs da seção 8.2 medidos.

---

## 10. Partes interessadas e personas

| Persona | Necessidade | O que a plataforma entrega |
|---|---|---|
| **Analista de crédito** | Situação, idade, porte, capital e Simples de um CNPJ | Ficha do CNPJ (gold + intenção MCP `ficha_cnpj`) |
| **Analista de KYC/PLD** | Quadro societário e empresas interligadas | `gold_socios_detalhe`, `gold_rede_societaria`, intenção `rede_societaria` |
| **Time comercial** | Listas de empresas ativas por setor e região | `gold_painel_prospeccao`, intenção `prospectar` |
| **Engenheiro de dados (operação)** | Saber o que quebrou e por quê | Incidentes, diagnósticos e post-mortems do Sentinel |
| **Avaliador técnico / recrutador** | Ver a arquitetura funcionando e medida | Repositório, ADRs, AC medidos e demo |

---

## 11. Registro de premissas e restrições

### 11.1 Premissas

| ID | Premissa | Confiança | Se estiver errada | Mitigação |
|---|---|---|---|---|
| A-01 | A Receita mantém publicação mensal no SERPRO+ via WebDAV | Média | Ingestão para | URL configurável; incidente de falha de listagem |
| A-02 | Uma competência cabe no hardware recomendado com spill em disco | Alta | AC-2 falha | Aumentar RAM/disco; processar por entidade |
| A-03 | O layout de 2026 segue o `cnpj-metadados.pdf` | Alta | Carga falha em `layout_drift` | Layout centralizado em um módulo, correção em um lugar |
| A-04 | Os modelos `gpt-5.6-luna` (especialistas) e `gpt-5.6-terra` (gerente) diagnosticam os casos injetados | Média | AC-6 abaixo da meta | Subir o tier do modelo por configuração |
| A-05 | Os dados são usados só para as finalidades declaradas | Alta | Risco LGPD | Seção 7.2 |

### 11.2 Restrições

| ID | Restrição | Impacto | Mitigação |
|---|---|---|---|
| C-01 | Uma pessoa, meio período | Cronograma de 8–10 semanas | Entregas por fase com valor isolado |
| C-02 | Dados on-premises | Sem warehouse gerenciado; só o LLM é externo | Stack 100% em containers; LLM trocável por Ollama |
| C-03 | DuckDB aceita um único escritor | Tarefas de escrita em série | Pool de 1 vaga |
| C-04 | Estação Windows com Docker Desktop | I/O de bind mount lento | Volumes nomeados / WSL2 |

---

## 12. Apêndice: arquitetura-alvo

### 12.1 Fluxo de dados

```text
SERPRO+ / Receita (WebDAV, 37 zips/mês)
      │  Airflow: detectar última competência → baixar (retomada) → validar CRC
      ▼
/data/landing/AAAA-MM/*.zip
      │  Airflow: checar layout → DuckDB read_csv (latin-1) → raw.raw_*
      ▼
DuckDB  raw ─▶ bronze (views tipadas) ─▶ silver (+ *_rejects) ─▶ gold
      │                                              │
      │  monitores de qualidade → ops.dq_metrics / ops.incidents (PostgreSQL)
      ▼                                              ▼
PostgreSQL gold (Power BI/SQL)            MCP (intenções curadas, somente leitura)
                                                     ▲
Sentinel (CrewAI + OpenAI API) ── lê logs, rejects e incidentes ── escreve só diagnósticos, patches propostos e post-mortems
```

### 12.2 Separação dos componentes (regra R3 da referência)

- O **Componente A** produz. O **Sentinel** observa, sempre somente leitura.
- O único caminho do Sentinel de volta ao pipeline é o **patch proposto**, que um humano revisa e aplica.
- O Sentinel é **pontuado** contra o ledger de incidentes injetados, nunca declarado correto.

### 12.3 Stack (referência)

Airflow 3.3 · DuckDB 1.5 · dbt-core 1.12 + dbt-duckdb 1.11 · PostgreSQL 17 · FastAPI + MCP · CrewAI 1.x · OpenAI API (Ollama opcional) · Docker Compose · Python 3.12.

---

## 13. Conclusão

A plataforma transforma uma publicação mensal grande e instável numa base confiável e rastreável para **crédito e risco, KYC/PLD e prospecção**. Os dados são processados inteiramente em infraestrutura própria, sem custo de licença (só a API do Sentinel é paga por uso), e a qualidade é **medida** (critérios AC-1 a AC-8). Com o Sentinel, o projeto também demonstra um sistema multiagente avaliado contra verdade de referência, que é a parte mais difícil e menos comum em portfólios.

**Recomendação: iniciar pelas Fases 0–2 e usar AC-1 como portão de decisão.**

---

**Versão:** 1.0 · **Última atualização:** 11/09/2026 · **Próxima revisão:** ao fim da Fase 1
