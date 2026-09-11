"""Contratos tipados na costura crew -> pontuação (herdados do ws-3)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Diagnosis(BaseModel):
    """Veredito do crew para um caso; o oráculo compara com ``ops.incidents`` (origin='chaos')."""

    failure_key: str = Field(..., description="failure_key diagnosticado (ou 'multi_failure_cascade').")
    sub_failures: list[str] = Field(default_factory=list, description="Membros, só para cascata.")
    evidence_surface: str = Field(default="", description="Superfície que prova (ex.: silver_socios_rejects).")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Autoavaliação; reportada, nunca pontua.")
    summary: str = Field(default="", description="Resumo de uma linha.")


class Postmortem(BaseModel):
    """Relatório humano do incidente (saída do A5)."""

    incident_key: str = Field(..., description="failure_key diagnosticado.")
    root_cause: str = Field(..., description="Causa raiz em linguagem simples.")
    evidence: str = Field(default="", description="Evidência que sustenta a causa raiz.")
    proposed_fix: str = Field(default="", description="Correção proposta (sujeita a aprovação, nunca automática).")
    recurrence_note: str = Field(default="", description="Se é reincidente.")
