"""Flow determinístico (CrewAI Flows + roteamento condicional) — sem LLM.

Faz a triagem de um caso a partir dos incidentes que o PRÓPRIO backbone abriu
(``origin`` pipeline/monitor — nunca os de chaos) e roteia:

* ``nenhum``  -> sem incidente;
* ``unico``   -> Diagnosis da chave observada (base para o crew confirmar/explicar);
* ``cascata`` -> ``multi_failure_cascade`` com os membros em ``sub_failures``.

É o caminho usado para cascatas (como no ws-3) e o fallback honesto quando não há
LLM configurado (``SENTINEL_LLM_PROVIDER=none``): a pontuação mostra exatamente
quanto o crew agrega sobre essa linha de base.
"""

from __future__ import annotations

from crewai.flow.flow import Flow, listen, router, start
from pydantic import BaseModel, Field

from pipeline import ops
from sentinel.models import Diagnosis

CASCADE_KEY = "multi_failure_cascade"
IGNORED = {"parse_errors"}  # sinal auxiliar: não é causa raiz sozinho


class TriageState(BaseModel):
    competencia: str = ""
    observed: dict[str, str] = Field(default_factory=dict)  # failure_key -> superfície
    diagnosis: Diagnosis | None = None


def observed_keys(competencia: str) -> dict[str, str]:
    with ops.session() as conn:
        rows = conn.execute(
            "SELECT failure_key, min(evidence_surface) AS surface FROM ops.incidents i "
            f"WHERE competencia = %s AND origin IN ('pipeline', 'monitor') AND {ops.UNDIAGNOSED} GROUP BY 1",
            [competencia],
        ).fetchall()
    return {r["failure_key"]: r["surface"] for r in rows if r["failure_key"] not in IGNORED}


class SentinelFlow(Flow[TriageState]):
    @start()
    def coletar(self) -> None:
        self.state.observed = observed_keys(self.state.competencia)

    @router(coletar)
    def rotear(self) -> str:
        n = len(self.state.observed)
        return "nenhum" if n == 0 else ("unico" if n == 1 else "cascata")

    @listen("nenhum")
    def sem_incidente(self) -> Diagnosis:
        self.state.diagnosis = Diagnosis(failure_key="no_incident", confidence=1.0,
                                         summary="nenhum incidente aberto pelo backbone")
        return self.state.diagnosis

    @listen("unico")
    def diagnostico_unico(self) -> Diagnosis:
        key, surface = next(iter(self.state.observed.items()))
        self.state.diagnosis = Diagnosis(failure_key=key, evidence_surface=surface, confidence=0.8,
                                         summary=f"{key} observado em {surface}")
        return self.state.diagnosis

    @listen("cascata")
    def diagnostico_cascata(self) -> Diagnosis:
        membros = sorted(self.state.observed)
        self.state.diagnosis = Diagnosis(
            failure_key=CASCADE_KEY, sub_failures=membros,
            evidence_surface=", ".join(self.state.observed[k] for k in membros), confidence=0.9,
            summary=f"{len(membros)} falhas simultâneas: {', '.join(membros)}",
        )
        return self.state.diagnosis


def triage(competencia: str) -> Diagnosis:
    flow = SentinelFlow()
    flow.kickoff(inputs={"competencia": competencia})
    assert flow.state.diagnosis is not None
    return flow.state.diagnosis
