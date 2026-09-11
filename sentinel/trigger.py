"""B1 — gatilho do Sentinel: consulta ``ops.incidents``, despacha, pontua, registra.

Por que polling e não callback do Airflow? A maioria das falhas NÃO derruba a DAG:
linhas ruins vão para quarentena e a DAG termina com sucesso (é o objetivo da
quarentena). Então o gatilho consulta o mesmo ledger que o oráculo lê — gatilho e
pontuação ficam consistentes, e o Componente A nunca chama o B (regra R3).

Um caso = incidentes abertos de UMA competência cuja DAG já terminou
(``ops.competencias.status`` em publicada/falhou). Roteamento:

* 2+ chaves observadas pelo backbone -> Flow determinístico de cascata;
* 1 chave e LLM configurado          -> crew hierárquico;
* sem LLM (``SENTINEL_LLM_PROVIDER=none`` ou sem chave) -> Flow determinístico;
* crew falhou (API fora, cota...)    -> ``no-run`` honesto, nunca nota inventada.

    python -m sentinel.trigger --once          # processa o que estiver pendente
    python -m sentinel.trigger --watch         # loop (serviço do docker-compose)
    python -m sentinel.trigger --competencia 2026-08
"""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import asdict, dataclass
from typing import Any

from chaos.failures import FAILURES
from pipeline import ops
from sentinel.flow import CASCADE_KEY, observed_keys, triage
from sentinel.llm import llm_available
from sentinel.models import Diagnosis
from sentinel.scoring import ScoreResult, score

log = logging.getLogger("sentinel.trigger")
VALID_KEYS = ", ".join([*FAILURES, CASCADE_KEY])


@dataclass(frozen=True, slots=True)
class CaseResult:
    competencia: str
    route: str
    observed: list[str]
    truth: list[str]
    diagnosis: Diagnosis | None
    score: ScoreResult


def pending_cases() -> list[str]:
    with ops.session() as conn:
        rows = conn.execute(
            "SELECT DISTINCT i.competencia FROM ops.incidents i "
            "JOIN ops.competencias c ON c.competencia = i.competencia "
            "WHERE i.status = 'open' AND c.status IN ('publicada', 'falhou') ORDER BY 1"
        ).fetchall()
    return [r["competencia"] for r in rows]


def truth_keys(competencia: str) -> list[str]:
    with ops.session() as conn:
        rows = conn.execute(
            "SELECT DISTINCT failure_key FROM ops.incidents WHERE competencia = %s AND origin = 'chaos' "
            "AND status = 'open'", [competencia]
        ).fetchall()
    return sorted(r["failure_key"] for r in rows)


def run_crew(competencia: str, key_hint: str, llm_override: Any | None = None) -> Diagnosis | None:
    from sentinel.crew import HUMAN_GATED_FAILURES, SentinelCrew, diagnosis_from_output

    sc = SentinelCrew(llm_override=llm_override, human_gated_fix=key_hint in HUMAN_GATED_FAILURES,
                      with_knowledge=key_hint == "orphan_domain" and llm_override is None)
    c = sc.crew()
    result = c.kickoff(inputs={"competencia": competencia, "chaves_validas": VALID_KEYS})
    return diagnosis_from_output(result, c)


def run_case(competencia: str, llm_override: Any | None = None) -> CaseResult:
    observed = observed_keys(competencia)
    truth = truth_keys(competencia)
    diag: Diagnosis | None
    if len(observed) > 1:
        route, diag = "cascade-flow", triage(competencia)
    elif llm_override is not None or llm_available():
        route = "crew"
        try:
            diag = run_crew(competencia, next(iter(observed), ""), llm_override)
        except Exception as exc:  # API fora do ar, cota, timeout: registra no-run
            log.exception("crew não concluiu: %s", exc)
            route, diag = "no-run", None
    else:
        route, diag = "deterministic-flow", triage(competencia)
    res = CaseResult(competencia, route, sorted(observed), truth, diag, score(diag, truth))
    _record(res)
    return res


def _record(res: CaseResult) -> None:
    with ops.session() as conn:
        ids = [r["incident_id"] for r in conn.execute(
            "SELECT incident_id FROM ops.incidents WHERE competencia = %s AND status = 'open'",
            [res.competencia]).fetchall()]
        d = res.diagnosis
        conn.execute(
            "INSERT INTO ops.diagnoses (incident_ids, route, failure_key, sub_failures, evidence_surface, "
            "confidence, summary, score_tier, match_score, evidence_score) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            [ids, res.route, d.failure_key if d else None, d.sub_failures if d else [],
             d.evidence_surface if d else None, d.confidence if d else None, d.summary if d else None,
             res.score.tier, res.score.match, res.score.evidence],
        )
    ops.mark_incidents(ids, "diagnosed")


def run_pending() -> list[CaseResult]:
    out = []
    for comp in pending_cases():
        r = run_case(comp)
        log.info("[SCORECARD] %s route=%s tier=%s match=%.2f evidence=%s truth=%s diagnosed=%s",
                 comp, r.route, r.score.tier, r.score.match, r.score.evidence, r.truth, r.score.diagnosed)
        out.append(r)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--once", action="store_true")
    g.add_argument("--watch", action="store_true")
    g.add_argument("--competencia")
    p.add_argument("--intervalo", type=int, default=60)
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    ops.ensure_schema()
    if a.competencia:
        r = run_case(a.competencia)
        print({**asdict(r.score), "route": r.route, "diagnosis": r.diagnosis.model_dump() if r.diagnosis else None})
    elif a.watch:
        while True:
            try:
                run_pending()
            except Exception:
                log.exception("ciclo do gatilho falhou; tentando de novo no próximo intervalo")
            time.sleep(a.intervalo)
    else:
        for r in run_pending():
            print(r.competencia, r.route, asdict(r.score))


if __name__ == "__main__":
    main()
