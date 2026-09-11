# Padrão: timeouts e retries amarrados aos ACs

O orçamento de tempo sai do brief, não de chute:
- AC-3 (detecção → dado utilizável ≤ 24 h) = download + processamento.
- AC-2 (processamento ≤ 4 h) começa em `processamento_iniciado_em` (início da carga), não no download.

Configuração: `baixar` com `execution_timeout=6h`, `retries=2`, `retry_delay=10min` (pior caso ~18 h, retomando por `Range`); tarefas de processamento com `execution_timeout` ≤ 4 h somadas. Servidor abaixo de ~95 KB/s médios estoura o AC-3 por causa externa — o eval reporta, não esconde.
