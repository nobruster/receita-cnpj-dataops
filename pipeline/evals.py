"""Critérios de aceite do BRD medidos, não declarados (regra de honestidade do ws-3).

    python -m pipeline.evals                  # competência mais recente
    python -m pipeline.evals --competencia 2026-08

Imprime PASS/FAIL/SKIP por AC. O código de saída é o contrato: 0 = tudo PASS/SKIP, 1 = algum FAIL.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time

from pipeline import ops
from pipeline.warehouse import connect_ro

AC2_MAX_H = 4.0
AC3_MAX_H = 24.0
AC5_P95_S = 5.0
AC6_MIN = 0.8


def _row(ac: str, verdict: str, medido: str, meta: str) -> tuple[str, str, str, str]:
    return ac, verdict, medido, meta


def run(competencia: str | None) -> list[tuple[str, str, str, str]]:
    with ops.session() as conn:
        comp = competencia or conn.execute(
            "SELECT max(competencia) c FROM ops.competencias WHERE status = 'publicada'").fetchone()["c"]
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

        if info and info["iniciado_em"] and info["finalizado_em"]:
            h = (info["finalizado_em"] - info["iniciado_em"]).total_seconds() / 3600
            out.append(_row("AC-2 tempo", "PASS" if h <= AC2_MAX_H else "FAIL", f"{h:.2f} h", f"<= {AC2_MAX_H} h"))
        else:
            out.append(_row("AC-2 tempo", "SKIP", "sem início/fim registrados", f"<= {AC2_MAX_H} h"))

        if info and info["publicada_em"] and info["finalizado_em"]:
            h = (info["finalizado_em"] - info["publicada_em"]).total_seconds() / 3600
            out.append(_row("AC-3 frescor", "PASS" if h <= AC3_MAX_H else "FAIL",
                            f"{h:.1f} h da publicação ao gold", f"<= {AC3_MAX_H} h após detecção"))
        else:
            out.append(_row("AC-3 frescor", "SKIP", "modo offline (sem data de publicação)", f"<= {AC3_MAX_H} h"))

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

    if diag and diag["n"]:
        m = float(diag["m"])
        medido = f"match médio {m:.2f} em {diag['n']} casos"
        out.append(_row("AC-6 Sentinel", "PASS" if m >= AC6_MIN else "FAIL", medido, f">= {AC6_MIN}"))
    else:
        out.append(_row("AC-6 Sentinel", "SKIP", "nenhum caso pontuado ainda (rode o chaos)", f">= {AC6_MIN}"))
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--competencia")
    a = p.parse_args()
    rows = run(a.competencia)
    w = max(len(r[0]) for r in rows)
    for ac, v, medido, meta in rows:
        print(f"{ac:<{w}}  {v:<4}  {medido}  (meta: {meta})")
    sys.exit(1 if any(r[1] == "FAIL" for r in rows) else 0)


if __name__ == "__main__":
    main()
