"""C7 — monitores de qualidade determinísticos (rodam depois do dbt).

Mede cada competência, grava em ``ops.dq_metrics`` e compara com a competência
anterior. Violou limiar => abre incidente ``origin='monitor'``. Nada aqui usa
LLM: é a camada que continua funcionando mesmo sem o Sentinel.

Regras:

* ``volume_drop``    — linhas raw de uma entidade caíram mais que
  ``dq_volume_drop_pct`` % em relação à competência anterior.
* ``<reject_rule>``  — contagem de uma regra de rejeição explodiu: acima de
  ``max(2 x anterior, anterior + piso)``; sem histórico, taxa acima de
  ``dq_reject_rate_pct`` %.
* ``orphan_domain``  — CNAE/município/natureza fora do domínio acima do mesmo
  critério (motivo/país órfãos são defeitos conhecidos da fonte: só métrica).
* ``parse_errors``   — erros de parsing do CSV acima de 0,001% (AC-1).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import duckdb

from pipeline import ops
from pipeline.config import Settings, get_settings

log = logging.getLogger("pipeline.quality")

FACTS = ("empresas", "estabelecimentos", "socios", "simples")
ORPHAN_FLAGS = {
    "estabelecimentos": ("_orphan_cnae", "_orphan_municipio", "_orphan_motivo", "_orphan_pais"),
    "empresas": ("_orphan_natureza",),
    "socios": ("_orphan_qualificacao",),
}
MONITORED_ORPHANS = {"_orphan_cnae", "_orphan_municipio", "_orphan_natureza"}


@dataclass(frozen=True, slots=True)
class Finding:
    failure_key: str
    entidade: str
    detail: str
    evidence_surface: str


def measure(con: duckdb.DuckDBPyConnection, competencia: str) -> dict[str, dict[str, float]]:
    """Coleta as métricas da competência que está no warehouse."""
    out: dict[str, dict[str, float]] = {}
    load = dict(
        (r[0], (r[1], r[2]))
        for r in con.execute(
            "SELECT entidade, sum(linhas), sum(erros_parse) FROM raw.raw_load_log "
            "WHERE competencia = ? GROUP BY 1", [competencia]
        ).fetchall()
    )
    for ent in FACTS:
        m: dict[str, float] = {}
        linhas, erros = load.get(ent, (0, 0))
        m["linhas_raw"] = float(linhas or 0)
        m["erros_parse"] = float(erros or 0)
        m["linhas_silver"] = float(con.execute(f"SELECT count(*) FROM silver.silver_{ent}").fetchone()[0])
        for rule, n in con.execute(
            f"SELECT reject_rule, count(*) FROM silver.silver_{ent}_rejects GROUP BY 1"
        ).fetchall():
            m[f"rejeitadas:{rule}"] = float(n)
        m["rejeitadas_total"] = sum(v for k, v in m.items() if k.startswith("rejeitadas:"))
        for flag in ORPHAN_FLAGS.get(ent, ()):
            m[f"orfaos:{flag}"] = float(
                con.execute(f"SELECT count(*) FROM silver.silver_{ent}_classificado WHERE {flag}").fetchone()[0]
            )
        out[ent] = m
    return out


def _exploded(atual: float, anterior: float | None, base: float, pct: float) -> bool:
    if anterior is None:
        return base > 0 and 100.0 * atual / base > pct
    piso = max(10.0, base * 1e-6)
    return atual > max(2 * anterior, anterior + piso)


def evaluate(competencia: str, metrics: dict[str, dict[str, float]], settings: Settings | None = None,
             previous: str | None = None) -> list[Finding]:
    s = settings or get_settings()
    prev = previous if previous is not None else ops.previous_competencia(competencia)
    findings: list[Finding] = []
    for ent, m in metrics.items():
        base = m.get("linhas_raw", 0.0)

        def anterior(nome: str, ent: str = ent) -> float | None:
            return ops.get_metric(prev, ent, nome) if prev else None

        prev_linhas = anterior("linhas_raw")
        if prev_linhas and base < prev_linhas * (1 - s.dq_volume_drop_pct / 100):
            queda = 100 * (1 - base / prev_linhas)
            findings.append(Finding("volume_drop", ent,
                                    f"{ent}: {base:,.0f} linhas vs {prev_linhas:,.0f} em {prev} (-{queda:.1f}%)",
                                    "ops.dq_metrics"))
        for nome, valor in m.items():
            if nome.startswith("rejeitadas:"):
                rule = nome.split(":", 1)[1]
                prev_v = anterior(nome)
                prev_v = prev_v if prev_v is not None else (0.0 if prev else None)
                if _exploded(valor, prev_v, base, s.dq_reject_rate_pct):
                    findings.append(Finding(rule, ent, f"{ent}: {valor:,.0f} linhas em quarentena por {rule} "
                                            f"(anterior: {prev_v if prev_v is not None else 'sem histórico'})",
                                            f"silver_{ent}_rejects"))
            elif nome.startswith("orfaos:") and nome.split(":", 1)[1] in MONITORED_ORPHANS:
                prev_v = anterior(nome)
                prev_v = prev_v if prev_v is not None else (0.0 if prev else None)
                if _exploded(valor, prev_v, base, s.dq_reject_rate_pct):
                    flag = nome.split(":", 1)[1]
                    findings.append(Finding("orphan_domain", ent,
                                            f"{ent}: {valor:,.0f} linhas com {flag} (anterior: {prev_v})",
                                            f"silver_{ent}.{flag}"))
        if base and m.get("erros_parse", 0) / base > 1e-5:
            findings.append(Finding("parse_errors", ent, f"{ent}: {m['erros_parse']:,.0f} erros de parsing",
                                    "raw.raw_load_log"))
    return findings


def run(con: duckdb.DuckDBPyConnection, competencia: str) -> list[int]:
    """Mede, grava, avalia e abre incidentes. Devolve os ids abertos."""
    metrics = measure(con, competencia)
    findings = evaluate(competencia, metrics)
    for ent, m in metrics.items():
        ops.put_metrics(competencia, ent, m)
    ids = []
    for f in findings:
        log.warning("DQ_FINDING key=%s entidade=%s %s", f.failure_key, f.entidade, f.detail)
        ids.append(ops.open_incident(f.failure_key, "monitor", competencia, f.detail, f.evidence_surface))
    return ids
