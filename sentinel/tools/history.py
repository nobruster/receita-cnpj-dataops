"""I5 — memória de incidentes (RAG leve, offline, sem embeddings).

Busca por sobreposição de termos nos post-mortems já escritos e conta
reincidências no histórico de ``ops.diagnoses``. Suficiente para o A5 dizer
"já vimos isto 3x" sem depender de um embedder (que exigiria outra chamada de API).
"""

from __future__ import annotations

import re

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from pipeline import ops
from sentinel.tools.writers import sentinel_dir


def _terms(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9_]{3,}", text.lower())}


class _Q(BaseModel):
    query: str = Field(..., description="failure_key ou descrição do sintoma")


class QueryIncidentHistory(BaseTool):
    name: str = "query_incident_history"
    description: str = "Procura incidentes parecidos já tratados (post-mortems) e conta reincidências."
    args_schema: type[BaseModel] = _Q

    def _run(self, query: str) -> str:
        q = _terms(query)
        scored = []
        for p in sentinel_dir("postmortems").glob("*.md"):
            text = p.read_text(encoding="utf-8", errors="replace")
            score = len(q & _terms(text))
            if score:
                scored.append((score, p.name, text[:400].replace("\n", " ")))
        scored.sort(reverse=True)
        try:
            with ops.session() as conn:
                n = conn.execute(
                    "SELECT count(*) AS n FROM ops.diagnoses WHERE failure_key = %s OR %s = ANY(sub_failures)",
                    [query.strip(), query.strip()],
                ).fetchone()["n"]
        except Exception:  # ledger indisponível não pode derrubar o agente
            n = 0
        head = f"diagnósticos anteriores com a chave '{query.strip()}': {n}"
        body = "\n".join(f"- {name} (score {s}): {snip}" for s, name, snip in scored[:3])
        return head + ("\n" + body if body else "\nnenhum post-mortem parecido")
