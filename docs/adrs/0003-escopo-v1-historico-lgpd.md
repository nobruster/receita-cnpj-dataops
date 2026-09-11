# ADR-0003 — Escopo do v1, histórico mensal e risco LGPD aceito

- **Status:** aceito (2026-09-11) · origem: interrogatório do Passo 1 (D-1..D-3) e consenso do Passo 4.

## Decisões
1. **Sentinel e MCP são fase 2 (D-3).** O código permanece no repositório e testado, mas os serviços ficam no profile `fase2` do compose e não contam para o aceite do v1. O critério da fase 2 é o **F2-1** (match médio ≥ 0,8 com rota crew).
2. **Histórico mensal em Parquet, 12 competências (D-1 → AC-8).** Ao concluir cada competência, o silver aceito é exportado para `/data/history/competencia=AAAA-MM/`. Histórico com vigência linha a linha (SCD2) fica fora. **Sem carga retroativa:** a stack processa só a última competência publicada; o histórico se acumula a partir da primeira execução.
3. **Contatos mantidos como publicados (D-2).** E-mail/telefone de MEI e empresário individual continuam nas saídas. **Risco LGPD aceito** enquanto o uso for pessoal/portfólio; dono: Bruno; gatilho de revisão: qualquer repasse de listas ou uso corporativo.
4. **ACs canônicos são os do engineering brief** (AC-1..AC-8). O BRD referencia o brief.

## Consequências
- `docker compose up` sobe só o backbone; `--profile fase2` acrescenta Sentinel e MCP.
- Disco: ~6 GB por competência de histórico Parquet estimados (a medir), além dos zips (retenção de 2).
