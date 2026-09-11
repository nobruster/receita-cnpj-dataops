"""Oráculo de pontuação — compara o Diagnosis com a verdade de referência (origin='chaos').

Pontua, nunca afirma que o crew está certo (regra R5). Rubrica determinística:

* Tier 1 (match, decide): 1.0 exato · 0.7 alias justificado · cascata:
  0.5 + 0.5 x (membros acertados / membros reais) · 0.0 erro.
* Tier 2 (evidência, não decide): a superfície citada bate com a esperada? Pega
  "chave certa com evidência inventada" (match=1.0, evidence=0.0).
* Sem diagnóstico => ``no-run`` (nunca uma nota fabricada). Sem verdade de
  referência (incidente real, não injetado) => ``unscored``.
"""

from __future__ import annotations

from dataclasses import dataclass

from chaos.failures import CASCADE_KEY, FAILURES
from sentinel.models import Diagnosis

EXPECTED_SURFACE: dict[str, str] = {k: f.evidence_surface for k, f in FAILURES.items()}
ALIASES: dict[tuple[str, str], float] = {("parse_errors", "layout_drift"): 0.7}


@dataclass(frozen=True, slots=True)
class ScoreResult:
    tier: str  # exact | alias | cascade | miss | no-run | unscored
    match: float
    evidence: float | None
    truth: tuple[str, ...]
    diagnosed: str | None


def _evidence(diag: Diagnosis, key: str) -> float:
    expected = EXPECTED_SURFACE.get(key, "")
    got = diag.evidence_surface.strip().lower()
    if not expected or not got:
        return 0.0
    if got == expected.lower():
        return 1.0
    return 0.5 if expected.split(".")[0].lower() in got else 0.0


def score(diag: Diagnosis | None, truth_keys: list[str] | tuple[str, ...]) -> ScoreResult:
    truth = tuple(sorted(set(truth_keys)))
    if diag is None:
        return ScoreResult("no-run", 0.0, None, truth, None)
    if not truth:
        return ScoreResult("unscored", 0.0, None, truth, diag.failure_key)
    key = diag.failure_key.strip()
    if len(truth) > 1:
        if key != CASCADE_KEY:
            return ScoreResult("miss", 0.0, None, truth, key)
        overlap = len(set(diag.sub_failures) & set(truth)) / len(truth)
        return ScoreResult("cascade", 0.5 + 0.5 * overlap, None, truth, key)
    real = truth[0]
    if key == real:
        return ScoreResult("exact", 1.0, _evidence(diag, real), truth, key)
    alias = ALIASES.get((key, real)) or ALIASES.get((real, key))
    if alias:
        return ScoreResult("alias", alias, _evidence(diag, real), truth, key)
    return ScoreResult("miss", 0.0, _evidence(diag, real), truth, key)
