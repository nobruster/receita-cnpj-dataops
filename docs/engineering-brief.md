# Engineering Brief — Plataforma DataOps do CNPJ (Passo 1 · Intent)

> Versão markdown do `engineering-brief.pdf`. **Consenso travado em 11/09/2026**, depois do interrogatório do Passo 1, e por isso passa a alimentar o build (mesmo ciclo de vida da referência: PDF durante o alinhamento, markdown depois). **Não nomeia tecnologia.**

## Problema
A fonte é **grande, instável e imperfeita**:
- 37 arquivos por mês, cerca de 6 GB compactados, com dezenas de milhões de linhas;
- servidor lento que já mudou de endereço;
- layout sujeito a mudança e CNPJ alfanumérico desde jul/2026;
- defeitos publicados pela própria Receita.

O consumo é **manual e sem verificação**. Por isso, crédito, KYC/PLD e prospecção decidem sobre dado de qualidade desconhecida.

## Quem sofre
| Quem | Como sofre |
|---|---|
| Analista de crédito | Base atrasada ou incompleta: aprova CNPJ irregular ou recusa quem não devia |
| Analista de KYC/PLD | Quadro societário sem histórico e sem ligação entre empresas |
| Time comercial | Listas com empresas baixadas |
| Engenharia de dados | Ciclo mensal manual, com falhas descobertas tarde |

## Escopo
**Dentro (v1):**
- 100% dos arquivos da última competência, sem intervenção;
- veredito para 100% das linhas (aceita ou em quarentena com motivo);
- CNPJ alfanumérico;
- alerta quando a fonte falha;
- comparação mês a mês e **12 meses de histórico**;
- ficha por CNPJ, quadro societário, rede entre empresas e listas de prospecção.

**Fora (fase 2 ou separado):**
- consulta em linguagem natural;
- diagnóstico autônomo por agentes;
- histórico com vigência linha a linha;
- enriquecimento com outras fontes;
- programa de LGPD (risco aceito, ver D-2);
- escolha de tecnologia.

## Critérios de aceite (verificáveis)
| ID | Critério | Como verificar | KPI |
|---|---|---|---|
| AC-1 | 37/37 arquivos; linhas lidas = publicadas; erro de leitura ≤ 0,001% | Registro de carga por arquivo | Competências completas → 100% |
| AC-2 | Com os arquivos locais, competência utilizável em ≤ 4 h (hardware de referência) | Duração registrada | Tempo de processamento |
| AC-3 | Da detecção da nova publicação até o dado utilizável ≤ 24 h | Hora de detecção vs. conclusão | Frescor |
| AC-4 | 100% das linhas classificadas; zero linha em quarentena no consumo | Aceitas + quarentena = lidas; teste de vazamento | Linhas verificadas 0% → 100% |
| AC-5 | Consultas agregadas de prospecção/resumo com p95 ≤ 5 s | Bateria cronometrada | Latência |
| AC-6 | Reprocessar a mesma competência dá contagens idênticas | Duas execuções comparadas | Confiabilidade |
| AC-7 | Arquivo ausente, corrompido, layout novo, queda de volume e fonte fora do ar viram alerta em 100% dos casos simulados | Falhas simuladas | Falhas descobertas tarde → 0 |
| AC-8 | As últimas 12 competências ficam consultáveis e comparáveis | Consulta a mês antigo + diferença entre dois | Meses consultáveis 1 → 12 |

**AC-1 é o go/no-go.**

## Métricas (atual → alvo no mês 3)
- Competências processadas sem intervenção: 0 → ≥ 90%
- Da detecção à base utilizável: indefinido → ≤ 24 h
- Linhas com veredito: 0% → 100%
- Oscilação da taxa de quarentena mês a mês: não medida → ± 0,1 p.p.

## Decisões do interrogatório
| ID | Pergunta | Decisão | Dono |
|---|---|---|---|
| D-1 | Histórico para KYC/crédito | Foto mensal compacta, 12 meses (AC-8) | Bruno |
| D-2 | Contato de pessoa física (MEI/empresário individual) nas listas | **Manter como a Receita publica.** Risco LGPD aceito enquanto o uso for pessoal/portfólio | Bruno |
| D-3 | Consulta em linguagem natural e agentes | **Fora do v1** (fase 2, depois de AC-1 provado) | Bruno |

## Premissas
| ID | Premissa | Se estiver errada |
|---|---|---|
| P-01 | A Receita segue publicando uma pasta por mês no repositório atual | O ciclo para; o AC-7 precisa avisar |
| P-02 | Uma competência cabe no hardware de referência (16–32 GB de RAM, SSD) | O AC-2 falha; revisar hardware |
| P-03 | O layout segue o documento oficial de metadados | O AC-7 dispara; ajuste em um único lugar |
| P-04 | O uso é pessoal/portfólio, sem repasse de listas | Reabrir D-2 |
