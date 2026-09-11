"""CLI do caos: ``list`` | ``sample`` | ``inject`` | ``reset``.

Regra R7 herdada: todo ciclo injetar -> detectar -> pontuar começa de uma base
limpa. ``reset`` regenera a competência com a mesma semente.

Exemplos::

    python -m chaos.cli list
    python -m chaos.cli sample --competencia 2026-08
    python -m chaos.cli inject invalid_cnpj --competencia 2026-08
    python -m chaos.cli inject multi_failure_cascade --competencia 2026-08
    python -m chaos.cli reset --competencia 2026-08
"""

from __future__ import annotations

import argparse
import random
import shutil

from chaos.failures import CASCADE_KEY, CASCADE_MEMBERS, FAILURES
from chaos.sample import generate
from pipeline import ops
from pipeline.config import get_settings


def inject(key: str, competencia: str, seed: int = 7) -> list[int]:
    """Aplica a falha nos zips da competência e grava a verdade em ops.incidents."""
    landing = get_settings().landing_dir / competencia
    rng = random.Random(seed)
    keys = list(CASCADE_MEMBERS) if key == CASCADE_KEY else [key]
    ids = []
    for k in keys:
        f = FAILURES[k]
        detail = f.inject(landing, rng)
        ids.append(ops.open_incident(k, "chaos", competencia, detail, f.evidence_surface))
    return ids


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    for name in ("sample", "reset"):
        sp = sub.add_parser(name)
        sp.add_argument("--competencia", required=True)
        sp.add_argument("--empresas", type=int, default=3000)
        sp.add_argument("--seed", type=int, default=42)
    ip = sub.add_parser("inject")
    ip.add_argument("key", choices=[*FAILURES, CASCADE_KEY])
    ip.add_argument("--competencia", required=True)
    a = p.parse_args()

    s = get_settings()
    s.ensure_dirs()
    if a.cmd == "list":
        for f in FAILURES.values():
            print(f"{f.key:<18} {f.detected_by:<13} {f.evidence_surface:<38} {f.unlocks}")
        print(f"{CASCADE_KEY:<18} {'flow':<13} {'+'.join(CASCADE_MEMBERS):<38} Flows + roteamento condicional")
    elif a.cmd in ("sample", "reset"):
        shutil.rmtree(s.landing_dir / a.competencia, ignore_errors=True)
        print(generate(a.competencia, s.landing_dir, a.empresas, a.seed))
    else:
        ops.ensure_schema()
        print("incidentes gravados (verdade de referência):", inject(a.key, a.competencia))


if __name__ == "__main__":
    main()
