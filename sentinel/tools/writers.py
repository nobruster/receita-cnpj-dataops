"""As DUAS únicas ferramentas que escrevem — e só em ``/data/sentinel`` (regra R3).

* A4 ``ProposePatch``   — patch proposto em ``/data/sentinel/proposed/``. Consultivo:
  nunca é aplicado ao pipeline; um humano revisa e aplica, se quiser.
* A5 ``WritePostmortem`` — post-mortem em ``/data/sentinel/postmortems/``.

O nome do arquivo é "slugificado" e revalidado com ``relative_to``: um
``failure_key`` malicioso não consegue escapar do diretório.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from pipeline.config import get_settings


def sentinel_dir(sub: str) -> Path:
    d = get_settings().data_dir / "sentinel" / sub
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_path(sub: str, key: str, ext: str = "md") -> Path:
    base = sentinel_dir(sub).resolve()
    slug = re.sub(r"[^a-z0-9_-]+", "-", key.lower()).strip("-")[:60] or "incidente"
    path = (base / f"{datetime.now(UTC):%Y%m%dT%H%M%S}-{slug}.{ext}").resolve()
    path.relative_to(base)  # ValueError se tentar escapar
    return path


class _Patch(BaseModel):
    failure_key: str = Field(..., description="failure_key diagnosticado")
    patch: str = Field(..., description="Mudança proposta em markdown (SQL/dbt/config) e como validar")


class ProposePatch(BaseTool):
    name: str = "propose_patch"
    description: str = (
        "Grava uma correção PROPOSTA (dbt, SQL, configuração ou ação operacional) para revisão humana. "
        "Nunca é aplicada automaticamente."
    )
    args_schema: type[BaseModel] = _Patch

    def _run(self, failure_key: str, patch: str) -> str:
        path = _safe_path("proposed", failure_key)
        path.write_text(f"# Patch proposto — {failure_key}\n\n> Consultivo: requer revisão e aplicação humana.\n\n"
                        f"{patch}\n", encoding="utf-8")
        return f"patch proposto gravado em {path}"


class _Pm(BaseModel):
    incident_key: str
    root_cause: str
    evidence: str = ""
    proposed_fix: str = ""
    recurrence_note: str = ""


class WritePostmortem(BaseTool):
    name: str = "write_postmortem"
    description: str = "Grava o post-mortem (sem culpados) do incidente em markdown."
    args_schema: type[BaseModel] = _Pm

    def _run(self, incident_key: str, root_cause: str, evidence: str = "", proposed_fix: str = "",
             recurrence_note: str = "") -> str:
        path = _safe_path("postmortems", incident_key)
        path.write_text(
            f"# Post-mortem — {incident_key}\n\n## Causa raiz\n{root_cause}\n\n## Evidência\n{evidence}\n\n"
            f"## Correção proposta\n{proposed_fix}\n\n## Reincidência\n{recurrence_note}\n",
            encoding="utf-8",
        )
        return f"post-mortem gravado em {path}"
