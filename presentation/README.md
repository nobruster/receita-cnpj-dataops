# presentation/ — deck do projeto

Material de apresentação. Cada arquivo é um `.html` **autocontido** (CSS embutido, sem rede): abra
no navegador e role para avançar. Não faz parte da plataforma — nada em `pipeline/`, `transform/`,
`dags/` ou `sentinel/` importa, serve ou testa esta pasta.

| Arquivo | O que é | Atos |
|---|---|---|
| [`receita-cnpj-dataops-deck.html`](receita-cnpj-dataops-deck.html) | O deck deste projeto: o problema (85 GB/mês de uma fonte instável), o corte em dois componentes, o caminho do dado, a decisão de quarentena, os critérios de aceite medidos, o Sentinel com nota e o método Converge. | I–VII |

## Como usar

- **Apresentar:** abra o arquivo no navegador e role. Cada `<section class="slide">` é um slide de tela cheia.
- **Exportar PDF:** imprimir → paisagem → margens mínimas → salvar como PDF.
- **Editar:** é HTML puro; o tema vive nas variáveis CSS no topo do arquivo (`--bg`, `--accent`, ...).

> Os números do deck (ACs, contagem de falhas, tarefas da DAG) vêm de
> [`../docs/engineering-brief.md`](../docs/engineering-brief.md) e do relatório de
> `python -m pipeline.evals`. Ao mudar o comportamento do pipeline, atualize o deck junto —
> um slide desatualizado é pior que nenhum slide.
