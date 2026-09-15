{#
  Rede PJ -> PJ (KYC/PLD): empresa sócia (identificador_socio = 1) -> empresa investida.
  Para sócio PJ a Receita publica a RAIZ (8 posições) em cnpj_cpf_socio — competências
  antigas traziam o CNPJ completo (14), então as duas formas são aceitas. O elo com a
  empresa sócia é sempre pela raiz (primeiras 8 posições).
#}
select
    upper(s.cnpj_cpf_socio)                       as cnpj_socio,
    upper(substr(s.cnpj_cpf_socio, 1, 8))         as cnpj_basico_socio,
    es.razao_social                               as razao_social_socio,
    s.cnpj_basico                                 as cnpj_basico_investida,
    ei.razao_social                               as razao_social_investida,
    s.qualificacao_socio,
    q.descricao                                   as qualificacao_socio_descricao,
    s.data_entrada_sociedade,
    s._competencia                                as competencia
from {{ ref('silver_socios') }} s
left join {{ ref('silver_empresas') }}          es on es.cnpj_basico = upper(substr(s.cnpj_cpf_socio, 1, 8))
left join {{ ref('silver_empresas') }}          ei on ei.cnpj_basico = s.cnpj_basico
left join {{ ref('silver_dom_qualificacoes') }} q  on q.codigo = s.qualificacao_socio
where s.identificador_socio = '1'
  and (regexp_full_match(upper(s.cnpj_cpf_socio), '[0-9A-Z]{8}')
       or regexp_full_match(upper(s.cnpj_cpf_socio), '[0-9A-Z]{12}[0-9]{2}'))
