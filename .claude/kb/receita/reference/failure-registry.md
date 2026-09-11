# Registro de falhas (chaos) → detecção

Fonte de verdade: `chaos/failures.py`. Pipeline (`PIPELINE_FAILURE`): `missing_file`, `corrupt_zip`, `layout_drift`. Monitor: `volume_drop`, `orphan_domain`, `source_unavailable`, `stale_release`. Quarentena (silver): `invalid_cnpj`, `duplicate_key`, `invalid_date`, `invalid_domain`, `invalid_capital`, `encoding_mojibake`, `orphan_socio`. Cascata: `invalid_cnpj + orphan_socio + volume_drop`.
