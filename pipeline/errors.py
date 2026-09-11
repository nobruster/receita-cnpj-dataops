"""Falhas de pipeline com chave estável (``failure_key``).

Toda exceção daqui vira, ao mesmo tempo:

* uma linha ``PIPELINE_FAILURE key=<chave> ...`` em ``/data/logs/pipeline.log``
  (superfície I1, lida pelo agente Log Analyst);
* um incidente ``origin='pipeline'`` em ``ops.incidents`` (aberto pela DAG).
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger("pipeline")


class PipelineFailure(RuntimeError):
    key = "pipeline_error"

    def __init__(self, message: str, **fields: object):
        super().__init__(message)
        self.fields = fields

    def contract_line(self) -> str:
        return failure_line(self.key, **self.fields)


class MissingFilesError(PipelineFailure):
    key = "missing_file"


class CorruptZipError(PipelineFailure):
    key = "corrupt_zip"


class LayoutDriftError(PipelineFailure):
    key = "layout_drift"


def failure_line(key: str, **fields: object) -> str:
    extra = " ".join(f"{k}={str(v).replace(' ', '_')}" for k, v in fields.items())
    return f"PIPELINE_FAILURE key={key} {extra}".strip()


def setup_logging(logs_dir: Path) -> None:
    """Loga o pacote ``pipeline`` também em arquivo compartilhado com o Sentinel."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    target = str(logs_dir / "pipeline.log")
    if any(getattr(h, "baseFilename", None) == target for h in log.handlers):
        return
    fh = logging.FileHandler(target, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    log.addHandler(fh)
    log.setLevel(logging.INFO)
