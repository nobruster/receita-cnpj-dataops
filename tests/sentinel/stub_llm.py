"""LLM roteirizado: roda a máquina real do CrewAI sem gastar token nem precisar de chave.

Prova a FIAÇÃO (agentes, tarefas, output_pydantic, guardrail, pontuação) — não prova
que um LLM de verdade diagnostica bem. Isso é papel do scorecard com chave (R5).
"""

from __future__ import annotations

import json
from typing import Any

from crewai.llms.base_llm import BaseLLM


class StubLLM(BaseLLM):
    diagnosis: dict = {}
    calls: list = []

    def __init__(self, diagnosis: dict, **kw: Any) -> None:
        super().__init__(model="stub/roteirizado", **kw)
        self.diagnosis = diagnosis
        self.calls = []

    def call(self, messages: Any, tools: Any = None, callbacks: Any = None, available_functions: Any = None,
             from_task: Any = None, from_agent: Any = None, response_model: Any = None) -> str:
        text = json.dumps(messages, default=str) if not isinstance(messages, str) else messages
        self.calls.append(text[-400:])
        if "incident_key" in text or "Postmortem" in text or "post-mortem" in text.lower():
            payload = {
                "incident_key": self.diagnosis["failure_key"],
                "root_cause": "Linhas da entrega da Receita violaram a regra de qualidade correspondente.",
                "evidence": self.diagnosis.get("evidence_surface", ""),
                "proposed_fix": "Patch proposto gravado para revisão humana.",
                "recurrence_note": "primeira ocorrência",
            }
        elif "failure_key" in text:
            payload = self.diagnosis
        else:
            return "Thought: tenho o suficiente.\nFinal Answer: investigação concluída, evidência registrada."
        return "Thought: tenho o suficiente.\nFinal Answer: " + json.dumps(payload, ensure_ascii=False)

    def supports_function_calling(self) -> bool:
        return False

    def supports_stop_words(self) -> bool:
        return False

    def get_context_window_size(self) -> int:
        return 16384
