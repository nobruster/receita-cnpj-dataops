"""Gerador de amostra no formato da Receita + injetor de falhas (verdade de referência).

Equivalente ao ``src/gen`` do ws-3: permite testar o pipeline inteiro sem baixar
6 GB e pontuar o Sentinel contra falhas conhecidas (``ops.incidents`` com
``origin='chaos'``).
"""
