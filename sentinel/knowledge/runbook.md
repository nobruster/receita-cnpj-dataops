# Runbook do Sentinel — dados abertos do CNPJ

## Defeitos CONHECIDOS da fonte (não abrir incidente)
- Motivo de situação `32` aparece em estabelecimentos, mas não existe em Motivos.csv.
- Alguns códigos de país (ex.: 150, 367, 359) não existem em Paises.csv.
- UF `EX` = estabelecimento no exterior (não documentado, mas legítimo).
- Capital social `999999999999` = sentinela de capital não informado.
- CEP com 7 dígitos = zero à esquerda perdido (o bronze corrige).

## Como desambiguar
- **orphan_domain vs invalid_domain**: `invalid_domain` é valor fora do formato/domínio fixo
  (situação `07`, UF inexistente) e vai para rejects. `orphan_domain` é código com formato válido
  mas ausente do domínio publicado no mesmo mês (CNAE/município/natureza) — vira flag e métrica.
  Se só motivo/país estiverem órfãos, é defeito conhecido: não é incidente.
- **volume_drop vs missing_file**: `missing_file` derruba o pipeline antes da carga (log
  PIPELINE_FAILURE). `volume_drop` é a carga completa, mas com bem menos linhas que o mês anterior
  (entrega parcial da Receita ou arquivo truncado dentro do zip válido).
- **corrupt_zip vs layout_drift**: zip corrompido falha ao extrair; layout_drift extrai, mas o
  número de campos não bate com o layout.
- **encoding_mojibake**: sequências como "Ã‡", "Ã£" nas razões sociais = trecho em UTF-8 dentro do
  arquivo ISO-8859-1.

## Correções típicas (sempre propostas, nunca automáticas)
- missing_file / corrupt_zip: apagar o arquivo local e rebaixar (o download retoma).
- layout_drift: atualizar `pipeline/receita/layout.py` + modelo bronze após conferir o PDF de layout.
- volume_drop: aguardar republicação da Receita e reprocessar a competência (destrutivo: aprovação).
- duplicate_key: manter a primeira ocorrência (já feito no silver); abrir chamado se persistir.
