"""Ferramentas de LEITURA do Sentinel (superfícies I1–I5). Nenhuma escreve no Componente A.

* I1 ``ReadPipelineLogs``    — linhas de contrato ``PIPELINE_FAILURE`` / ``DQ_FINDING``.
* I2 ``ReadDbtRunResults``   — nós que falharam no último ``dbt build``.
* I3 ``ProfileRejects``      — quarentena por regra + amostra mínima (DuckDB somente leitura).
* I3 ``QueryWarehouse``      — SELECT com lista de tabelas permitidas e LIMIT forçado.
* I4 ``ReadQualityMetrics``  — ``ops.dq_metrics`` (mês atual vs anterior) + incidentes
  ``pipeline``/``monitor``. Os incidentes ``chaos`` (verdade de referência) NUNCA aparecem aqui.

Soberania (AC-8): as ferramentas devolvem só agregados e amostras pequenas de dado
público — nunca a base em massa para o LLM.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from intelligence.sql_guard import open_ro as _ro
from intelligence.sql_guard import run_guarded_select
from pipeline import ops
from pipeline.config import get_settings

REJECT_TABLES = ("estabelecimentos", "empresas", "socios", "simples")


class _Competencia(BaseModel):
    competencia: str = Field(default="", description="AAAA-MM (vazio = mais recente)")


class ReadPipelineLogs(BaseTool):
    name: str = "read_pipeline_logs"
    description: str = (
        "Lê o log do pipeline e devolve as linhas de contrato PIPELINE_FAILURE (falha de download, zip, "
        "layout, arquivo ausente) e DQ_FINDING (monitores de qualidade). Use para falhas de PIPELINE."
    )
    args_schema: type[BaseModel] = _Competencia

    def _run(self, competencia: str = "") -> str:
        path = get_settings().logs_dir / "pipeline.log"
        if not path.exists():
            return "log do pipeline ainda não existe (nenhuma execução)"
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        hits = [ln for ln in lines if ("PIPELINE_FAILURE" in ln or "DQ_FINDING" in ln)
                and (not competencia or competencia in ln or "DQ_FINDING" in ln)]
        return "\n".join(hits[-40:]) or "nenhuma falha de pipeline registrada no log"


class _Empty(BaseModel):
    pass


class ReadDbtRunResults(BaseTool):
    name: str = "read_dbt_run_results"
    description: str = "Lista modelos/testes do último dbt build que falharam ou deram erro (run_results.json)."
    args_schema: type[BaseModel] = _Empty

    def _run(self) -> str:
        target = Path(os.environ.get("DBT_TARGET_PATH", str(get_settings().data_dir / "dbt" / "target")))
        rr = target / "run_results.json"
        if not rr.exists():
            return "sem run_results.json (dbt ainda não rodou)"
        data = json.loads(rr.read_text(encoding="utf-8"))
        bad = [f"{r['unique_id']}: {r['status']} — {(r.get('message') or '')[:200]}"
               for r in data.get("results", []) if r.get("status") in ("error", "fail", "runtime error")]
        return "\n".join(bad) or f"último dbt build sem falhas ({len(data.get('results', []))} nós)"


class _Entidade(BaseModel):
    entidade: str = Field(default="", description="estabelecimentos | empresas | socios | simples (vazio = todas)")


class ProfileRejects(BaseTool):
    name: str = "profile_rejects"
    description: str = (
        "Conta linhas em quarentena (silver_<entidade>_rejects) por reject_rule — o reject_rule É o "
        "failure_key — e mostra 3 exemplos por regra. Também conta flags de órfão de domínio."
    )
    args_schema: type[BaseModel] = _Entidade

    def _run(self, entidade: str = "") -> str:
        ents = [entidade] if entidade in REJECT_TABLES else list(REJECT_TABLES)
        out = []
        con = _ro()
        try:
            for ent in ents:
                rows = con.execute(
                    f"SELECT reject_rule, count(*) FROM silver.silver_{ent}_rejects GROUP BY 1 ORDER BY 2 DESC"
                ).fetchall()
                if not rows:
                    out.append(f"silver_{ent}_rejects: vazio")
                    continue
                for rule, n in rows:
                    key = "cnpj" if ent == "estabelecimentos" else "cnpj_basico"
                    ex = con.execute(
                        f"SELECT {key}, _arquivo FROM silver.silver_{ent}_rejects WHERE reject_rule = ? LIMIT 3",
                        [rule],
                    ).fetchall()
                    out.append(f"silver_{ent}_rejects: {rule} = {n} linhas; exemplos: {ex}")
            flags = con.execute(
                "SELECT count(*) FILTER (WHERE _orphan_cnae), count(*) FILTER (WHERE _orphan_municipio), "
                "count(*) FILTER (WHERE _orphan_motivo), count(*) FILTER (WHERE _orphan_pais) "
                "FROM silver.silver_estabelecimentos_classificado"
            ).fetchone()
            out.append(f"silver_estabelecimentos órfãos: cnae={flags[0]} municipio={flags[1]} "
                       f"motivo={flags[2]} pais={flags[3]} (motivo/pais órfãos são defeitos conhecidos da fonte)")
        finally:
            con.close()
        return "\n".join(out)


class _Sql(BaseModel):
    sql: str = Field(..., description="Um único SELECT sobre silver.silver_*, gold.gold_* ou raw.raw_load_log")


# Colunas de dado pessoal que NUNCA vão para o LLM (soberania/LGPD — achado 11 do reviewer).
PII_COLUMNS: tuple[str, ...] = (
    "correio_eletronico", "ddd_1", "telefone_1", "ddd_2", "telefone_2", "ddd_fax", "fax", "nome_socio",
    "cnpj_cpf_socio", "representante_legal", "nome_representante", "logradouro", "numero", "complemento",
)
LLM_MAX_ROWS = 20


class QueryWarehouse(BaseTool):
    name: str = "query_warehouse"
    description: str = (
        "Executa UM SELECT somente-leitura no DuckDB (tabelas silver.silver_*, gold.gold_*, raw.raw_load_log). "
        f"Devolve no máximo {LLM_MAX_ROWS} linhas; colunas de contato/sócio e SELECT * são bloqueados. "
        "Prefira agregações (count, group by)."
    )
    args_schema: type[BaseModel] = _Sql

    def _run(self, sql: str) -> str:
        return run_guarded_select(sql, max_rows=LLM_MAX_ROWS, deny_columns=PII_COLUMNS)


class ReadQualityMetrics(BaseTool):
    name: str = "read_quality_metrics"
    description: str = (
        "Métricas de qualidade da competência vs a anterior (linhas raw, silver, rejeitadas por regra, órfãos) "
        "e incidentes abertos pelos monitores e pelo pipeline. Use para queda de volume e explosão de rejeições."
    )
    args_schema: type[BaseModel] = _Competencia

    def _run(self, competencia: str = "") -> str:
        with ops.session() as conn:
            comp = competencia or (conn.execute("SELECT max(competencia) c FROM ops.dq_metrics").fetchone()["c"])
            if not comp:
                return "sem métricas registradas"
            prev = conn.execute("SELECT max(competencia) c FROM ops.dq_metrics WHERE competencia < %s",
                                [comp]).fetchone()["c"]
            rows = conn.execute(
                "SELECT a.entidade, a.metrica, a.valor, b.valor AS anterior FROM ops.dq_metrics a "
                "LEFT JOIN ops.dq_metrics b ON b.entidade = a.entidade AND b.metrica = a.metrica "
                "AND b.competencia = %s WHERE a.competencia = %s ORDER BY 1, 2", [prev, comp]
            ).fetchall()
            inc = conn.execute(
                "SELECT failure_key, origin, detail FROM ops.incidents WHERE competencia = %s "
                "AND origin IN ('pipeline', 'monitor') ORDER BY incident_id", [comp]
            ).fetchall()
        def fmt(v: float | None) -> str:
            return "-" if v is None else f"{v:,.0f}"

        linhas = [f"competência {comp} (anterior: {prev or 'nenhuma'})"]
        linhas += [f"  {r['entidade']}.{r['metrica']}: {fmt(r['valor'])} (antes: {fmt(r['anterior'])})"
                   for r in rows if r["valor"] or r["anterior"]]
        linhas.append("incidentes abertos pelo backbone:")
        linhas += [f"  [{i['origin']}] {i['failure_key']}: {i['detail']}" for i in inc] or ["  nenhum"]
        return "\n".join(linhas)
