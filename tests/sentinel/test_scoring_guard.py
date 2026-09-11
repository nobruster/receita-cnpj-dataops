"""Oráculo, guardrail e guarda de SQL — determinísticos, sem LLM e sem banco."""

from sentinel.guardrails import validate_postmortem
from sentinel.models import Diagnosis, Postmortem
from sentinel.scoring import score
from sentinel.tools.readers import FORBIDDEN, run_guarded_select


def d(key, surface="", subs=None):
    return Diagnosis(failure_key=key, evidence_surface=surface, sub_failures=subs or [])


def test_exato_com_evidencia():
    r = score(d("invalid_cnpj", "silver_estabelecimentos_rejects"), ["invalid_cnpj"])
    assert (r.tier, r.match, r.evidence) == ("exact", 1.0, 1.0)


def test_chave_certa_evidencia_inventada():
    r = score(d("orphan_socio", "gold_qualquer"), ["orphan_socio"])
    assert r.match == 1.0 and r.evidence == 0.0


def test_erro_pontua_zero():
    assert score(d("invalid_date"), ["invalid_cnpj"]).tier == "miss"


def test_cascata_parcial():
    r = score(d("multi_failure_cascade", subs=["invalid_cnpj"]), ["invalid_cnpj", "orphan_socio"])
    assert r.tier == "cascade" and r.match == 0.75


def test_no_run_nunca_inventa_nota():
    r = score(None, ["invalid_cnpj"])
    assert r.tier == "no-run" and r.match == 0.0


def test_sem_verdade_nao_pontua():
    assert score(d("volume_drop"), []).tier == "unscored"


def test_guardrail_recusa_lixo():
    ok, _ = validate_postmortem(Postmortem(incident_key="encoding_mojibake", root_cause="AÃ\x87Ã\x83O quebrado lá",
                                           evidence="x"))
    assert not ok
    ok, _ = validate_postmortem(Postmortem(incident_key="encoding_mojibake",
                                           root_cause="Trecho em UTF-8 dentro de arquivo latin-1."))
    assert ok


def test_guarda_sql_bloqueia_escrita():
    for sql in ("DROP TABLE gold.gold_empresa_detalhe", "select 1; delete from x",
                "SELECT * FROM read_csv('/etc/passwd')", "select * from ops.incidents"):
        assert run_guarded_select(sql).startswith("recusado"), sql
    assert FORBIDDEN.search("ATTACH 'x'")
