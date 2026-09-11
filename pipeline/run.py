"""Executa o pipeline inteiro sem Airflow (mesmos passos da DAG).

    python -m pipeline.run                      # última competência publicada
    python -m pipeline.run --competencia 2026-08
    python -m pipeline.run --competencia 2026-08 --sem-download   # usa o que já está no landing
"""

from __future__ import annotations

import argparse
import logging

from pipeline import steps


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--competencia", default=None)
    p.add_argument("--sem-download", action="store_true")
    p.add_argument("--sem-publicar", action="store_true")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    alvo = steps.discover(a.competencia)
    print(alvo)
    if alvo["skip"]:
        return
    comp = alvo["competencia"]
    if not a.sem_download:
        steps.download(comp)
    steps.load_raw(comp)
    for select in steps.DBT_LAYERS:
        steps.transform(comp, select)
    print("incidentes de qualidade:", steps.check_quality(comp))
    if not a.sem_publicar:
        print("publicado:", steps.publish_postgres(comp))
    steps.finish(comp)


if __name__ == "__main__":
    main()
