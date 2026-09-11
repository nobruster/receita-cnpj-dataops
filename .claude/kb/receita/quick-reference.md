# Domínio Receita/CNPJ — referência rápida

| Tema | Fato | Fonte |
|---|---|---|
| Onde baixar | SERPRO+ Nextcloud `https://arquivos.receitafederal.gov.br/index.php/s/<RFB_SHARE_TOKEN>`; WebDAV `/public.php/webdav`, auth `(token, "")`; pastas `AAAA-MM` desde 2023-05 (~6 GB/mês) | verificado no navegador em 11/09/2026 |
| Endereço antigo | `…/dados/cnpj/dados_abertos_cnpj/` → "Page not found" | idem |
| Arquivos | 37: Empresas0-9, Estabelecimentos0-9, Socios0-9, Simples, Cnaes, Motivos, Municipios, Naturezas, Paises, Qualificacoes | `cnpj-metadados.pdf` |
| Formato | sem cabeçalho, `;`, `"`, ISO-8859-1 (bytes cp1252 aparecem → fallback de transcodificação) | layout + teste real |
| Layout | fonte única: `pipeline/receita/layout.py` | — |
| CNPJ alfanumérico | desde jul/2026; raiz/ordem `[0-9A-Z]`, DV numérico; valor do caractere `ord(c)-48`; módulo 11 | IN RFB 2.229/2024 |
| Defeitos conhecidos (não são incidente) | motivo 32 sem domínio; países órfãos; UF `EX`; capital `999999999999`; CEP com 7 dígitos; representante `***000000**` | auditoria caiopizzol (2026-04) |
| Placeholders de data | `0`/`00000000` = nulo (não é defeito) | layout |
