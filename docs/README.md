# docs/ — referências e registros de decisão

O acervo de documentação do projeto. Nenhum código mora aqui. São dois tipos de documento: o
**"por quê / o quê"** de entrada (BRD, engineering brief, tech spec) e o **"o que decidimos"** de
saída (ADRs, consenso P4, gate dos closers).

> Contexto do projeto (corte em dois componentes, frota de agentes, regras R1–R11) está em
> [`../CLAUDE.md`](../CLAUDE.md) e [`../.claude/rules/agent-operating-rules.md`](../.claude/rules/agent-operating-rules.md).
> O passo a passo de operação está em [`GUIA.md`](GUIA.md).

---

## Entradas (o problema)

| Arquivo | O que é |
|---|---|
| [`business-requirements-document.md`](business-requirements-document.md) · [`.pdf`](business-requirements-document.pdf) | O BRD: caso de negócio, casos de uso (crédito e risco, KYC/PLD, prospecção), requisitos BR/RF/RNF. Projeto pessoal / portfólio. |
| [`engineering-brief.md`](engineering-brief.md) · [`.pdf`](engineering-brief.pdf) | Saída da passagem P1 do Converge. Só problema — **não nomeia tecnologia**. Carrega os critérios de aceite **AC-1..AC-8 canônicos** e as decisões D-1, D-2, D-3. |
| [`tech-spec.md`](tech-spec.md) | Saída da P2: a arquitetura em 7 camadas (C1 fonte → C7 qualidade) aterrada no layout real da Receita. |

## Método (como foi construído)

| Arquivo | O que é |
|---|---|
| [`converge/p2-structure-grounding.md`](converge/p2-structure-grounding.md) | Cada afirmação da spec conferida contra o código/layout, com as lacunas G1–G7. |
| [`converge/p4-consensus.md`](converge/p4-consensus.md) | Revisão adversarial em outra engine: objeções O1–O7, cada uma resolvida como FIX ou ACEITO. |
| [`converge/closers-review.md`](converge/closers-review.md) | Gate dos closers: os 16 achados do reviewer independente, o destino de cada um e o teste que prova a correção. |
| [`../prompts/`](../prompts/) | Os prompts de operador das quatro passagens. |

## Saídas (o que decidimos e como se opera)

| Arquivo | O que é |
|---|---|
| [`adrs/`](adrs/) | Registros de decisão arquitetural — veja o [índice](adrs/README.md). |
| [`ARQUITETURA.md`](ARQUITETURA.md) | O desenho vigente: camadas, quarentena, interfaces do Sentinel, concorrência, ledger `ops`, rede e LGPD. |
| [`GUIA.md`](GUIA.md) | Guia passo a passo de instalação e operação no Windows + Docker Desktop. |
| [`src/`](src/) | Fonte HTML dos PDFs gerados (o brief). Edite o HTML, regere o PDF. |

## Regra de leitura para agentes

O **brief manda** nos critérios de aceite: se o BRD e o brief divergirem num AC, o brief vence
(está escrito no próprio BRD). Toda afirmação sobre uma tecnologia precisa ser aterrada no KB
correspondente antes de ir para o código (regra R2).
