"""Guardrail do post-mortem (desbloqueio 'Guardrails + output_pydantic' do encoding_mojibake).

Um post-mortem precisa ser estruturado mesmo quando a evidência é lixo (texto com
mojibake). Recusa campos vazios e ruído bruto colado no relatório.
"""

# Sem `from __future__ import annotations`: o CrewAI inspeciona a anotação de retorno.
import re
from typing import Any, Tuple  # noqa: UP035 — o CrewAI valida a anotação em runtime

from sentinel.models import Postmortem

_NOISE = re.compile(r"[ÃÂ][\x80-\xBF]|�")


def validate_postmortem(output: Any) -> Tuple[bool, Any]:  # noqa: UP006
    pm = getattr(output, "pydantic", None) or output
    if not isinstance(pm, Postmortem):
        return False, "A saída precisa ser um Postmortem tipado (incident_key, root_cause, evidence, proposed_fix)."
    if not pm.incident_key.strip() or len(pm.root_cause.strip()) < 15:
        return False, "incident_key e root_cause (>= 15 caracteres) são obrigatórios."
    for field in ("root_cause", "evidence", "proposed_fix"):
        if _NOISE.search(getattr(pm, field)):
            return False, f"O campo {field} contém texto corrompido; resuma em vez de colar o dado bruto."
    return True, pm
