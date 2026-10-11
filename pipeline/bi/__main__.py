"""Ponto de entrada: ``python -m pipeline.bi`` publica todas as tabelas aprovadas da allowlist."""
from __future__ import annotations

import logging
import sys

from pipeline.bi import publicar
from pipeline.config import get_settings
from pipeline.warehouse import connect_ro


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    con = connect_ro(settings)
    try:
        publicadas = publicar.publicar_todas(con, settings=settings)
    finally:
        con.close()
    logging.getLogger("pipeline.bi").info("%d tabela(s) publicada(s)", len(publicadas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
