# prompts/ — Converge: as 4 passagens de planejamento

A boca do funil. Antes de qualquer código, o problema viaja de um documento de negócio até
**dois planos endurecidos por adversário**, em quatro passagens ordenadas. Estes arquivos são os
**prompts do operador**: texto para colar numa engine de IA, uma passagem por vez. Não há nada
para executar aqui — só ler e colar.

A saída final desta pasta — [`../sketch/receita-backbone.md`](../sketch/receita-backbone.md) e
[`../sketch/sentinel-engine.md`](../sketch/sentinel-engine.md) — é o que os agentes de tecnologia
constroem depois. Acertar aqui é mais barato que corrigir no código.

> Contexto do projeto (o corte em dois componentes, a frota de agentes, decisões D-1..D-3,
> critérios de aceite) está em [`../CLAUDE.md`](../CLAUDE.md) e em
> [`../.claude/rules/agent-operating-rules.md`](../.claude/rules/agent-operating-rules.md) —
> aqui é referenciado, não duplicado.

---

## O caminho, de relance

| Passo | Engine usada aqui | Entrada | Saída | Portão |
|---|---|---|---|---|
| [P1 Intent](p1-intent.md) | Claude (chat, sem repo) | `docs/business-requirements-document.pdf` | [`docs/engineering-brief.pdf`](../docs/engineering-brief.pdf) | Problema confirmado, **sem tecnologia** |
| [P2 Structure](p2-structure.md) | Claude Code (com o repo) | brief + repo | [`docs/tech-spec.md`](../docs/tech-spec.md) + [`p2-structure-grounding.md`](../docs/converge/p2-structure-grounding.md) | Cada afirmação aterrada no código |
| [P3 Decomposition](p3-decomposition.md) | Claude Code | spec | [`sketch/receita-backbone.md`](../sketch/receita-backbone.md), [`sketch/sentinel-engine.md`](../sketch/sentinel-engine.md) | Dois planos na costura A/B |
| [P4 Consensus](p4-consensus.md) | **Outra** engine (aqui: subagente Sonnet em contexto novo) | os dois planos | [`docs/converge/p4-consensus.md`](../docs/converge/p4-consensus.md) | Toda objeção vira FIX ou ACEITO |

Depois das quatro passagens vem o resto do método, que já não é prompt de operador:

1. **ADRs** — [`docs/adrs/`](../docs/adrs/): o que foi decidido e por quê (D-1 histórico, D-2 LGPD, D-3 escopo v1).
2. **Task-Specs** — [`tasks/`](../tasks/), geradas pela skill [`task-spec`](../.claude/skills/task-spec/): cada mudança nasce com evals bash.
3. **Frota de agentes** — [`.claude/agents/`](../.claude/agents/) aterrada nos KBs [`.claude/kb/`](../.claude/kb/) (regra R2).
4. **Gate dos closers** — reviewer → simplifier → fix → documenter (R11): resultado em
   [`docs/converge/closers-review.md`](../docs/converge/closers-review.md).

## Como este projeto usou cada passagem

- **P1** trocou o BRD genérico por decisões nossas: só a última competência, histórico Parquet de
  12 meses (D-1), campos de contato mantidos com risco aceito (D-2), Sentinel e MCP fora do v1 (D-3).
- **P2** aterrou a spec no layout real da Receita (37 arquivos, CNPJ alfanumérico, defeitos conhecidos
  da fonte) em vez de confiar no documento.
- **P3** produziu os dois planos na costura entre o backbone determinístico e o Sentinel probabilístico.
- **P4** rodou numa engine diferente e devolveu as objeções O1–O7 (rótulo errado do AC-6, janela do
  AC-2 incluindo download, Sentinel subindo por padrão contra a D-3, ordem de build, escritores fora
  do pool, premissa de memória, comentário morto). Todas resolvidas antes do código final.

## Por que a engine muda a cada passagem

Cada passo pede um tipo de pensamento diferente: conversa sem repo em P1 (para não pular para a
solução), repo em mãos em P2 e P3 (para aterrar), e **outra cabeça** em P4 — um revisor que não
escreveu o plano encontra o que o autor não consegue enxergar. Quando não há uma segunda engine à
mão, vale um subagente em contexto novo e com outro modelo, que foi o que fizemos aqui.
