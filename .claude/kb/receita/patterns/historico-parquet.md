# Padrão: histórico mensal em Parquet (AC-8)

Ao concluir a competência: `COPY (SELECT * FROM silver.silver_<ent>) TO '/data/history/competencia=AAAA-MM/<ent>.parquet' (FORMAT parquet, COMPRESSION zstd)` para empresas, estabelecimentos, socios, simples. Retenção: 12 competências (as mais antigas são apagadas). Comparação sem precisar do raw: `read_parquet('/data/history/competencia=*/estabelecimentos.parquet', hive_partitioning=true)`.
