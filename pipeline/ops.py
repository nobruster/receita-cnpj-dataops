"""Ledger operacional no PostgreSQL (schema ``ops``).

É a costura entre os dois componentes, como o ``injected_incidents`` do ws-3:

* ``ops.competencias`` — controle de qual competência já foi processada
  (o pipeline sempre busca a última publicada e pula as já concluídas).
* ``ops.dq_metrics`` — histórico de métricas por competência/entidade
  (linhas, rejeições...). É o que permite comparar mês contra mês.
* ``ops.incidents`` — incidentes abertos pelo pipeline (``origin='pipeline'``),
  pelos monitores de qualidade (``'monitor'``) ou pelo injetor de falhas
  (``'chaos'`` — a verdade de referência para pontuar o Sentinel).
* ``ops.diagnoses`` — veredito tipado do Sentinel e sua pontuação.

Regra R3: o Componente A escreve aqui; o Sentinel só LÊ ``incidents``/
``dq_metrics`` e escreve apenas em ``diagnoses``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

import psycopg
from psycopg.rows import dict_row

from pipeline.config import Settings, get_settings

# Pseudo-competência para incidentes da FONTE (servidor fora do ar, publicação atrasada),
# que não pertencem a um mês específico.
FONTE = "fonte"

DDL = """
CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE IF NOT EXISTS ops.competencias (
    competencia   TEXT PRIMARY KEY,
    status        TEXT NOT NULL DEFAULT 'descoberta',
    publicada_em  TIMESTAMPTZ,
    bytes_total   BIGINT,
    iniciado_em   TIMESTAMPTZ,
    finalizado_em TIMESTAMPTZ,
    detalhe       TEXT
);

ALTER TABLE ops.competencias ADD COLUMN IF NOT EXISTS detectado_em TIMESTAMPTZ;
ALTER TABLE ops.competencias ADD COLUMN IF NOT EXISTS processamento_iniciado_em TIMESTAMPTZ;
ALTER TABLE ops.competencias ADD COLUMN IF NOT EXISTS atualizado_em TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS ops.dq_metrics (
    competencia TEXT NOT NULL,
    entidade    TEXT NOT NULL,
    metrica     TEXT NOT NULL,
    valor       DOUBLE PRECISION NOT NULL,
    medido_em   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (competencia, entidade, metrica)
);

CREATE TABLE IF NOT EXISTS ops.incidents (
    incident_id      BIGSERIAL PRIMARY KEY,
    failure_key      TEXT NOT NULL,
    origin           TEXT NOT NULL CHECK (origin IN ('pipeline', 'monitor', 'chaos')),
    competencia      TEXT,
    detail           TEXT NOT NULL DEFAULT '',
    evidence_surface TEXT NOT NULL DEFAULT '',
    detected_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    status           TEXT NOT NULL DEFAULT 'open'
);
CREATE INDEX IF NOT EXISTS incidents_detected_at_idx ON ops.incidents (detected_at);

CREATE TABLE IF NOT EXISTS ops.diagnoses (
    diagnosis_id     BIGSERIAL PRIMARY KEY,
    incident_ids     BIGINT[] NOT NULL,
    route            TEXT NOT NULL,
    failure_key      TEXT,
    sub_failures     TEXT[] NOT NULL DEFAULT '{}',
    evidence_surface TEXT,
    confidence       DOUBLE PRECISION,
    summary          TEXT,
    score_tier       TEXT,
    match_score      DOUBLE PRECISION,
    evidence_score   DOUBLE PRECISION,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


@contextmanager
def session(settings: Settings | None = None) -> Iterator[psycopg.Connection]:
    s = settings or get_settings()
    with psycopg.connect(s.pg_dsn, row_factory=dict_row, autocommit=True) as conn:
        yield conn


def ensure_schema(settings: Settings | None = None) -> None:
    with session(settings) as conn:
        conn.execute(DDL)


# --- competências -----------------------------------------------------------

FINAL_STATUSES: tuple[str, ...] = ("publicada", "falhou")


def set_status(competencia: str, status: str, detalhe: str = "", **extra: object) -> None:
    """Upsert do status; ``atualizado_em`` sempre avança (o gatilho do Sentinel depende disso)."""
    cols = {"status": status, "detalhe": detalhe, **extra}
    sets = ", ".join(f"{k} = EXCLUDED.{k}" for k in cols)
    names = ", ".join(cols)
    marks = ", ".join(["%s"] * len(cols))
    with session() as conn:
        conn.execute(
            f"INSERT INTO ops.competencias (competencia, {names}, atualizado_em) VALUES (%s, {marks}, now()) "
            f"ON CONFLICT (competencia) DO UPDATE SET {sets}, atualizado_em = now()",
            [competencia, *cols.values()],
        )


def mark_detected(competencia: str, reset: bool = False) -> None:
    """Marca a competência como EM ANDAMENTO (status ``descoberta``) e grava a hora da detecção.

    ``detectado_em`` é a âncora do AC-3: a primeira detecção vale, exceto num reprocessamento
    forçado (``reset=True``), que é um novo evento de detecção.
    """
    novo = "EXCLUDED.detectado_em" if reset else "COALESCE(ops.competencias.detectado_em, EXCLUDED.detectado_em)"
    with session() as conn:
        conn.execute(
            "INSERT INTO ops.competencias (competencia, status, detalhe, detectado_em, atualizado_em) "
            "VALUES (%s, 'descoberta', 'competência em processamento', now(), now()) "
            "ON CONFLICT (competencia) DO UPDATE SET status = 'descoberta', "
            f"detalhe = 'competência em processamento', detectado_em = {novo}, atualizado_em = now()",
            [competencia],
        )


def has_incident(failure_key: str, competencia: str) -> bool:
    with session() as conn:
        row = conn.execute(
            "SELECT 1 FROM ops.incidents WHERE failure_key = %s AND competencia = %s LIMIT 1",
            [failure_key, competencia],
        ).fetchone()
    return row is not None


def last_processed() -> str | None:
    """Última competência que chegou até o fim (status 'publicada')."""
    with session() as conn:
        row = conn.execute(
            "SELECT max(competencia) AS c FROM ops.competencias WHERE status = 'publicada' AND competencia <> %s",
            [FONTE],
        ).fetchone()
    return row["c"] if row else None


# --- métricas ---------------------------------------------------------------

def put_metrics(competencia: str, entidade: str, metrics: dict[str, float]) -> None:
    with session() as conn, conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO ops.dq_metrics (competencia, entidade, metrica, valor) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (competencia, entidade, metrica) DO UPDATE SET valor = EXCLUDED.valor, medido_em = now()",
            [(competencia, entidade, k, float(v)) for k, v in metrics.items()],
        )


def get_metric(competencia: str, entidade: str, metrica: str) -> float | None:
    with session() as conn:
        row = conn.execute(
            "SELECT valor FROM ops.dq_metrics WHERE competencia = %s AND entidade = %s AND metrica = %s",
            [competencia, entidade, metrica],
        ).fetchone()
    return row["valor"] if row else None


def previous_competencia(competencia: str) -> str | None:
    with session() as conn:
        row = conn.execute(
            "SELECT max(competencia) AS c FROM ops.dq_metrics WHERE competencia < %s", [competencia]
        ).fetchone()
    return row["c"] if row else None


# --- incidentes -------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Incident:
    incident_id: int
    failure_key: str
    origin: str
    competencia: str | None
    detail: str
    evidence_surface: str
    detected_at: datetime


UNDIAGNOSED = "NOT EXISTS (SELECT 1 FROM ops.diagnoses d WHERE i.incident_id = ANY(d.incident_ids))"


def open_incident_once(failure_key: str, origin: str, competencia: str | None, detail: str = "",
                       evidence_surface: str = "") -> int:
    """Como :func:`open_incident`, mas reaproveita um incidente igual ainda não diagnosticado
    (reexecuções não duplicam alertas — achado 14 do reviewer)."""
    with session() as conn:
        row = conn.execute(
            f"SELECT incident_id FROM ops.incidents i WHERE failure_key = %s AND origin = %s "
            f"AND competencia IS NOT DISTINCT FROM %s AND {UNDIAGNOSED} LIMIT 1",
            [failure_key, origin, competencia],
        ).fetchone()
    if row:
        return int(row["incident_id"])
    return open_incident(failure_key, origin, competencia, detail, evidence_surface)


def open_incident(failure_key: str, origin: str, competencia: str | None, detail: str = "",
                  evidence_surface: str = "") -> int:
    with session() as conn:
        row = conn.execute(
            "INSERT INTO ops.incidents (failure_key, origin, competencia, detail, evidence_surface) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING incident_id",
            [failure_key, origin, competencia, detail, evidence_surface],
        ).fetchone()
    return int(row["incident_id"])


def incidents_since(since: datetime, origins: tuple[str, ...] | None = None) -> list[Incident]:
    q = "SELECT * FROM ops.incidents WHERE detected_at > %s"
    params: list[object] = [since]
    if origins:
        q += " AND origin = ANY(%s)"
        params.append(list(origins))
    with session() as conn:
        rows = conn.execute(q + " ORDER BY incident_id", params).fetchall()
    return [
        Incident(r["incident_id"], r["failure_key"], r["origin"], r["competencia"], r["detail"],
                 r["evidence_surface"], r["detected_at"])
        for r in rows
    ]
