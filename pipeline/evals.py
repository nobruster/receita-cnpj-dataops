"""Critérios de aceite do engineering brief (AC-1..AC-8), medidos — nunca declarados.

    python -m pipeline.evals                         # competência mais recente
    python -m pipeline.evals --competencia 2026-08
    python -m pipeline.evals --reprocessar           # também mede o AC-6 (recarrega e compara)

Imprime PASS/FAIL/SKIP por critério. O código de saída é o contrato: 0 = só PASS/SKIP,
1 = algum FAIL. A nota do Sentinel aparece como **F2-1** (critério da fase 2, não é AC do v1).
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time

import duckdb

from pipeline import history, ops, quality, steps
from pipeline.receita import loader
from pipeline.warehouse import connect_ro, connect_rw

AC2_MAX_H = 4.0
AC3_MAX_H = 24.0
AC5_P95_S = 5.0
F21_MIN = 0.8


def _row(ac: str, verdict: str, medido: str, meta: str) -> tuple[str, str, str, str]:
    return ac, verdict, medido, meta


def _ultima() -> str | None:
    with ops.session() as conn:
        return conn.execute("SELECT max(competencia) c FROM ops.competencias WHERE status = 'publicada' "
                            "AND competencia <> %s", [ops.FONTE]).fetchone()["c"]


def run(competencia: str | None) -> list[tuple[str, str, str, str]]:
    with ops.session() as conn:
        comp = competencia or _ultima()
        info = conn.execute("SELECT * FROM ops.competencias WHERE competencia = %s", [comp]).fetchone()
        diag = conn.execute(
            "SELECT avg(match_score) m, count(*) n FROM ops.diagnoses WHERE score_tier NOT IN ('unscored')"
        ).fetchone()
    out = []
    con = connect_ro()
    try:
        linhas, erros, arquivos = con.execute(
            "SELECT sum(linhas), sum(erros_parse), count(DISTINCT arquivo) FROM raw.raw_load_log WHERE competencia = ?",
            [comp]).fetchone()
        taxa = (erros or 0) / max(linhas or 1, 1)
        out.append(_row("AC-1 completude", "PASS" if arquivos == 37 and taxa <= 1e-5 else "FAIL",
                        f"{arquivos}/37 arquivos, erros de parsing {taxa:.6%}", "37/37 e <= 0,001%"))

        # AC-2 mede o PROCESSAMENTO (arquivos já locais), não a rede — O2 do Passo 4.
        if info and info["processamento_iniciado_em"] and info["finalizado_em"]:
            h = (info["finalizado_em"] - info["processamento_iniciado_em"]).total_seconds() / 3600
            out.append(_row("AC-2 processamento", "PASS" if h <= AC2_MAX_H else "FAIL", f"{h:.2f} h",
                            f"<= {AC2_MAX_H} h com arquivos locais"))
        else:
            out.append(_row("AC-2 processamento", "SKIP", "sem início/fim registrados", f"<= {AC2_MAX_H} h"))

        if info and info["detectado_em"] and info["finalizado_em"]:
            h = (info["finalizado_em"] - info["detectado_em"]).total_seconds() / 3600
            out.append(_row("AC-3 frescor", "PASS" if h <= AC3_MAX_H else "FAIL",
                            f"{h:.1f} h da detecção ao dado utilizável", f"<= {AC3_MAX_H} h"))
        else:
            out.append(_row("AC-3 frescor", "SKIP", "sem hora de detecção registrada", f"<= {AC3_MAX_H} h"))

        vaz = con.execute(
            "SELECT count(*) FROM gold.gold_empresa_detalhe g JOIN silver.silver_estabelecimentos_rejects r "
            "ON r.cnpj = g.cnpj AND r.reject_rule <> 'duplicate_key'").fetchone()[0]
        out.append(_row("AC-4 quarentena", "PASS" if vaz == 0 else "FAIL", f"{vaz} vazamentos para o gold", "0"))
    finally:
        con.close()

    from intelligence import intents

    tempos = []
    for fn in (intents.resumo_competencia, lambda: intents.painel(uf="SP"),
               lambda: intents.prospectar(uf="DF", limite=100), intents.schema_info):
        for _ in range(5):
            t = time.perf_counter()
            fn()
            tempos.append(time.perf_counter() - t)
    p95 = statistics.quantiles(tempos, n=20)[18]
    out.append(_row("AC-5 consulta", "PASS" if p95 <= AC5_P95_S else "FAIL", f"p95 {p95:.3f} s", f"<= {AC5_P95_S} s"))

    out.append(_row("AC-7 alertas da fonte", "SKIP", "provado por falhas simuladas: pytest tests/test_e2e.py",
                    "100% das falhas simuladas viram alerta"))
    out.append(_ac8())
    if diag and diag["n"]:
        m = float(diag["m"])
        medido = f"match médio {m:.2f} em {diag['n']} casos"
        out.append(_row("F2-1 Sentinel (fase 2)", "PASS" if m >= F21_MIN else "FAIL", medido, f">= {F21_MIN}"))
    else:
        out.append(_row("F2-1 Sentinel (fase 2)", "SKIP", "nenhum caso pontuado (fase 2)", f">= {F21_MIN}"))
    return out


def _ac8() -> tuple[str, str, str, str]:
    """AC-8: toda competência concluída (até 12) está no histórico e é legível."""
    with ops.session() as conn:
        feitas = [r["competencia"] for r in conn.execute(
            "SELECT competencia FROM ops.competencias WHERE status = 'publicada' AND competencia <> %s "
            "ORDER BY competencia DESC LIMIT %s", [ops.FONTE, history.RETENCAO]).fetchall()]
    if not feitas:
        return _row("AC-8 histórico", "SKIP", "nenhuma competência concluída", "12 meses consultáveis")
    arq = set(history.arquivadas())
    faltam = [c for c in feitas if c not in arq]
    con = duckdb.connect()
    try:
        ilegiveis = []
        for c in feitas:
            if c in arq:
                try:
                    con.execute(f"SELECT count(*) FROM {history.read_sql('estabelecimentos', c)}").fetchone()
                except Exception:
                    ilegiveis.append(c)
    finally:
        con.close()
    ok = not faltam and not ilegiveis and len(arq) <= history.RETENCAO
    medido = f"{len(feitas) - len(faltam)}/{len(feitas)} concluídas no histórico; {len(arq)} partições"
    if faltam or ilegiveis:
        medido += f"; faltam {faltam} ilegíveis {ilegiveis}"
    return _row("AC-8 histórico", "PASS" if ok else "FAIL", medido, "concluídas (até 12) arquivadas e legíveis")


def reprocessar(competencia: str) -> tuple[str, str, str, str]:
    """AC-6: recarrega raw + dbt e compara as métricas com as gravadas (sem abrir incidentes)."""
    meta = "métricas idênticas"
    with ops.session() as conn:
        rodando = conn.execute(
            "SELECT competencia FROM ops.competencias WHERE status IN ('baixando', 'carregando', 'transformada')"
        ).fetchall()
        antes = {(r["entidade"], r["metrica"]): r["valor"] for r in conn.execute(
            "SELECT entidade, metrica, valor FROM ops.dq_metrics WHERE competencia = %s", [competencia])}
    if rodando:
        return _row("AC-6 reprocessamento", "SKIP", f"DAG em andamento ({rodando[0]['competencia']})", meta)
    if not antes:
        return _row("AC-6 reprocessamento", "SKIP", "competência sem métricas gravadas", meta)
    s = steps.get_settings()
    con = connect_rw(s)
    try:
        loader.load_all(con, s.landing_dir / competencia, s.work_dir / competencia, competencia)
    finally:
        con.close()
    for sel in steps.DBT_LAYERS:
        steps.dbt(competencia, sel)
    con = connect_rw(s)
    try:
        depois = {(e, k): v for e, m in quality.measure(con, competencia).items() for k, v in m.items()}
    finally:
        con.close()
    difs = sorted(k for k in set(antes) | set(depois) if antes.get(k) != depois.get(k))
    medido = f"{len(antes)} métricas comparadas; {len(difs)} diferentes" + (f": {difs[:5]}" if difs else "")
    return _row("AC-6 reprocessamento", "PASS" if not difs else "FAIL", medido, meta)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--competencia")
    p.add_argument("--reprocessar", action="store_true", help="mede também o AC-6 (recarrega a competência)")
    a = p.parse_args()
    rows = run(a.competencia)
    if a.reprocessar:
        comp = a.competencia or _ultima()
        rows.insert(5, reprocessar(comp))
    w = max(len(r[0]) for r in rows)
    for ac, v, medido, meta in rows:
        print(f"{ac:<{w}}  {v:<4}  {medido}  (meta: {meta})")
    sys.exit(1 if any(r[1] == "FAIL" for r in rows) else 0)


if __name__ == "__main__":
    main()
