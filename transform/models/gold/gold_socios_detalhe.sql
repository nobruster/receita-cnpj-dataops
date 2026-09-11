-- Quadro societário com descrições (KYC). CPF já vem mascarado pela Receita.
select
    s.cnpj_basico,
    emp.razao_social,
    s.identificador_socio,
    ids.descricao                               as tipo_socio,
    s.nome_socio,
    s.cnpj_cpf_socio,
    s.qualificacao_socio,
    q.descricao                                 as qualificacao_socio_descricao,
    s.data_entrada_sociedade,
    s.pais,
    pai.descricao                               as pais_nome,
    s.representante_legal,
    s.nome_representante,
    s.qualificacao_representante,
    qr.descricao                                as qualificacao_representante_descricao,
    s.faixa_etaria,
    fe.descricao                                as faixa_etaria_descricao,
    s._competencia                              as competencia
from {{ ref('silver_socios') }} s
left join {{ ref('silver_empresas') }}          emp on emp.cnpj_basico = s.cnpj_basico
left join {{ ref('dom_identificador_socio') }}  ids on ids.codigo = s.identificador_socio
left join {{ ref('silver_dom_qualificacoes') }} q   on q.codigo   = s.qualificacao_socio
left join {{ ref('silver_dom_qualificacoes') }} qr  on qr.codigo  = s.qualificacao_representante
left join {{ ref('silver_dom_paises') }}        pai on pai.codigo = s.pais
left join {{ ref('dom_faixa_etaria') }}         fe  on fe.codigo  = s.faixa_etaria
