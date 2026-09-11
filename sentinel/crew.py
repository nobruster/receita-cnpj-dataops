"""Crew hierárquico do Sentinel (Componente B).

A1 gerente (``manager_agent``) delega a dois esquadrões:

* Investigação — A2 Log Analyst (I1/I2) + A3 Data Profiler (I3/I4). A tarefa de
  síntese emite um :class:`~sentinel.models.Diagnosis` tipado, pontuado pelo oráculo.
* Resolução — A4 Data Engineer (patch proposto, nunca aplicado) + A5 Incident
  Commander (histórico + post-mortem tipado com guardrail).

Contrato do processo hierárquico: o gerente vai em ``manager_agent=`` (não em
``agents=[]``) e só ele delega; especialistas têm ``allow_delegation=False``.

Capacidades exercitadas pelo mapa de falhas (``chaos.failures``):

* HITL — ``propose_fix_task.human_input`` quando a falha tem correção destrutiva.
* Guardrails + output_pydantic — post-mortem tipado e validado (encoding_mojibake).
* Knowledge/RAG — runbook de desambiguação (orphan_domain), opcional.
* Tool reliability — ``max_retry_limit`` no Log Analyst (arquivos/zips instáveis).
* Flows — cascatas vão para ``sentinel.flow`` (determinístico).

``llm_override`` aplica um LLM (ou stub de teste) a todos os agentes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from pipeline.config import get_settings
from sentinel.guardrails import validate_postmortem
from sentinel.llm import build_llm
from sentinel.models import Diagnosis, Postmortem
from sentinel.tools import (
    ProfileRejects,
    ProposePatch,
    QueryIncidentHistory,
    QueryWarehouse,
    ReadDbtRunResults,
    ReadPipelineLogs,
    ReadQualityMetrics,
    WritePostmortem,
)

RUNBOOK_PATH = Path(__file__).resolve().parent / "knowledge" / "runbook.md"
HUMAN_GATED_FAILURES: frozenset[str] = frozenset({"duplicate_key", "volume_drop"})


def _knowledge_sources() -> list[Any]:
    from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

    return [StringKnowledgeSource(content=RUNBOOK_PATH.read_text(encoding="utf-8"))]


@CrewBase
class SentinelCrew:
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def __init__(self, llm_override: Any | None = None, *, human_gated_fix: bool = False,
                 with_knowledge: bool = False, memory: bool = False) -> None:
        self._llm_override = llm_override
        self._human_gated_fix = human_gated_fix
        self._with_knowledge = with_knowledge
        self._memory = memory
        s = get_settings()
        self._worker_llm = llm_override or build_llm(s.sentinel_llm_model, s)
        self._manager_llm = llm_override or build_llm(s.sentinel_manager_model or s.sentinel_llm_model, s)

    def _cfg(self, name: str, llm: Any) -> dict[str, Any]:
        cfg = dict(self.agents_config[name])
        cfg["llm"] = llm
        return cfg

    def manager_agent_instance(self) -> Agent:
        return Agent(config=self._cfg("manager", self._manager_llm), allow_delegation=True)

    @agent
    def log_analyst(self) -> Agent:
        return Agent(config=self._cfg("log_analyst", self._worker_llm),
                     tools=[ReadPipelineLogs(), ReadDbtRunResults()], allow_delegation=False, max_retry_limit=2)

    @agent
    def data_profiler(self) -> Agent:
        return Agent(config=self._cfg("data_profiler", self._worker_llm),
                     tools=[ProfileRejects(), ReadQualityMetrics(), QueryWarehouse()], allow_delegation=False)

    @agent
    def data_engineer(self) -> Agent:
        return Agent(config=self._cfg("data_engineer", self._worker_llm), tools=[ProposePatch()],
                     allow_delegation=False)

    @agent
    def incident_commander(self) -> Agent:
        return Agent(config=self._cfg("incident_commander", self._worker_llm),
                     tools=[QueryIncidentHistory(), WritePostmortem()], allow_delegation=False)

    @task
    def analyze_pipeline_logs_task(self) -> Task:
        return Task(config=self.tasks_config["analyze_pipeline_logs_task"])

    @task
    def profile_warehouse_task(self) -> Task:
        return Task(config=self.tasks_config["profile_warehouse_task"])

    @task
    def synthesize_diagnosis_task(self) -> Task:
        return Task(config=self.tasks_config["synthesize_diagnosis_task"], output_pydantic=Diagnosis)

    @task
    def propose_fix_task(self) -> Task:
        return Task(config=self.tasks_config["propose_fix_task"], human_input=self._human_gated_fix)

    @task
    def write_postmortem_task(self) -> Task:
        return Task(config=self.tasks_config["write_postmortem_task"], output_pydantic=Postmortem,
                    guardrail=validate_postmortem, guardrail_max_retries=2)

    @crew
    def crew(self) -> Crew:
        kwargs: dict[str, Any] = {
            "agents": self.agents,
            "tasks": self.tasks,
            "process": Process.hierarchical,
            "manager_agent": self.manager_agent_instance(),
            "verbose": False,
            "memory": self._memory,
        }
        if self._with_knowledge:
            kwargs["knowledge_sources"] = _knowledge_sources()
        return Crew(**kwargs)


def diagnosis_from_output(result: Any, crew_obj: Crew | None = None) -> Diagnosis | None:
    """Extrai o Diagnosis da tarefa de síntese (não da última tarefa, que é o post-mortem)."""
    tasks = getattr(crew_obj, "tasks", None) or []
    for t in tasks:
        out = getattr(t, "output", None)
        if out is not None and isinstance(getattr(out, "pydantic", None), Diagnosis):
            return out.pydantic
    for out in getattr(result, "tasks_output", []) or []:
        if isinstance(getattr(out, "pydantic", None), Diagnosis):
            return out.pydantic
    return None
